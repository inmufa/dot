"""File-backed memory: one fact per file, a MEMORY.md index, an FTS5 search index."""

import asyncio
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from dot_contracts.memory import MemoryFact, MemoryIn, MemoryKind, MemoryUpdate
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.memory.models import MemoryFactRow
from backend.memory.services import factfile
from backend.memory.services.embedder import Embedder

logger = logging.getLogger(__name__)
NOT_FOUND = 2021
INVALID = 2022
INDEX_FILE = "MEMORY.md"
MAX_FACTS = 2000
_SLUG = re.compile(r"[^a-z0-9]+")
_WORD = re.compile(r"\w+", re.UNICODE)


def slugify(name: str) -> str:
    return _SLUG.sub("-", name.lower()).strip("-")[:40] or "fact"


def fts_query(q: str) -> str | None:
    """Safe FTS5 MATCH expression: quoted prefix terms joined by OR."""
    words = _WORD.findall(q)[:12]
    return " OR ".join(f'"{w}"*' for w in words) or None


def _fact(row: MemoryFactRow) -> MemoryFact:
    return MemoryFact(
        id=row.public_id,
        name=row.name,
        description=row.description,
        kind=MemoryKind(row.kind),
        body=row.body,
        updated_at=row.updated_at,
    )


class MemoryService:
    def __init__(
        self,
        maker: async_sessionmaker,
        directory: Path,
        embedder: Embedder | None = None,
    ) -> None:
        self._maker = maker
        self._dir = directory.expanduser()
        self._embedder = embedder  # reserved: vector search is off by default
        self._lock = asyncio.Lock()
        # Bumped by every write: the prompt suffix refreshes at the next turn.
        self.version = 0

    @property
    def directory(self) -> Path:
        return self._dir

    # -- reads ---------------------------------------------------------------
    async def get(self, fact_id: str) -> MemoryFact:
        async with self._maker() as db:
            return _fact(await self._row(db, fact_id))

    async def list_facts(self, limit: int = 200) -> list[MemoryFact]:
        async with self._maker() as db:
            q = select(MemoryFactRow).order_by(MemoryFactRow.name).limit(limit)
            return [_fact(r) for r in (await db.scalars(q)).all()]

    async def search(self, query: str, limit: int = 10) -> list[MemoryFact]:
        match = fts_query(query)
        if match is None:
            return []
        sql = text(
            "SELECT rowid FROM memory_fts WHERE memory_fts MATCH :m "
            "ORDER BY bm25(memory_fts) LIMIT :n"
        )
        async with self._maker() as db:
            ids = [r[0] for r in await db.execute(sql, {"m": match, "n": limit})]
            if not ids:
                return []
            rows = (
                await db.scalars(select(MemoryFactRow).where(MemoryFactRow.id.in_(ids)))
            ).all()
        order = {i: n for n, i in enumerate(ids)}
        return [_fact(r) for r in sorted(rows, key=lambda r: order[r.id])]

    async def index_text(self, max_lines: int = 200) -> str:
        """First `max_lines` lines of MEMORY.md (what the prompt suffix carries)."""
        try:
            raw = (self._dir / INDEX_FILE).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return "\n".join(raw.splitlines()[:max_lines])

    # -- writes --------------------------------------------------------------
    async def add(self, data: MemoryIn) -> MemoryFact:
        async with self._lock, self._maker() as db:
            count = len((await db.scalars(select(MemoryFactRow.id))).all())
            if count >= MAX_FACTS:
                raise DomainException(INVALID)
            name = factfile.one_line(data.name)
            if not name or not data.body.strip():
                raise DomainException(INVALID)
            row = MemoryFactRow(
                public_id=new_public_id("M"),
                name=name,
                description=factfile.one_line(data.description),
                kind=data.kind.value,
                body=data.body.strip(),
                filename=self._free_name(slugify(data.name)),
                updated_at=datetime.now(UTC),
            )
            db.add(row)
            await db.flush()
            await self._write(db, row, new=True)
            return _fact(row)

    async def update(self, fact_id: str, patch: MemoryUpdate) -> MemoryFact:
        async with self._lock, self._maker() as db:
            row = await self._row(db, fact_id)
            for key, value in patch.model_dump(exclude_none=True).items():
                setattr(row, key, value.value if key == "kind" else value)
            row.name = factfile.one_line(row.name)
            row.description = factfile.one_line(row.description)
            row.body = row.body.strip()
            if not row.name or not row.body:
                await db.rollback()
                raise DomainException(INVALID)
            row.updated_at = datetime.now(UTC)
            await self._write(db, row, new=False)
            return _fact(row)

    async def delete(self, fact_id: str) -> None:
        async with self._lock, self._maker() as db:
            row = await self._row(db, fact_id)
            (self._dir / row.filename).unlink(missing_ok=True)
            await db.execute(
                text("DELETE FROM memory_fts WHERE rowid=:i"), {"i": row.id}
            )
            await db.delete(row)
            await db.flush()
            await self._write_index(db)
            await db.commit()
            self.version += 1

    async def reindex(self) -> int:
        """Rebuild the database index from the files (hand edits, first start)."""
        async with self._lock, self._maker() as db:
            await db.execute(text("DELETE FROM memory_fts"))
            await db.execute(text("DELETE FROM memory_facts"))
            count = 0
            for path in sorted(self._dir.glob("*.md")) if self._dir.is_dir() else []:
                if path.name == INDEX_FILE:
                    continue
                parsed = self._read(path)
                if parsed is None:
                    logger.warning("memory: skipped unreadable file %s", path.name)
                    continue
                row = MemoryFactRow(
                    public_id=parsed.id or new_public_id("M"),
                    name=parsed.name[:80],
                    description=parsed.description[:200],
                    kind=parsed.kind if parsed.kind in MemoryKind else "project",
                    body=parsed.body,
                    filename=path.name,
                    updated_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
                )
                db.add(row)
                await db.flush()
                await self._fts_put(db, row)
                if not parsed.id:
                    self._write_file(row)
                count += 1
            await self._write_index(db)
            await db.commit()
            self.version += 1
            return count

    # -- internals -----------------------------------------------------------
    @staticmethod
    async def _row(db: AsyncSession, fact_id: str) -> MemoryFactRow:
        row = await db.scalar(
            select(MemoryFactRow).where(MemoryFactRow.public_id == fact_id)
        )
        if row is None:
            raise DomainException(NOT_FOUND)
        return row

    def _free_name(self, slug: str) -> str:
        n, name = 1, f"{slug}.md"
        while (self._dir / name).exists():
            n += 1
            name = f"{slug}-{n}.md"
        return name

    @staticmethod
    def _read(path: Path) -> factfile.FactFile | None:
        try:
            return factfile.parse(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return None

    def _write_file(self, row: MemoryFactRow) -> None:
        self._atomic(
            self._dir / row.filename,
            factfile.render(
                factfile.FactFile(
                    row.public_id, row.name, row.description, row.kind, row.body
                )
            ),
        )

    def _atomic(self, path: Path, content: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)

    async def _write(self, db: AsyncSession, row: MemoryFactRow, *, new: bool) -> None:
        self._write_file(row)
        if not new:
            await db.execute(
                text("DELETE FROM memory_fts WHERE rowid=:i"), {"i": row.id}
            )
        await self._fts_put(db, row)
        await db.flush()
        await self._write_index(db)
        await db.commit()
        self.version += 1

    @staticmethod
    async def _fts_put(db: AsyncSession, row: MemoryFactRow) -> None:
        await db.execute(
            text(
                "INSERT INTO memory_fts(rowid, name, description, body) "
                "VALUES (:i, :n, :d, :b)"
            ),
            {"i": row.id, "n": row.name, "d": row.description, "b": row.body},
        )

    async def _write_index(self, db: AsyncSession) -> None:
        rows = (
            await db.scalars(select(MemoryFactRow).order_by(MemoryFactRow.name))
        ).all()
        lines = [
            f"- [{r.name}]({r.filename})"
            + (f" - {r.description}" if r.description else "")
            for r in rows
        ]
        self._atomic(self._dir / INDEX_FILE, "\n".join(lines) + ("\n" if lines else ""))
