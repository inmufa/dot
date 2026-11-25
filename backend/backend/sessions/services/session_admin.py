"""Session management: list/search, patch, delete, activity stats."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from dot_contracts.sessions import SessionPatch
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.models import Task
from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.sessions.models import Message, Session
from backend.sessions.services.search import fts
from backend.sessions.services.session_service import SESSION_NOT_FOUND, TITLE_MAX

MAX_LIMIT = 200


@dataclass
class Activity:
    last_message_at: datetime | None = None
    count: int = 0


class SessionAdmin:
    def __init__(self, maker: async_sessionmaker) -> None:
        self._maker = maker

    async def activity(self, pks: list[int]) -> dict[int, Activity]:
        async with self._maker() as db:
            q = (
                select(Message.session_id, func.max(Message.created_at), func.count())
                .where(
                    Message.session_id.in_(pks),
                    Message.rewound.is_(False),
                    Message.compacted_into.is_(None),
                    Message.role != "summary",
                )
                .group_by(Message.session_id)
            )
            rows = (await db.execute(q)).all()
        return {pk: Activity(last, n) for pk, last, n in rows}

    async def find(
        self,
        *,
        q: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
        project: str | None = None,
        limit: int = 50,
        before: str | None = None,
    ) -> tuple[list[Session], dict[int, str]]:
        """Rows plus search snippets (by pk). Archived hidden unless asked."""
        limit = max(1, min(limit, MAX_LIMIT))
        hits: dict[int, str] = {}
        async with self._maker() as db:
            stmt = select(Session)
            if q and q.strip():
                found = await fts.search(db, q)
                hits = dict(found)
                stmt = stmt.where(Session.id.in_(list(hits)))
            stmt = stmt.where(Session.archived.is_(bool(archived)))
            if pinned is not None:
                stmt = stmt.where(Session.pinned.is_(pinned))
            if project:
                stmt = stmt.where(Session.project == project)
            rows = list((await db.scalars(stmt)).all())
        act = await self.activity([r.id for r in rows])
        epoch = datetime.min.replace(tzinfo=UTC)

        def recent(r: Session) -> datetime:
            when = act[r.id].last_message_at if r.id in act else None
            when = when or r.created_at
            return when if when.tzinfo else when.replace(tzinfo=UTC)

        if hits:
            order = {pk: i for i, pk in enumerate(hits)}
            rows.sort(key=lambda r: order[r.id])
        else:
            rows.sort(key=lambda r: (recent(r) or epoch, r.id), reverse=True)
        if before:
            ids = [r.public_id for r in rows]
            if before in ids:
                rows = rows[ids.index(before) + 1 :]
        return rows[:limit], hits

    async def create(self, mode: str, *, project: str | None, effort: str) -> Session:
        async with self._maker() as db:
            row = Session(
                public_id=new_public_id("S"),
                mode=mode,
                project=project,
                effort=effort,
            )
            db.add(row)
            await db.commit()
            return row

    async def patch(self, public_id: str, body: SessionPatch) -> Session:
        async with self._maker() as db:
            row = await db.scalar(select(Session).where(Session.public_id == public_id))
            if row is None:
                raise DomainException(SESSION_NOT_FOUND)
            if body.title is not None:
                row.title = " ".join(body.title.split())[:TITLE_MAX] or None
                await fts.set_title(db, row.id, row.title)
            if body.pinned is not None:
                row.pinned = body.pinned
            if body.archived is not None:
                row.archived = body.archived
            if body.project is not None:
                row.project = body.project or None
            if body.effort is not None:
                row.effort = body.effort.value
            await db.commit()
            return row

    async def purge_empty(self, older_than: timedelta) -> int:
        """Drop chats that never got a message (the title is set with the first one)."""
        cutoff = datetime.now(UTC) - older_than
        has_message = (
            select(Message.id).where(Message.session_id == Session.id).exists()
        )
        async with self._maker() as db:
            rows = (
                await db.scalars(
                    select(Session).where(
                        Session.title.is_(None),
                        ~has_message,
                        Session.created_at < cutoff,
                    )
                )
            ).all()
            for row in rows:
                await fts.delete_session(db, row.id)
                await db.execute(delete(Task).where(Task.session_id == row.public_id))
                await db.execute(delete(Session).where(Session.id == row.id))
            await db.commit()
            return len(rows)

    async def delete(self, row: Session) -> None:
        """Hard delete: messages, checkpoints and compactions cascade; files stay."""
        async with self._maker() as db:
            await fts.delete_session(db, row.id)
            await db.execute(delete(Task).where(Task.session_id == row.public_id))
            await db.execute(delete(Session).where(Session.id == row.id))
            await db.commit()
