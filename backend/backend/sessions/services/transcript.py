"""Append-only message store. History is only ever appended to."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.sessions.models import Message, Session
from backend.sessions.services.compaction.overlay import Overlay
from backend.sessions.services.search import fts
from backend.sessions.services.transcript_tokens import estimate_tokens


class TranscriptStore:
    def __init__(self, maker: async_sessionmaker) -> None:
        self._maker = maker
        self.overlay = Overlay(maker)

    async def append(  # noqa: PLR0913
        self,
        session_pk: int,
        role: str,
        content: str = "",
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        reminder: str | None = None,
        tainted: bool = False,
        reasoning: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Message:
        async with self._maker() as db:
            last = await db.scalar(
                select(func.max(Message.seq)).where(Message.session_id == session_pk)
            )
            row = Message(
                session_id=session_pk,
                seq=(last or 0) + 1,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                reminder=reminder,
                token_count=estimate_tokens(content),
                tainted=tainted,
                reasoning=reasoning or None,
                meta=meta,
            )
            db.add(row)
            await fts.index_message(db, session_pk, row.seq, role, content)
            await db.commit()
            return row

    async def load(
        self, session_pk: int, *, include_compacted: bool = False
    ) -> list[Message]:
        """Rows the model sees: summaries first, then live rows in seq order.

        With `include_compacted` every non-rewound row comes back in seq order.
        """
        async with self._maker() as db:
            q = select(Message).where(
                Message.session_id == session_pk, Message.rewound.is_(False)
            )
            if not include_compacted:
                q = q.where(Message.compacted_into.is_(None))
            rows = list((await db.scalars(q.order_by(Message.seq))).all())
        if include_compacted:
            return rows
        return sorted(rows, key=lambda r: (r.role != "summary", r.seq))

    async def uncompact_after_rewind(self, session_pk: int, cutoff: int) -> int:
        return await self.overlay.undo_after_rewind(session_pk, cutoff)

    async def last_seq(self, session_pk: int) -> int:
        """Highest seq ever used (rewound rows included, seq never repeats)."""
        async with self._maker() as db:
            q = select(func.max(Message.seq)).where(Message.session_id == session_pk)
            return (await db.scalar(q)) or 0

    async def mode_of(self, session_pk: int) -> str:
        async with self._maker() as db:
            row = await db.get(Session, session_pk)
            return row.mode if row else "default"
