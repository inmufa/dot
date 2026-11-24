import asyncio
import json

import httpx
from dot_cli.app import DotApp
from dot_cli.config import Config
from dot_cli.widgets import ApprovalBar, StatusBar
from support import DONE, FakeBackend, GatedStream, sse, tok, wait_for
from textual.widgets import Input

DIFF = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n"
TOOL = {"call_id": "c1", "name": "Edit", "arguments": {"file_path": "f.py"}}
APPROVAL = {
    "type": "approval_required",
    "approval_id": "A1",
    "invocation": TOOL,
    "diff": DIFF,
}


def make_app(backend: FakeBackend, grace: float = 0.0) -> DotApp:
    app = DotApp(Config(), backend.client())
    app.approval_grace_s = grace
    return app


async def send(pilot, app: DotApp, text: str) -> None:
    app.query_one(Input).value = text
    await pilot.press("enter")


def log_text(app: DotApp) -> str:
    return " ".join(str(w.render()) for w in app.query("#log Static"))


async def test_approval_flow_allow_then_done() -> None:
    gate = asyncio.Event()
    head = sse(
        tok("plan", thinking=True),
        tok("Editing"),
        {"type": "tool_call", "invocation": TOOL},
        {"type": "usage", "context_tokens": 500, "context_limit": 1000},
        APPROVAL,
    )
    backend = FakeBackend(
        lambda: httpx.Response(200, stream=GatedStream(head, sse(DONE), gate))
    )
    app = make_app(backend)
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "fix it")
        await wait_for(lambda: app.pending is not None, pilot)
        status = app.query_one(StatusBar)
        assert status.state == "approval"
        assert app.query_one(ApprovalBar).display
        assert "500/1000 (50%)" in str(status.render())
        assert "Edit(file_path=f.py)" in log_text(app)
        await pilot.press("a")
        await wait_for(
            lambda: "POST /v1/approvals/A1/resolve" in backend.paths(), pilot
        )
        resolve = next(r for r in backend.requests if "resolve" in r.url.path)
        assert json.loads(resolve.content) == {"decision": "allow"}
        gate.set()
        await wait_for(lambda: status.state == "idle", pilot)
        assert not app.query_one(ApprovalBar).display


async def _decide(key: str) -> dict:
    gate = asyncio.Event()
    stream = GatedStream(sse(APPROVAL), sse(DONE), gate)
    backend = FakeBackend(lambda: httpx.Response(200, stream=stream))
    app = make_app(backend)
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "x")
        await wait_for(lambda: app.pending is not None, pilot)
        await pilot.press(key)
        await wait_for(lambda: any("resolve" in p for p in backend.paths()), pilot)
        gate.set()
        return json.loads(backend.requests[-1].content)


async def test_reject_and_always_keys() -> None:
    assert await _decide("r") == {"decision": "reject"}
    assert await _decide("s") == {"decision": "always"}


async def test_slash_commands() -> None:
    backend = FakeBackend()
    app = make_app(backend)
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "/mode auto")
        await wait_for(lambda: app.mode == "auto", pilot)
        assert "auto" in str(app.query_one(StatusBar).render())
        await send(pilot, app, "/help")
        await wait_for(lambda: "/stop" in log_text(app), pilot)
        await send(pilot, app, "/new")
        await wait_for(lambda: backend.paths().count("POST /v1/sessions") == 2, pilot)
        await send(pilot, app, "/quit")
    assert "chat" not in " ".join(backend.paths())


async def test_stop_posts_and_returns_idle() -> None:
    gate = asyncio.Event()
    stream = GatedStream(sse(tok("working")), sse(DONE), gate)
    backend = FakeBackend(lambda: httpx.Response(200, stream=stream))
    app = make_app(backend)
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "go")
        await wait_for(lambda: "working" in log_text(app), pilot)
        await send(pilot, app, "/stop")
        await wait_for(
            lambda: "POST /v1/sessions/S0001abcd/stop" in backend.paths(), pilot
        )
        await wait_for(lambda: app.query_one(StatusBar).state == "idle", pilot)
        gate.set()


async def test_tool_result_truncated() -> None:
    result = {"call_id": "c1", "output": "\n".join(f"line{i}" for i in range(20))}
    body = sse({"type": "tool_result", "result": result}, DONE)
    backend = FakeBackend(lambda: httpx.Response(200, content=body))
    app = make_app(backend)
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "go")
        await wait_for(lambda: "line4" in log_text(app), pilot)
        preview = next(str(w.render()) for w in app.query(".tool-result"))
        assert "line4" in preview
        assert "line5" not in preview
        assert app.query("Collapsible")


async def test_approval_keys_ignored_during_grace_window() -> None:
    gate = asyncio.Event()
    stream = GatedStream(sse(APPROVAL), sse(DONE), gate)
    backend = FakeBackend(lambda: httpx.Response(200, stream=stream))
    app = make_app(backend, grace=0.5)
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "x")
        await wait_for(lambda: app.pending is not None, pilot)
        await pilot.press("a")  # a stray keystroke from typing
        await pilot.pause(0.1)
        assert app.pending is not None
        assert not any("resolve" in p for p in backend.paths())
        await pilot.pause(0.6)
        await pilot.press("a")
        await wait_for(lambda: any("resolve" in p for p in backend.paths()), pilot)
        gate.set()


async def test_stream_without_done_is_reported() -> None:
    backend = FakeBackend(lambda: httpx.Response(200, content=sse(tok("partial"))))
    app = make_app(backend)
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "go")
        await wait_for(lambda: "without a result" in log_text(app), pilot)
        assert app.query_one(StatusBar).state == "idle"


async def test_question_and_subagent_events_are_shown_not_fatal() -> None:
    head = sse(
        {
            "type": "subagent",
            "label": "Explore 1",
            "subagent_type": "Explore",
            "status": "started",
        },
        {
            "type": "subagent",
            "label": "Explore 1",
            "subagent_type": "Explore",
            "status": "queued",
        },
        {
            "type": "question",
            "question_id": "Q1",
            "question": "Which db?",
            "options": [{"label": "pg"}, {"label": "sqlite"}],
        },
        tok("fine"),
        DONE,
    )
    app = make_app(FakeBackend(lambda: httpx.Response(200, content=head)))
    async with app.run_test() as pilot:
        await wait_for(lambda: app.session_id is not None, pilot)
        await send(pilot, app, "go")
        await wait_for(lambda: app.query_one(StatusBar).state == "idle", pilot)
        text = log_text(app)
        assert "Explore 1: started" in text
        assert "question: Which db? [pg / sqlite]" in text
        assert "queued" not in text
