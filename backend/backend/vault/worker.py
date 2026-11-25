"""Calls to the browser worker's /vault routes. Bodies carry secrets: never log them."""

from typing import Any

from backend.cognition.services.tools.web.browser_client import (
    BROWSER_FAILED,
    BrowserClient,
)
from backend.core.exceptions import DomainException

ORIGIN_MISMATCH, UNSAFE_FORM = 4144, 4148
_CODES = {"origin_mismatch": ORIGIN_MISMATCH, "unsafe_form": UNSAFE_FORM}


def _map(code: str, detail: str) -> DomainException:
    if code in _CODES:
        return DomainException(_CODES[code])
    return DomainException(BROWSER_FAILED, {"detail": f"{code}: {detail[:200]}"})


class VaultWorker:
    def __init__(self, browser: BrowserClient) -> None:
        self._b = browser

    async def _call(
        self, sid: str, path: str, body: dict[str, Any], *, acting: bool
    ) -> dict[str, Any] | None:
        """None means the worker has no live context for this session (404)."""
        if acting:
            try:
                return await self._b.post(sid, path, body)
            except DomainException as exc:
                head = str(exc.ctx.get("detail", "")).split(":", 1)
                if head[0] in _CODES:
                    raise _map(head[0], "") from exc
                raise
        r = await self._b.send("POST", sid, path, body)
        if r.status_code == 404:  # noqa: PLR2004
            return None
        if r.status_code >= 400:  # noqa: PLR2004
            raise _map(*self._b.worker_error(r))
        data = r.json()
        return data if isinstance(data, dict) else {}

    async def login(self, sid: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._call(sid, "/vault/login", body, acting=True) or {}

    async def export(self, sid: str, origins: list[str]) -> dict[str, Any] | None:
        return await self._call(
            sid, "/vault/session/export", {"origins": origins}, acting=False
        )

    async def restore(
        self,
        sid: str,
        cred: str,
        origins: list[str],
        state: dict[str, Any],
        url: str | None,
        *,
        acting: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"id": cred, "origins": origins, "state": state}
        if url:
            body["url"] = url
        return (
            await self._call(sid, "/vault/session/restore", body, acting=acting) or {}
        )

    async def restored(self, sid: str, ids: list[str]) -> set[str]:
        got = await self._call(
            sid, "/vault/session/restored", {"ids": ids}, acting=False
        )
        return set((got or {}).get("restored", []))

    async def page_url(self, sid: str) -> str | None:
        r = await self._b.send("GET", sid, "/view/state")
        if r.status_code >= 400:  # noqa: PLR2004
            raise _map(*self._b.worker_error(r))
        data = r.json()
        return data.get("url") if data.get("open") else None
