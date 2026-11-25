from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.sessions.models import Message, Session
from backend.sessions.services.search import fts

SESSION_NOT_FOUND = 2000
TITLE_MAX = 60


class SessionService:
    def __init__(self, maker: async_sessionmaker) -> None:
        self._maker = maker

    async def create(self, mode: str) -> Session:
        async with self._maker() as db:
            row = Session(public_id=new_public_id("S"), mode=mode)
            db.add(row)
            await db.commit()
            return row

    async def get(self, public_id: str) -> Session:
        async with self._maker() as db:
            row = await db.scalar(select(Session).where(Session.public_id == public_id))
        if row is None:
            raise DomainException(SESSION_NOT_FOUND)
        return row

    async def recent(self, limit: int = 50) -> list[Session]:
        async with self._maker() as db:
            q = select(Session).order_by(Session.id.desc()).limit(limit)
            return list((await db.scalars(q)).all())

    async def set_mode(self, public_id: str, mode: str) -> Session:
        async with self._maker() as db:
            row = await db.scalar(select(Session).where(Session.public_id == public_id))
            if row is None:
                raise DomainException(SESSION_NOT_FOUND)
            row.mode = mode
            await db.commit()
            return row

    async def messages(
        self,
        public_id: str,
        *,
        include_rewound: bool = False,
        include_compacted: bool = False,
    ) -> list[Message]:
        row = await self.get(public_id)
        async with self._maker() as db:
            q = select(Message).where(Message.session_id == row.id)
            if not include_rewound:
                q = q.where(Message.rewound.is_(False))
            if not include_compacted:
                q = q.where(Message.compacted_into.is_(None))
            q = q.order_by(Message.seq)
            return list((await db.scalars(q)).all())

    async def set_title_if(
        self, session_pk: int, expected: str | None, title: str
    ) -> None:
        """Replace the title only if it is still `expected` (a rename in between wins)."""
        async with self._maker() as db:
            row = await db.get(Session, session_pk)
            if row is not None and row.title == expected:
                row.title = title
                await fts.set_title(db, session_pk, title)
                await db.commit()

    async def title_from(self, session_pk: int, text: str) -> None:
        """Set the title from the first user message when it is still empty."""
        async with self._maker() as db:
            row = await db.get(Session, session_pk)
            if row is not None and row.title is None:
                row.title = " ".join(text.split())[:TITLE_MAX] or None
                await fts.set_title(db, session_pk, row.title)
                await db.commit()
