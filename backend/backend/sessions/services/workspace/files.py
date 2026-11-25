"""Session file list, previews and the workspace tree (read-only, via the sandbox)."""

import mimetypes
from datetime import UTC, datetime
from typing import Any

from dot_contracts.ui.files import FileInfo, TreeEntry
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.exceptions import DomainException
from backend.routing.clients.sandbox_client import SandboxClient
from backend.sessions.services.transcript import TranscriptStore
from backend.sessions.services.workspace.attachments import AttachmentService

NOT_FOUND, TOO_LARGE, OUTSIDE = 4110, 4111, 4112
_WRITERS = {"Write": "created", "Edit": "modified"}
_RECENT_LIMIT = 200


def _when(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, UTC)


def mime_of(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


class FilesService:
    def __init__(
        self,
        maker: async_sessionmaker,
        store: TranscriptStore,
        sandbox: SandboxClient,
        attachments: AttachmentService,
        workspace: str,
        preview_max_bytes: int,
    ) -> None:
        self._maker = maker
        self._store = store
        self._sandbox = sandbox
        self._attachments = attachments
        self._root = workspace.rstrip("/")
        self.preview_max = preview_max_bytes

    def _abs(self, path: str) -> str:
        return path if path.startswith("/") else f"{self._root}/{path}"

    async def _written(self, pk: int) -> dict[str, tuple[str, int]]:
        """path -> (origin, seq) for the last Write/Edit of each file."""
        out: dict[str, tuple[str, int]] = {}
        for row in await self._store.load(pk, include_compacted=True):
            for call in row.tool_calls or []:
                fn = call.get("function", {})
                origin = _WRITERS.get(fn.get("name", ""))
                args = _args(fn.get("arguments"))
                path = args.get("file_path")
                if origin and isinstance(path, str):
                    prev = out.get(self._abs(path))
                    out[self._abs(path)] = (
                        "created" if prev and prev[0] == "created" else origin,
                        row.seq,
                    )
        return out

    async def _stat(self, sid: str, paths: list[str]) -> list[dict[str, Any]]:
        if not paths:
            return []
        resp = await self._sandbox.post(sid, "/internal/stat", {"paths": paths})
        return resp.data.get("entries", []) if resp.ok else []

    async def session_files(
        self, sid: str, pk: int, created_at: datetime
    ) -> list[FileInfo]:
        written = await self._written(pk)
        found: dict[str, FileInfo] = {}
        for e in await self._stat(sid, list(written)):
            origin, seq = written[e["path"]]
            found[e["path"]] = _info(e, origin, seq)
        resp = await self._sandbox.post(
            sid,
            "/internal/recent",
            {"since": created_at.timestamp(), "limit": _RECENT_LIMIT},
        )
        uploads = f"{self._root}/uploads/"
        for e in resp.data.get("entries", []) if resp.ok else []:
            if e["path"] not in found and not e["path"].startswith(uploads):
                found[e["path"]] = _info(e, "created", None)
        for att in await self._attachments.list(sid):
            found[att.path] = FileInfo(
                path=att.path,
                name=att.name,
                size=att.size,
                mime=att.mime,
                origin="upload",
                modified_at=att.created_at,
            )
        return sorted(found.values(), key=lambda f: f.modified_at, reverse=True)

    async def content(self, sid: str, path: str) -> tuple[bytes, str]:
        resp, data = await self._sandbox.get_raw(sid, self._abs(path), self.preview_max)
        if resp.ok:
            return data, self._abs(path)
        raise DomainException(
            {404: NOT_FOUND, 413: TOO_LARGE, 403: OUTSIDE}.get(resp.status, NOT_FOUND)
        )

    async def tree(self, sid: str, path: str | None, depth: int) -> list[TreeEntry]:
        body = {"path": self._abs(path) if path else None, "depth": depth}
        resp = await self._sandbox.post(sid, "/internal/tree", body)
        if not resp.ok:
            raise DomainException(OUTSIDE if resp.status == 403 else NOT_FOUND)  # noqa: PLR2004
        return [
            TreeEntry(
                path=e["path"],
                name=e["name"],
                type=e["type"],
                size=e["size"],
                modified_at=_when(e["modified"]),
            )
            for e in resp.data.get("entries", [])
        ]


def _args(raw: Any) -> dict[str, Any]:
    import json  # noqa: PLC0415

    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _info(e: dict[str, Any], origin: str, seq: int | None) -> FileInfo:
    return FileInfo(
        path=e["path"],
        name=e["name"],
        size=e["size"] or 0,
        mime=mime_of(e["name"]),
        origin=origin,  # type: ignore[arg-type]
        modified_at=_when(e["modified"]),
        seq=seq,
    )
