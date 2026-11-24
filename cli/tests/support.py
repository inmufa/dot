import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import httpx
from dot_cli.api import DotClient
from dot_contracts.events import StreamEvent
from dot_contracts.sessions import SessionInfo

SESSION = SessionInfo(id="S0001abcd", mode="default", created_at=datetime.now(UTC))


def sse(*events: dict) -> bytes:
    return b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events)


def tok(text: str, *, thinking: bool = False) -> dict:
    return {"type": "token", "text": text, "thinking": thinking}


DONE = {"type": "done", "stop_reason": "end_turn"}


class GatedStream(httpx.AsyncByteStream):
    """Yields `head`, waits for `gate`, then yields `tail`."""

    def __init__(self, head: bytes, tail: bytes, gate: asyncio.Event) -> None:
        self.head, self.tail, self.gate = head, tail, gate

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self.head
        await self.gate.wait()
        yield self.tail


class FakeBackend:
    """MockTransport handler recording requests; chat body is configurable."""

    def __init__(self, chat: Callable[[], httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.chat = chat or (lambda: httpx.Response(200, content=sse(DONE)))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/chat"):
            return self.chat()
        if path == "/v1/sessions":
            return httpx.Response(200, json=json.loads(SESSION.model_dump_json()))
        if path.endswith("/mode"):
            body = json.loads(SESSION.model_dump_json()) | {
                "mode": json.loads(request.content)["mode"]
            }
            return httpx.Response(200, json=body)
        return httpx.Response(200, json={"ok": True})

    def paths(self) -> list[str]:
        return [f"{r.method} {r.url.path}" for r in self.requests]

    def client(self, token: str | None = None) -> DotClient:
        return DotClient(
            "http://test", token or "tkn", transport=httpx.MockTransport(self)
        )


async def wait_for(predicate: Callable[[], bool], pilot, tries: int = 100) -> None:
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause(0.02)
    msg = "condition not reached"
    raise AssertionError(msg)


async def collect(stream: AsyncIterator[StreamEvent]) -> list[StreamEvent]:
    return [e async for e in stream]
