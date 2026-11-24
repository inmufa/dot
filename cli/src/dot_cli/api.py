"""Async HTTP client for the Dot backend public API."""

from collections.abc import AsyncIterator
from typing import Literal

import httpx
from dot_contracts.events import StreamEvent
from dot_contracts.sessions import CompactOut, Message, RewindOut, SessionInfo

from dot_cli.sse import SseDecoder

Decision = Literal["allow", "always", "reject"]
_STREAM_TIMEOUT = httpx.Timeout(10.0, read=None)


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def _check(response: httpx.Response) -> None:
    if response.is_success:
        return
    raise ApiError(response.status_code, response.text.strip()[:300])


class DotClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            transport=transport,
            timeout=30.0,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def create_session(self, mode: str | None = None) -> SessionInfo:
        body = {"mode": mode} if mode else {}
        response = await self._http.post("/v1/sessions", json=body)
        _check(response)
        return SessionInfo.model_validate(response.json())

    async def messages(self, session_id: str) -> list[Message]:
        response = await self._http.get(f"/v1/sessions/{session_id}/messages")
        _check(response)
        return [Message.model_validate(item) for item in response.json()]

    async def set_mode(self, session_id: str, mode: str) -> SessionInfo:
        response = await self._http.post(
            f"/v1/sessions/{session_id}/mode", json={"mode": mode}
        )
        _check(response)
        return SessionInfo.model_validate(response.json())

    async def resolve(self, approval_id: str, decision: Decision) -> None:
        response = await self._http.post(
            f"/v1/approvals/{approval_id}/resolve", json={"decision": decision}
        )
        _check(response)

    async def answer(
        self, question_id: str, selected: list[str], other: str | None
    ) -> None:
        response = await self._http.post(
            f"/v1/questions/{question_id}/answer",
            json={"selected": selected, "other": other},
        )
        _check(response)

    async def stop(self, session_id: str) -> None:
        _check(await self._http.post(f"/v1/sessions/{session_id}/stop"))

    async def rewind(self, session_id: str, to_seq: int) -> RewindOut:
        response = await self._http.post(
            f"/v1/sessions/{session_id}/rewind", json={"to_seq": to_seq}
        )
        _check(response)
        return RewindOut.model_validate(response.json())

    async def compact(self, session_id: str) -> CompactOut:
        response = await self._http.post(f"/v1/sessions/{session_id}/compact")
        _check(response)
        return CompactOut.model_validate(response.json())

    async def chat(self, session_id: str, message: str) -> AsyncIterator[StreamEvent]:
        decoder = SseDecoder()
        async with self._http.stream(
            "POST",
            f"/v1/sessions/{session_id}/chat",
            json={"message": message},
            headers={"Accept": "text/event-stream"},
            timeout=_STREAM_TIMEOUT,
        ) as response:
            if not response.is_success:
                await response.aread()
                _check(response)
            async for chunk in response.aiter_bytes():
                for event in decoder.feed(chunk):
                    yield event
            for event in decoder.flush():
                yield event
