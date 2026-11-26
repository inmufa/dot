"""Inline chat images: remote URLs (SSRF-safe) and workspace files, as raw bytes."""

import posixpath
from dataclasses import dataclass

from backend.cognition.services.tools.web.fetch_http import (
    FETCH_BLOCKED,
    FETCH_UNSUPPORTED,
    IMAGE_MAX_BYTES,
    IMAGE_POLICY,
    SafeFetcher,
)
from backend.core.exceptions import DomainException
from backend.routing.clients.sandbox_client import SandboxClient

BAD_SOURCE, NOT_IMAGE, TOO_BIG, MISSING = 4020, 4021, 4022, 4023
_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
    "svg": "image/svg+xml",
}
_AVIF_BRANDS = (b"avif", b"avis")


@dataclass(frozen=True)
class Media:
    data: bytes
    mime: str


def sniff(data: bytes) -> str | None:
    """Image type from magic bytes, or None."""
    head = data[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp" and head[8:12] in _AVIF_BRANDS:
        return "image/avif"
    text = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text.startswith((b"<svg", b"<?xml")) and b"<svg" in text:
        return "image/svg+xml"
    return None


def _dotted(parts: list[str]) -> bool:
    return any(p.startswith(".") for p in parts)


def _ext(path: str) -> str:
    return posixpath.splitext(path)[1].lower().lstrip(".")


class MediaService:
    def __init__(self, sandbox: SandboxClient, workspace: str, fetcher: SafeFetcher):
        self._sandbox = sandbox
        self._root = posixpath.normpath(workspace)
        self._fetcher = fetcher

    async def load(self, sid: str, src: str) -> Media:
        src = src.strip()
        if "\x00" in src or not src:
            raise DomainException(BAD_SOURCE)
        if src.lower().startswith(("http://", "https://")):
            return await self._remote(src)
        return await self._local(sid, src)

    async def _remote(self, url: str) -> Media:
        try:
            page = await self._fetcher.get(url, IMAGE_POLICY)
        except DomainException as exc:
            if exc.code == FETCH_BLOCKED:
                raise DomainException(BAD_SOURCE) from exc
            if exc.code == FETCH_UNSUPPORTED:
                too_big = "too large" in str(exc.ctx.get("detail", ""))
                raise DomainException(TOO_BIG if too_big else NOT_IMAGE) from exc
            raise DomainException(MISSING) from exc
        mime = sniff(page.body)
        if mime is None or mime != page.content_type:
            raise DomainException(NOT_IMAGE)
        return Media(page.body, mime)

    def _rel(self, path: str, root: str) -> list[str]:
        """Path parts below `root`; rejects anything outside it or dotted."""
        if not (path == root or path.startswith(root.rstrip("/") + "/")):
            raise DomainException(BAD_SOURCE)
        parts = [p for p in path[len(root) :].split("/") if p]
        if _dotted(parts):
            raise DomainException(BAD_SOURCE)
        return parts

    async def _real(self, sid: str, path: str) -> str:
        resp = await self._sandbox.post(sid, "/internal/realpath", {"path": path})
        real = resp.data.get("path")
        if not resp.ok or not isinstance(real, str):
            raise DomainException(MISSING)
        if resp.data.get("inside") is not True:
            raise DomainException(BAD_SOURCE)
        return real

    async def _local(self, sid: str, src: str) -> Media:
        path = posixpath.normpath(
            src if src.startswith("/") else f"{self._root}/{src}"
        )
        if not self._rel(path, self._root) or _ext(path) not in _EXT:
            raise DomainException(BAD_SOURCE if _ext(path) in _EXT else NOT_IMAGE)
        real = await self._real(sid, path)
        real_root = await self._real(sid, self._root)
        self._rel(real, real_root)
        if _ext(real) not in _EXT:
            raise DomainException(NOT_IMAGE)
        resp, data = await self._sandbox.get_raw(sid, real, IMAGE_MAX_BYTES)
        if not resp.ok:
            raise DomainException(
                {404: MISSING, 413: TOO_BIG, 403: BAD_SOURCE}.get(resp.status, MISSING)
            )
        mime = sniff(data)
        if mime is None or mime != _EXT[_ext(real)]:
            raise DomainException(NOT_IMAGE)
        return Media(data, mime)
