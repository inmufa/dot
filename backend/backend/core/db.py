from sqlalchemy import URL, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.settings import Settings


class Base(DeclarativeBase):
    """Declarative base for every domain model."""


def make_engine(settings: Settings) -> AsyncEngine:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        URL.create("sqlite+aiosqlite", database=str(settings.db_path))
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _pragmas(dbapi_conn, _record) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


_MESSAGE_COLUMNS = {
    "rewound": "BOOLEAN DEFAULT 0",
    "compacted_into": "INTEGER",
    "view_content": "TEXT",
    "tainted": "BOOLEAN DEFAULT 0",
    "reasoning": "TEXT",
    "meta": "JSON",
}


async def create_schema(engine: AsyncEngine) -> None:
    """Create missing tables (Alembic replaces this later)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.begin() as conn:
        cols = {r[1] for r in await conn.execute(text("PRAGMA table_info(messages)"))}
        for name, ddl in _MESSAGE_COLUMNS.items():  # dev databases from older builds
            if cols and name not in cols:
                await conn.execute(
                    text(f"ALTER TABLE messages ADD COLUMN {name} {ddl}")
                )
