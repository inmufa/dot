"""Checkpoints before Write/Edit and /rewind (files and transcript)."""

import logging
from collections.abc import Callable

from dot_contracts.sessions import RestoredFile, RewindOut
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.engine.turn import TurnRegistry
from backend.core.exceptions import DomainException
from backend.governance.models import Checkpoint
from backend.routing.clients.sandbox_client import SandboxClient
from backend.sessions.models import Message, Session
from backend.sessions.services.transcript import TranscriptStore

logger = logging.getLogger(__name__)
SESSION_NOT_FOUND = 2000
REWIND_TARGET_INVALID = 2002
RESTORE_FAILED = 3004
CHECKPOINT_FAILED = 3007
_SKIPPABLE = {400, 403, 404}  # bad path: the tool itself reports it


class CheckpointService:
    def __init__(
        self,
        maker: async_sessionmaker,
        store: TranscriptStore,
        sandbox: SandboxClient,
        turns: TurnRegistry,
        on_rewind: Callable[[str], None] | None = None,
    ) -> None:
        self._maker = maker
        self._store = store
        self._sandbox = sandbox
        self._turns = turns
        self._on_rewind = on_rewind

    async def record(
        self, session_pk: int, session: str, call_id: str, abs_path: str
    ) -> None:
        """Snapshot a file before it is written. Fails closed on sandbox trouble."""
        r = await self._sandbox.post(
            session, "/internal/checkpoint", {"path": abs_path}
        )
        if r.status in _SKIPPABLE:
            return
        if not r.ok:
            raise DomainException(CHECKPOINT_FAILED)
        seq = await self._store.last_seq(session_pk) + 1
        async with self._maker() as db:
            db.add(
                Checkpoint(
                    session_id=session_pk,
                    call_id=call_id,
                    sandbox_id=str(r.data["checkpoint_id"]),
                    path=abs_path,
                    msg_seq=seq,
                )
            )
            await db.commit()

    async def rewind(self, public_id: str, to_seq: int) -> RewindOut:
        self._turns.claim(public_id)  # 2001 while a turn runs; blocks new turns
        try:
            return await self._rewind(public_id, to_seq)
        finally:
            self._turns.release(public_id)

    async def _rewind(self, public_id: str, to_seq: int) -> RewindOut:
        async with self._maker() as db:
            sess = await db.scalar(
                select(Session).where(Session.public_id == public_id)
            )
            if sess is None:
                raise DomainException(SESSION_NOT_FOUND)
            rows = (
                await db.execute(
                    select(Message.seq, Message.role)
                    .where(Message.session_id == sess.id, Message.rewound.is_(False))
                    .order_by(Message.seq)
                )
            ).all()
        cutoff = _turn_end(rows, to_seq)
        restored = await self._restore_files(sess.id, public_id, cutoff)
        async with self._maker() as db:
            result = await db.execute(
                update(Message)
                .where(Message.session_id == sess.id, Message.seq > cutoff)
                .where(Message.rewound.is_(False))
                .values(rewound=True)
            )
            await db.commit()
        # Rewinding past a compaction un-compacts: the summary row is rewound too.
        await self._store.uncompact_after_rewind(sess.id, cutoff)
        if self._on_rewind:
            self._on_rewind(public_id)
        return RewindOut(
            kept_through_seq=cutoff,
            rewound_messages=result.rowcount or 0,
            restored=restored,
        )

    async def _restore_files(
        self, session_pk: int, public_id: str, cutoff: int
    ) -> list[RestoredFile]:
        async with self._maker() as db:
            q = (
                select(Checkpoint)
                .where(Checkpoint.session_id == session_pk)
                .where(Checkpoint.msg_seq > cutoff, Checkpoint.restored.is_(False))
                .order_by(Checkpoint.id.desc())  # newest first: oldest content wins
            )
            cps = list((await db.scalars(q)).all())
        # Prove every snapshot is intact first: a pruned one must fail the rewind
        # before any file is touched, never leave it half restored.
        for cp in cps:
            r = await self._sandbox.post(
                public_id,
                "/internal/restore",
                {"checkpoint_id": cp.sandbox_id, "dry_run": True},
            )
            if not r.ok:
                logger.warning("checkpoint unavailable: %s", r.error_text())
                raise DomainException(RESTORE_FAILED)
        done: list[RestoredFile] = []
        for cp in cps:
            r = await self._sandbox.post(
                public_id, "/internal/restore", {"checkpoint_id": cp.sandbox_id}
            )
            if not r.ok:
                logger.warning("restore failed: %s", r.error_text())
                raise DomainException(RESTORE_FAILED)
            async with self._maker() as db:
                await db.execute(
                    update(Checkpoint)
                    .where(Checkpoint.id == cp.id)
                    .values(restored=True)
                )
                await db.commit()
            done.append(RestoredFile(path=r.data["path"], action=r.data["action"]))
        return done


def _turn_end(rows: list, to_seq: int) -> int:
    """Last seq of the turn that contains to_seq (0 means: rewind everything)."""
    if to_seq == 0:
        return 0
    seqs = [seq for seq, _ in rows]
    if to_seq not in seqs:
        raise DomainException(REWIND_TARGET_INVALID)
    cutoff = to_seq
    for seq, role in rows:
        if seq > to_seq:
            if role == "user":
                break
            cutoff = seq
    return cutoff
