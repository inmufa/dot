import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from backend.governance.settings.mcp_spec import McpServerSpec
from backend.main import create_app
from backend.mcp.services.connection import McpConnection
from backend.mcp.services.transports import sandbox_stdio
from backend.routing.clients.sandbox_client import SandboxClient
from dot_sandbox.main import create_app as create_sandbox_app
from dot_sandbox.settings import Settings as SandboxSettings
from helpers import new_session
from httpx import ASGITransport, AsyncClient
from mcp_helpers import (
    run_turn,
    search_and_call,
    stdio_cfg,
    tool_events,
    trust_and_connect,
    wait_status,
    write_settings,
)


async def until(cond, limit_s: float = 15) -> None:
    async with asyncio.timeout(limit_s):
        while not cond():  # noqa: ASYNC110
            await asyncio.sleep(0.02)


def failing_opener(counter: list[int]):
    @asynccontextmanager
    async def opener():
        counter.append(1)
        msg = "no route"
        raise ConnectionError(msg)
        yield

    return opener


async def test_backoff_stops_after_the_limit_then_waits_for_manual_reconnect():
    tries: list[int] = []
    conn = McpConnection(
        "x", failing_opener(tries), lambda *_: None, backoff=(0.01, 0.01)
    )
    conn.start()
    await until(lambda: len(tries) == 3)  # first try + 2 backoff retries
    await asyncio.sleep(0.2)
    assert len(tries) == 3
    assert conn.status == "failed"
    assert conn.error == "ConnectionError"
    conn.reconnect()
    await until(lambda: len(tries) >= 4)
    await conn.stop()
    assert conn.status == "stopped"


async def test_crashed_server_reconnects(authed: AsyncClient, ws, llm, app):
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    await trust_and_connect(authed, "fake")
    conn = app.state.mcp._entries["fake"].conn
    assert conn.connects == 1
    llm.scripts = search_and_call("mcp__fake__crash", {})
    sid = await new_session(authed, "bypass")
    out = tool_events(await run_turn(authed, sid))
    assert out[1]["is_error"] is True
    await until(lambda: conn.connects == 2)
    row = await wait_status(authed, "fake", "connected")
    assert row["tool_count"] == 10


async def test_manual_reconnect_endpoint(authed, ws, app):
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    await trust_and_connect(authed, "fake")
    conn = app.state.mcp._entries["fake"].conn
    r = await authed.post("/v1/mcp/servers/fake/reconnect")
    assert r.status_code == 200
    await until(lambda: conn.connects == 2)
    await wait_status(authed, "fake", "connected")


async def test_bad_command_is_failed_and_recoverable(authed, ws):
    write_settings(ws, {"mcpServers": {"b": {"command": "no-such-binary-xyz"}}})
    await wait_status(authed, "b", "needs_trust")
    await authed.post("/v1/mcp/servers/b/trust")
    row = await wait_status(authed, "b", "failed")
    assert row["error"] == "McpTransportError"
    write_settings(ws, {"mcpServers": {"b": stdio_cfg()}})
    await wait_status(authed, "b", "needs_trust")  # new config = new approval


async def test_stop_kills_the_sandbox_process(ws):
    sb_app = create_sandbox_app(SandboxSettings(workspace=ws))
    http = httpx.AsyncClient(transport=ASGITransport(app=sb_app), base_url="http://sb")
    sandbox = SandboxClient("http://sb", client=http)
    spec = McpServerSpec(**stdio_cfg())
    conn = McpConnection(
        "fake",
        lambda: sandbox_stdio(sandbox, "fake", spec, {}),
        lambda *_: None,
        ping_s=0.3,
    )
    conn.start()
    await until(lambda: conn.status == "connected")
    assert len(sb_app.state.mcp.procs) == 1
    pid = next(iter(sb_app.state.mcp.procs.values())).proc.pid
    await conn.stop()
    assert sb_app.state.mcp.procs == {}
    await http.aclose()
    for _ in range(100):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.05)
    msg = "process survived stop"
    raise AssertionError(msg)


async def test_runtime_close_stops_connections(settings, llm, sandbox, ws):
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    app = create_app(settings, llm=llm, sandbox=sandbox)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            headers={"Authorization": "Bearer " + "t" * 32},
        ) as c,
    ):
        await trust_and_connect(c, "fake")
        conn = app.state.mcp._entries["fake"].conn
    assert conn.status == "stopped"
    assert conn._task.done()
