"""Compaction writes. Rows are never deleted: they get a marker or a view text."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.sessions.models import CompactionRecord, Message
from backend.sessions.services.transcript_tokens import estimate_tokens


class Overlay:
    def __init__(self, maker: async_sessionmaker) -> None:
        self._maker = maker

    async def set_views(self, session_pk: int, views: dict[int, str]) -> None:
        if not views:
            return
        async with self._maker() as db:
            for seq, text in views.items():
                await db.execute(
                    update(Message)
                    .where(Message.session_id == session_pk, Message.seq == seq)
                    .values(view_content=text)
                )
            await db.commit()

    async def commit_summary(
        self, session_pk: int, head_seqs: list[int], content: str, *, tainted: bool
    ) -> int:
        """Append the summary row and fold `head_seqs` into it; returns its seq."""
        async with self._maker() as db:
            last = await db.scalar(
                select(func.max(Message.seq)).where(Message.session_id == session_pk)
            )
            seq = (last or 0) + 1
            db.add(
                Message(
                    session_id=session_pk,
                    seq=seq,
                    role="summary",
                    content=content,
                    token_count=estimate_tokens(content),
                    tainted=tainted,
                )
            )
            await db.execute(
                update(Message)
                .where(Message.session_id == session_pk, Message.seq.in_(head_seqs))
                .values(compacted_into=seq)
            )
            await db.commit()
        return seq

    async def record(
        self,
        session_pk: int,
        trigger: str,
        stages: list[str],
        before: int,
        after: int,
        summary_seq: int | None,
    ) -> CompactionRecord:
        async with self._maker() as db:
            last = await db.scalar(
                select(func.max(Message.seq)).where(Message.session_id == session_pk)
            )
            row = CompactionRecord(
                session_id=session_pk,
                trigger=trigger,
                stages=stages,
                tokens_before=before,
                tokens_after=after,
                at_seq=last or 0,
                summary_seq=summary_seq,
            )
            db.add(row)
            await db.commit()
            return row

    async def history(self, session_pk: int) -> list[CompactionRecord]:
        async with self._maker() as db:
            q = select(CompactionRecord).where(
                CompactionRecord.session_id == session_pk
            )
            return list((await db.scalars(q.order_by(CompactionRecord.id))).all())

    async def undo_after_rewind(self, session_pk: int, cutoff: int) -> int:
        """Un-compact after /rewind passed a compaction; returns records undone.

        View texts are cleared (a stub may point at a rewound Read) and re-applied
        by the next trigger.
        """
        async with self._maker() as db:
            crossed = list(
                (
                    await db.scalars(
                        select(CompactionRecord).where(
                            CompactionRecord.session_id == session_pk,
                            CompactionRecord.at_seq > cutoff,
                            CompactionRecord.undone.is_(False),
                        )
                    )
                ).all()
            )
            if not crossed:
                return 0
            dead = select(Message.seq).where(
                Message.session_id == session_pk,
                Message.role == "summary",
                Message.rewound.is_(True),
            )
            await db.execute(
                update(Message)
                .where(Message.session_id == session_pk)
                .where(Message.compacted_into.in_(dead))
                .values(compacted_into=None)
            )
            await db.execute(
                update(Message)
                .where(Message.session_id == session_pk)
                .where(Message.view_content.is_not(None))
                .values(view_content=None)
            )
            for rec in crossed:
                rec.undone = True
            await db.commit()
            return len(crossed)
