import json

import httpx
import pytest
from dot_cli.api import ApiError, DotClient
from dot_contracts.events import DoneEvent, TokenEvent
from support import DONE, FakeBackend, collect, sse, tok


async def test_create_session_sends_auth_and_mode() -> None:
    backend = FakeBackend()
    client = backend.client()
    info = await client.create_session("plan")
    assert info.id == "S0001abcd"
    request = backend.requests[0]
    assert request.headers["authorization"] == "Bearer tkn"
    assert json.loads(request.content) == {"mode": "plan"}


async def test_chat_streams_events() -> None:
    backend = FakeBackend(lambda: httpx.Response(200, content=sse(tok("a"), DONE)))
    events = await collect(backend.client().chat("S1", "hello"))
    assert events == [TokenEvent(text="a"), DoneEvent(stop_reason="end_turn")]
    assert json.loads(backend.requests[0].content) == {"message": "hello"}


async def test_chat_error_status_raises() -> None:
    backend = FakeBackend(lambda: httpx.Response(409, text="busy"))
    with pytest.raises(ApiError) as exc:
        await collect(backend.client().chat("S1", "x"))
    assert exc.value.status == 409


async def test_resolve_stop_mode_paths() -> None:
    backend = FakeBackend()
    client = backend.client()
    await client.resolve("A1", "always")
    await client.stop("S1")
    await client.set_mode("S1", "auto")
    assert backend.paths() == [
        "POST /v1/approvals/A1/resolve",
        "POST /v1/sessions/S1/stop",
        "POST /v1/sessions/S1/mode",
    ]
    assert json.loads(backend.requests[0].content) == {"decision": "always"}


async def test_rewind_posts_target_and_parses_result() -> None:
    seen: list[httpx.Request] = []
    body = {"kept_through_seq": 5, "rewound_messages": 4, "restored": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    client = DotClient("http://t", transport=httpx.MockTransport(handler))
    out = await client.rewind("S1", 5)
    assert seen[0].url.path == "/v1/sessions/S1/rewind"
    assert json.loads(seen[0].content) == {"to_seq": 5}
    assert out.rewound_messages == 4


async def test_compaction_event_and_compact_call() -> None:
    event = {
        "type": "compaction",
        "tokens_before": 3000,
        "tokens_after": 900,
        "stages": ["summary"],
    }
    backend = FakeBackend(lambda: httpx.Response(200, content=sse(event, DONE)))
    events = await collect(backend.client().chat("S1", "x"))
    assert events[0].type == "compaction"
    assert events[0].tokens_after == 900
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = {
            "compacted": True,
            "tokens_before": 5,
            "tokens_after": 2,
            "stages": ["summary"],
        }
        return httpx.Response(200, json=body)

    client = DotClient("http://test", "tkn", transport=httpx.MockTransport(handler))
    assert (await client.compact("S1")).compacted
    assert seen[0].url.path == "/v1/sessions/S1/compact"
