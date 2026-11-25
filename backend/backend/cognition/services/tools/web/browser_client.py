"""HTTP client for the browser worker (X-Browser-Token, X-Session-Id)."""

import logging
from typing import Any

import httpx

from backend.core.exceptions import DomainException

logger = logging.getLogger(__name__)
BROWSER_UNAVAILABLE = 4015
BROWSER_FAILED = 4016


class BrowserClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        # Agent actions in flight and a counter bumped after each, per session.
        self.acting: dict[str, int] = {}
        self.agent_seq: dict[str, int] = {}
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=3.0), trust_env=False
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send(
        self,
        method: str,
        session_id: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """One worker call; transport failures raise 4015 (down) or 4016 (timeout)."""
        headers = {"X-Session-Id": session_id}
        if self._token:
            headers["X-Browser-Token"] = self._token
        try:
            return await self._client.request(
                method, f"{self._base}{path}", json=payload, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise DomainException(BROWSER_FAILED, {"detail": "timed out"}) from exc
        except httpx.HTTPError as exc:
            logger.warning("browser transport error: %s", type(exc).__name__)
            raise DomainException(BROWSER_UNAVAILABLE) from exc

    @staticmethod
    def worker_error(r: httpx.Response) -> tuple[str, str]:
        try:
            data = r.json()
        except ValueError:
            data = {}
        data = data if isinstance(data, dict) else {}
        return str(data.get("error", f"http_{r.status_code}")), str(
            data.get("detail", "")
        )

    async def post(
        self, session_id: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Agent action. Marks the session busy so owner input is rejected meanwhile."""
        self.acting[session_id] = self.acting.get(session_id, 0) + 1
        try:
            r = await self.send("POST", session_id, path, payload)
        finally:
            self.acting[session_id] -= 1
            if not self.acting[session_id]:
                del self.acting[session_id]
            self.agent_seq[session_id] = self.agent_seq.get(session_id, 0) + 1
        try:
            data = r.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if r.status_code >= 400:  # noqa: PLR2004
            code, detail = self.worker_error(r)
            raise DomainException(BROWSER_FAILED, {"detail": f"{code}: {detail}"})
        return data
