"""HTTP client for the sandbox runner (internal API, see docs/api-contract.md)."""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from backend.core.exceptions import DomainException

logger = logging.getLogger(__name__)
SANDBOX_UNAVAILABLE = 4001
SANDBOX_TIMEOUT = 4002
_PAD_S = 15.0


@dataclass
class SandboxResponse:
    status: int
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300  # noqa: PLR2004

    def error_text(self) -> str:
        code = self.data.get("error", f"http_{self.status}")
        return f"{code}: {self.data.get('detail', '')}".strip()


class SandboxClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=3.0)
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, session_id: str) -> dict[str, str]:
        headers = {"X-Session-Id": session_id}
        if self._token:
            headers["X-Sandbox-Token"] = self._token
        return headers

    async def health(self) -> bool:
        try:
            r = await self._client.get(f"{self._base}/health", timeout=3.0)
        except httpx.HTTPError:
            return False
        return r.status_code == httpx.codes.OK

    async def post(
        self,
        session_id: str,
        path: str,
        payload: dict[str, Any],
        timeout_s: float | None = None,
    ) -> SandboxResponse:
        """POST to the sandbox. Transport failures raise DomainException."""
        timeout = httpx.Timeout(timeout_s + _PAD_S if timeout_s else 30.0, connect=3.0)
        try:
            r = await self._client.post(
                f"{self._base}{path}",
                json=payload,
                headers=self._headers(session_id),
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise DomainException(SANDBOX_TIMEOUT) from exc
        except httpx.HTTPError as exc:
            logger.warning("sandbox transport error: %s", type(exc).__name__)
            raise DomainException(SANDBOX_UNAVAILABLE) from exc
        try:
            data = r.json()
        except ValueError:
            data = {"error": "bad_response", "detail": r.text[:200]}
        return SandboxResponse(r.status_code, data if isinstance(data, dict) else {})

    async def put_bytes(
        self, session_id: str, path: str, data: bytes
    ) -> SandboxResponse:
        """Raw-body upload to /internal/write_binary (the path must be under uploads/)."""
        try:
            r = await self._client.post(
                f"{self._base}/internal/write_binary",
                params={"path": path},
                content=data,
                headers=self._headers(session_id),
                timeout=httpx.Timeout(120.0, connect=3.0),
            )
        except httpx.TimeoutException as exc:
            raise DomainException(SANDBOX_TIMEOUT) from exc
        except httpx.HTTPError as exc:
            raise DomainException(SANDBOX_UNAVAILABLE) from exc
        return _parse(r)

    async def get_raw(
        self, session_id: str, path: str, max_bytes: int
    ) -> tuple[SandboxResponse, bytes]:
        """Bytes of a workspace file; on error the body is the JSON error."""
        try:
            r = await self._client.get(
                f"{self._base}/internal/raw",
                params={"path": path, "max_bytes": max_bytes},
                headers=self._headers(session_id),
                timeout=httpx.Timeout(60.0, connect=3.0),
            )
        except httpx.TimeoutException as exc:
            raise DomainException(SANDBOX_TIMEOUT) from exc
        except httpx.HTTPError as exc:
            raise DomainException(SANDBOX_UNAVAILABLE) from exc
        if r.status_code == httpx.codes.OK:
            return SandboxResponse(r.status_code, {}), r.content
        return _parse(r), b""


def _parse(r: httpx.Response) -> SandboxResponse:
    try:
        data = r.json()
    except ValueError:
        data = {"error": "bad_response", "detail": r.text[:200]}
    return SandboxResponse(r.status_code, data if isinstance(data, dict) else {})
