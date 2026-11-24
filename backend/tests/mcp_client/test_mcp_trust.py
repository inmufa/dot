import asyncio
import sys

from helpers import new_session
from httpx import AsyncClient
from mcp_helpers import (
    SERVER,
    run_turn,
    search_and_call,
    stdio_cfg,
    tool_events,
    trust_and_connect,
    wait_status,
    write_settings,
)


def marker_cfg() -> dict:
    code = "open('ran.txt', 'w').write('x'); import time; time.sleep(60)"
    return {"command": sys.executable, "args": ["-c", code]}


async def test_project_server_never_launches_before_approval(authed: AsyncClient, ws):
    write_settings(ws, {"mcpServers": {"p": marker_cfg()}})
    row = await wait_status(authed, "p", "needs_trust")
    assert row["trusted"] is False
    await asyncio.sleep(1.0)  # several reconcile ticks
    assert not (ws / "ran.txt").exists()
    await authed.post("/v1/mcp/servers/p/trust")
    for _ in range(100):
        if (ws / "ran.txt").exists():
            break
        await asyncio.sleep(0.05)
    assert (ws / "ran.txt").exists()


async def test_untrusted_server_has_no_tools(authed, ws, app):
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    await wait_status(authed, "fake", "needs_trust")
    assert not [d for d in app.state.agent.registry.definitions() if "mcp__" in d.name]
    assert "fake" not in app.state.skills.env.mcp


async def test_trust_is_audited_and_enables_tools(authed, ws, llm):
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    row = await trust_and_connect(authed, "fake")
    assert row["trusted"] is True
    audit = (await authed.get("/v1/audit?session=mcp")).json()["items"]
    assert audit[0]["tool"] == "mcp_trust"
    assert audit[0]["source"] == "user"
    assert audit[0]["args"]["server"] == "fake"
    llm.scripts = search_and_call("mcp__fake__echo", {"text": "t"})
    sid = await new_session(authed, "bypass")
    assert tool_events(await run_turn(authed, sid))[1]["output"] == "echo: t"


async def test_changed_config_needs_a_new_approval(authed, ws):
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    await trust_and_connect(authed, "fake")
    changed = stdio_cfg(args=[SERVER, "stdio", "--extra"])
    write_settings(ws, {"mcpServers": {"fake": changed}})
    row = await wait_status(authed, "fake", "needs_trust")
    assert row["tool_count"] == 0


async def test_same_config_is_remembered_after_removal(authed, ws):
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    await trust_and_connect(authed, "fake")
    write_settings(ws, {})
    await asyncio.sleep(0.6)
    write_settings(ws, {"mcpServers": {"fake": stdio_cfg()}})
    await wait_status(authed, "fake", "connected")


async def test_unknown_server_is_404(authed):
    r = await authed.post("/v1/mcp/servers/nope/trust")
    assert r.status_code == 404
    assert r.json()[0]["code"] == 4030
    r = await authed.post("/v1/mcp/servers/nope/reconnect")
    assert r.status_code == 404


async def test_endpoints_need_the_token(client):
    assert (await client.get("/v1/mcp/servers")).status_code == 401
    assert (await client.post("/v1/mcp/servers/x/trust")).status_code == 401
