"""HTTP client for the voice worker (X-Voice-Token). Audio is never stored or logged."""

import logging
import time
from typing import Any

import httpx

from backend.core.exceptions import DomainException

logger = logging.getLogger(__name__)
VOICE_UNAVAILABLE = 4130
AUDIO_TOO_LARGE = 4131
AUDIO_TOO_LONG = 4132
BAD_AUDIO = 4133
BAD_TEXT = 4134
VOICE_FAILED = 4135
UNKNOWN_VOICE = 4136

_WORKER_CODES = {
    "audio_too_large": AUDIO_TOO_LARGE,
    "audio_too_long": AUDIO_TOO_LONG,
    "bad_audio_format": BAD_AUDIO,
    "empty_audio": BAD_AUDIO,
    "text_too_long": BAD_TEXT,
    "nothing_to_speak": BAD_TEXT,
    "unknown_voice": UNKNOWN_VOICE,
    "stt_unavailable": VOICE_UNAVAILABLE,
    "tts_unavailable": VOICE_UNAVAILABLE,
}
_STATUS_TTL_S = 5.0


def worker_failure(r: httpx.Response) -> DomainException:
    try:
        data = r.json()
    except ValueError:
        data = {}
    key = str(data.get("error", "")) if isinstance(data, dict) else ""
    return DomainException(_WORKER_CODES.get(key, VOICE_FAILED))


class VoiceClient:
    def __init__(
        self,
        base_url: str,
        token: str | None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=3.0), trust_env=False
        )
        self._status: tuple[float, dict[str, Any]] | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {"X-Voice-Token": self._token or ""}

    async def status(self) -> dict[str, Any]:
        """{available, stt, tts}; cached a few seconds so polling stays cheap."""
        now = time.monotonic()
        if self._status and now - self._status[0] < _STATUS_TTL_S:
            return self._status[1]
        out = {"available": False, "stt": False, "tts": False}
        if self._token:
            try:
                r = await self._client.get(
                    f"{self._base}/health", timeout=httpx.Timeout(2.0)
                )
                data = r.json() if r.status_code == httpx.codes.OK else {}
                out = {
                    "available": bool(data.get("stt") or data.get("tts")),
                    "stt": bool(data.get("stt")),
                    "tts": bool(data.get("tts")),
                }
            except (httpx.HTTPError, ValueError):
                logger.info("voice worker not reachable")
        self._status = (now, out)
        return out

    async def _send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
        if not self._token:
            raise DomainException(VOICE_UNAVAILABLE)
        try:
            return await self._client.send(request, stream=stream)
        except httpx.TimeoutException as exc:
            raise DomainException(VOICE_FAILED) from exc
        except httpx.HTTPError as exc:
            self._status = None
            logger.warning("voice transport error: %s", type(exc).__name__)
            raise DomainException(VOICE_UNAVAILABLE) from exc

    async def get_json(self, path: str) -> dict[str, Any]:
        req = self._client.build_request(
            "GET", f"{self._base}{path}", headers=self._headers()
        )
        r = await self._send(req, stream=False)
        if r.status_code >= httpx.codes.BAD_REQUEST:
            raise worker_failure(r)
        return r.json()

    async def transcribe(self, audio: bytes, content_type: str) -> dict[str, Any]:
        req = self._client.build_request(
            "POST",
            f"{self._base}/transcribe",
            content=audio,
            headers={**self._headers(), "Content-Type": content_type},
        )
        r = await self._send(req, stream=False)
        if r.status_code >= httpx.codes.BAD_REQUEST:
            raise worker_failure(r)
        return r.json()

    async def speak(self, payload: dict[str, Any]) -> httpx.Response:
        """Open stream: the caller must aclose() it (the route does, via a background task)."""
        req = self._client.build_request(
            "POST", f"{self._base}/speak", json=payload, headers=self._headers()
        )
        r = await self._send(req, stream=True)
        if r.status_code >= httpx.codes.BAD_REQUEST:
            await r.aread()
            await r.aclose()
            raise worker_failure(r)
        return r
