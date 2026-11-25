"""FTS5 index over session titles (seq 0) and user/assistant message text."""

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

SQL_CREATE = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS session_fts USING fts5("
    "body, session_pk UNINDEXED, seq UNINDEXED, "
    "tokenize='unicode61 remove_diacritics 2')"
)
INDEXED_ROLES = ("user", "assistant")
_WORD = re.compile(r"\w+", re.UNICODE)
MAX_TERMS = 8
_SNIPPET = "snippet(session_fts, 0, '', '', '...', 12)"


async def ensure(conn: AsyncConnection) -> None:
    await conn.execute(text(SQL_CREATE))


def match_query(q: str) -> str | None:
    """Every word quoted as a prefix term, ANDed; operators and quotes are inert."""
    terms = _WORD.findall(q)[:MAX_TERMS]
    if not terms:
        return None
    return " ".join(f'"{t}"*' for t in terms)


async def index_message(
    db: AsyncSession, session_pk: int, seq: int, role: str, content: str
) -> None:
    if role in INDEXED_ROLES and content.strip():
        await db.execute(
            text("INSERT INTO session_fts(body, session_pk, seq) VALUES (:b, :s, :q)"),
            {"b": content, "s": session_pk, "q": seq},
        )


async def set_title(db: AsyncSession, session_pk: int, title: str | None) -> None:
    await db.execute(
        text("DELETE FROM session_fts WHERE session_pk = :s AND seq = 0"),
        {"s": session_pk},
    )
    if title:
        await db.execute(
            text("INSERT INTO session_fts(body, session_pk, seq) VALUES (:b, :s, 0)"),
            {"b": title, "s": session_pk},
        )


async def delete_session(db: AsyncSession, session_pk: int) -> None:
    await db.execute(
        text("DELETE FROM session_fts WHERE session_pk = :s"), {"s": session_pk}
    )


async def search(db: AsyncSession, q: str, limit: int = 200) -> list[tuple[int, str]]:
    """(session_pk, snippet) per matching session, best match first."""
    query = match_query(q)
    if query is None:
        return []
    rows = await db.execute(
        text(
            f"SELECT session_pk, {_SNIPPET}, bm25(session_fts) AS r "  # noqa: S608
            "FROM session_fts WHERE session_fts MATCH :q "
            "AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.rewound = 1 "
            "AND m.session_id = session_fts.session_pk AND m.seq = session_fts.seq) "
            "ORDER BY r LIMIT :n"
        ),
        {"q": query, "n": limit * 4},
    )
    seen: dict[int, str] = {}
    for pk, snippet, _ in rows:
        seen.setdefault(int(pk), str(snippet))
    return list(seen.items())[:limit]


async def rebuild_if_empty(maker: async_sessionmaker) -> None:
    """Index existing sessions once (databases from before the index existed)."""
    async with maker() as db:
        if (await db.scalar(text("SELECT count(*) FROM session_fts"))) or 0:
            return
        await db.execute(
            text(
                "INSERT INTO session_fts(body, session_pk, seq) "
                "SELECT title, id, 0 FROM sessions WHERE title IS NOT NULL"
            )
        )
        await db.execute(
            text(
                "INSERT INTO session_fts(body, session_pk, seq) "
                "SELECT content, session_id, seq FROM messages "
                "WHERE role IN ('user', 'assistant') AND content != ''"
            )
        )
        await db.commit()
