import os
from pathlib import Path

from sqlalchemy import URL, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.settings import Settings


class Base(DeclarativeBase):
    """Declarative base for every domain model."""


def _make_private(db: Path) -> None:
    """Chats sit in plaintext: owner-only directory and database files (WAL follows)."""
    db.parent.mkdir(parents=True, exist_ok=True)
    try:
        db.parent.chmod(0o700)
        os.close(os.open(db, os.O_CREAT | os.O_RDWR, 0o600))
        for f in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
            if f.exists():
                f.chmod(0o600)
    except PermissionError:  # a directory we do not own (host dev): leave it
        pass


def make_engine(settings: Settings) -> AsyncEngine:
    _make_private(settings.db_path)
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


_SESSION_COLUMNS = {
    "pinned": "BOOLEAN DEFAULT 0",
    "archived": "BOOLEAN DEFAULT 0",
    "project": "VARCHAR(64)",
    "parent_id": "VARCHAR(10)",
    "parent_seq": "INTEGER",
    "effort": "VARCHAR(8) DEFAULT 'medium'",
}


async def _add_columns(conn, table: str, wanted: dict[str, str]) -> None:
    cols = {r[1] for r in await conn.execute(text(f"PRAGMA table_info({table})"))}
    for name, ddl in wanted.items():  # dev databases from older builds
        if cols and name not in cols:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


async def create_schema(engine: AsyncEngine) -> None:
    """Create missing tables (Alembic replaces this later)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.begin() as conn:
        await _add_columns(conn, "messages", _MESSAGE_COLUMNS)
        await _add_columns(conn, "sessions", _SESSION_COLUMNS)
        from backend.sessions.services.search import fts  # noqa: PLC0415

        await fts.ensure(conn)
