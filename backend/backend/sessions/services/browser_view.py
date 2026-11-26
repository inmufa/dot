"""Owner view of the shared browser page: frames, state and manual input.

Nothing here reaches the transcript or model context. Owner input is rejected
(4017) while an agent browser call is in flight.
"""

from typing import Any

import httpx
from fastapi import Request

from backend.cognition.services.tools.web.browser_client import (
    BROWSER_FAILED,
    BrowserClient,
)
from backend.core.api.ratelimit import RATE_LIMITED, TokenBucket
from backend.core.exceptions import DomainException
from backend.governance.services.audit import AuditService

BROWSER_BUSY = 4017
URL_BLOCKED = 4018
PAGE_FAILED = 4019
_ACTION_PATHS = {
    "navigate": "/nav",
    "back": "/view/back",
    "forward": "/view/forward",
    "reload": "/view/reload",
    "click": "/view/click",
    "type": "/view/type",
    "press": "/press",
    "scroll": "/view/wheel",
    "tab_new": "/tabs/new",
    "tab_switch": "/tabs/switch",
    "tab_close": "/close",
    "viewport": "/view/viewport",
}
_NAV_KINDS = {"navigate", "tab_new"}
_LOAD_KINDS = {"navigate", "tab_new", "back", "forward", "reload"}
_LOAD_FAILS = {"timeout", "action_failed"}
# Owner navigation returns once the server answers; the view polls while it paints.
_OWNER_WAIT = "commit"
_QUIET = {"scroll", "viewport"}  # too chatty for the audit log
_MAX_CLIENTS = 64


class BrowserView:
    def __init__(self, client: BrowserClient, audit: AuditService) -> None:
        self._b = client
        self._audit = audit
        self._buckets: dict[str, TokenBucket] = {}
        self.vault: Any = (
            None  # VaultAgent: restores saved sessions on owner navigation
        )

    def limit(self, request: Request, kind: str) -> None:
        """Token bucket per client and kind ('view' polling or 'input')."""
        cfg = request.app.state.settings
        rate, burst = (
            (cfg.browser_view_rate_per_min, cfg.browser_view_burst)
            if kind == "view"
            else (cfg.browser_input_rate_per_min, cfg.browser_input_burst)
        )
        bucket = self._buckets.setdefault(kind, TokenBucket(rate, burst))
        key = request.client.host if request.client else "-"
        wait = bucket.take(key)
        if wait:
            raise DomainException(RATE_LIMITED, retry_after=max(1, int(wait) + 1))

    def _agent(self, sid: str) -> dict[str, Any]:
        return {
            "agent_acting": self._b.acting.get(sid, 0) > 0,
            "agent_seq": self._b.agent_seq.get(sid, 0),
        }

    def _fail(self, r: httpx.Response, kind: str = "") -> DomainException:
        code, detail = self._b.worker_error(r)
        if code == "ssrf_blocked":
            return DomainException(URL_BLOCKED, {"detail": detail})
        if kind in _LOAD_KINDS and code in _LOAD_FAILS:
            return DomainException(PAGE_FAILED, {"detail": f"{code}: {detail}"})
        return DomainException(BROWSER_FAILED, {"detail": f"{code}: {detail}"})

    async def state(self, sid: str) -> dict[str, Any]:
        r = await self._b.send("GET", sid, "/view/state")
        if r.status_code >= 400:  # noqa: PLR2004
            raise self._fail(r)
        return {**r.json(), **self._agent(sid)}

    async def frame(self, sid: str, tab: str | None) -> bytes | None:
        body = {"tab": tab} if tab else {}
        r = await self._b.send("POST", sid, "/view/frame", body)
        if r.status_code == 204:  # noqa: PLR2004
            return None
        if r.status_code >= 400:  # noqa: PLR2004
            raise self._fail(r)
        return r.content

    async def act(
        self, sid: str, kind: str, body: dict[str, Any], note: dict[str, Any]
    ) -> dict[str, Any]:
        """Run one owner action; `note` is what the audit entry may record."""
        if self._b.acting.get(sid):
            raise DomainException(BROWSER_BUSY)
        if kind not in _QUIET:
            await self._audit.append(
                session=sid,
                mode="-",
                tool=f"BrowserView.{kind}",
                args=note,
                decision="allow",
                source="user",
            )
        if self.vault is not None and body.get("url") and kind in _NAV_KINDS:
            await self.vault.restore_on_navigate(sid, str(body["url"]), owner=True)
        if kind in _NAV_KINDS and body.get("url"):
            body = {**body, "wait_until": _OWNER_WAIT}
        r = await self._b.send("POST", sid, _ACTION_PATHS[kind], body)
        if r.status_code >= 400:  # noqa: PLR2004
            raise self._fail(r, kind)
        out = r.json()
        if kind == "tab_close":
            return await self.state(sid)
        return {**(await self.state(sid)), "status": out.get("status")}
