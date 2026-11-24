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
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=3.0), trust_env=False
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def post(
        self, session_id: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """POST an action. Worker errors raise 4016 with the worker's detail."""
        headers = {"X-Session-Id": session_id}
        if self._token:
            headers["X-Browser-Token"] = self._token
        try:
            r = await self._client.post(
                f"{self._base}{path}", json=payload, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise DomainException(BROWSER_FAILED, {"detail": "timed out"}) from exc
        except httpx.HTTPError as exc:
            logger.warning("browser transport error: %s", type(exc).__name__)
            raise DomainException(BROWSER_UNAVAILABLE) from exc
        try:
            data = r.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if r.status_code >= 400:  # noqa: PLR2004
            code = data.get("error", f"http_{r.status_code}")
            raise DomainException(
                BROWSER_FAILED, {"detail": f"{code}: {data.get('detail', '')}"}
            )
        return data
