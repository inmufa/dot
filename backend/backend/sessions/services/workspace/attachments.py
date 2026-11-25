"""Attachment storage: validate, write through the sandbox, extract document text."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dot_contracts.ui.files import Attachment
from sqlalchemy import select

from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.sessions.services.workspace.models import AttachmentRow
from backend.sessions.services.workspace.sniff import Sniffed, clean_name, sniff

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from backend.routing.clients.sandbox_client import SandboxClient

logger = logging.getLogger(__name__)
TOO_LARGE, TOO_MANY, NOT_FOUND, UNREADABLE = 4100, 4102, 4103, 4105
_DOC_KINDS = {"pdf", "docx", "xlsx"}
EXTRACT_STORE = 200_000


@dataclass
class Upload:
    name: str
    data: bytes


def to_dto(row: AttachmentRow) -> Attachment:
    return Attachment(
        id=row.public_id,
        session_id=row.session_id,
        name=row.name,
        mime=row.mime,
        size=row.size,
        kind=row.kind,  # type: ignore[arg-type]
        path=row.path,
        pages=row.pages,
        extracted_chars=row.extracted_chars,
        width=row.width,
        height=row.height,
        created_at=row.created_at,
    )


class AttachmentService:
    def __init__(
        self,
        maker: async_sessionmaker,
        sandbox: SandboxClient,
        workspace: str,
        *,
        max_files: int,
        max_bytes: int,
    ) -> None:
        self._maker = maker
        self._sandbox = sandbox
        self._root = workspace.rstrip("/")
        self.max_files = max_files
        self.max_bytes = max_bytes

    async def save(self, session_id: str, uploads: list[Upload]) -> list[AttachmentRow]:
        """All-or-nothing: every file is checked before the first one is written."""
        if len(uploads) > self.max_files:
            raise DomainException(TOO_MANY)
        checked: list[tuple[str, Sniffed, bytes]] = []
        for up in uploads:
            if len(up.data) > self.max_bytes:
                raise DomainException(TOO_LARGE)
            name = clean_name(up.name)
            checked.append((name, sniff(name, up.data), up.data))
        taken = {r.name for r in await self.list(session_id)}
        written: list[AttachmentRow] = []
        try:
            for name, info, data in checked:
                name = _unique(name, taken)  # noqa: PLW2901
                taken.add(name)
                written.append(await self._store(session_id, name, info, data))
        except BaseException:
            for row in written:
                await self._unlink(session_id, row)
            raise
        async with self._maker() as db:
            db.add_all(written)
            await db.commit()
        return written

    async def _put(self, session_id: str, path: str, data: bytes) -> None:
        resp = await self._sandbox.put_bytes(session_id, path, data)
        if not resp.ok:
            logger.warning("upload write failed: %s", resp.error_text())
            raise DomainException(TOO_LARGE if resp.status == 413 else UNREADABLE)  # noqa: PLR2004

    async def _store(
        self, session_id: str, name: str, info: Sniffed, data: bytes
    ) -> AttachmentRow:
        pid = new_public_id("A")
        path = f"{self._root}/uploads/{session_id}/{pid}-{name}"
        await self._put(session_id, path, data)
        row = AttachmentRow(
            public_id=pid,
            session_id=session_id,
            name=name,
            mime=info.mime,
            size=len(data),
            kind=info.kind,
            path=path,
            width=info.width,
            height=info.height,
        )
        if info.kind in ("text", "data") and info.ext not in _DOC_KINDS:
            row.extracted = data[:EXTRACT_STORE].decode("utf-8", errors="replace")
        if info.ext in _DOC_KINDS:
            try:
                await self._extract(session_id, row, info.ext)
            except BaseException:
                await self._unlink(session_id, row)
                raise
        return row

    async def _extract(self, session_id: str, row: AttachmentRow, kind: str) -> None:
        resp = await self._sandbox.post(
            session_id, "/internal/extract", {"path": row.path, "kind": kind}
        )
        if not resp.ok:
            raise DomainException(UNREADABLE)
        text = str(resp.data.get("text", ""))
        row.pages = resp.data.get("pages") if kind == "pdf" else row.pages
        row.extracted_chars = len(text)
        row.extracted = text[:EXTRACT_STORE]
        row.text_path = f"{row.path}.txt"
        await self._put(session_id, row.text_path, text.encode())

    async def _unlink(self, session_id: str, row: AttachmentRow) -> None:
        for path in (row.path, row.text_path):
            if path:
                await self._sandbox.post(
                    session_id, "/internal/delete_upload", {"path": path}
                )

    async def list(self, session_id: str) -> list[AttachmentRow]:
        async with self._maker() as db:
            q = select(AttachmentRow).where(AttachmentRow.session_id == session_id)
            return list((await db.scalars(q.order_by(AttachmentRow.id))).all())

    async def get(self, public_id: str) -> AttachmentRow:
        async with self._maker() as db:
            row = await db.scalar(
                select(AttachmentRow).where(AttachmentRow.public_id == public_id)
            )
        if row is None:
            raise DomainException(NOT_FOUND)
        return row

    async def resolve(self, session_id: str, ids: list[str]) -> list[AttachmentRow]:
        """Rows for ids that belong to this session, in order; 4103 for any other."""
        rows = []
        for pid in dict.fromkeys(ids):
            row = await self.get(pid)
            if row.session_id != session_id:
                raise DomainException(NOT_FOUND)
            rows.append(row)
        return rows

    async def content(self, row: AttachmentRow) -> bytes:
        resp, data = await self._sandbox.get_raw(
            row.session_id, row.path, self.max_bytes
        )
        if not resp.ok:
            raise DomainException(NOT_FOUND)
        return data

    async def delete(self, public_id: str) -> None:
        row = await self.get(public_id)
        await self._unlink(row.session_id, row)
        async with self._maker() as db:
            await db.delete(await db.get(AttachmentRow, row.id))
            await db.commit()


def _unique(name: str, taken: set[str]) -> str:
    if name not in taken:
        return name
    stem, dot, ext = name.rpartition(".")
    stem, dot = (stem, dot) if dot else (name, "")
    n = 2
    while f"{stem} ({n}){dot}{ext}" in taken:
        n += 1
    return f"{stem} ({n}){dot}{ext}"
