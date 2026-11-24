import asyncio

from fastapi import FastAPI
from helpers import new_session, resolve_next, start_chat
from httpx import AsyncClient
from mcp_helpers import (
    events_of,
    run_turn,
    search_and_call,
    stdio_cfg,
    tool_events,
    trust_and_connect,
    wait_status,
    write_settings,
)

BYPASS = "bypass"


async def connect(c: AsyncClient, ws, name: str = "fake", **extra) -> dict:
    write_settings(ws, {"mcpServers": {name: stdio_cfg(**extra)}})
    return await trust_and_connect(c, name)


async def test_server_listed_with_tool_count(authed, ws):
    row = await connect(authed, ws)
    assert row["transport"] == "stdio"
    assert row["scope"] == "project"  # workspace settings
    assert row["tool_count"] == 10
    assert row["status"] == "connected"


async def test_tools_are_deferred_and_found_by_tool_search(authed, ws, app: FastAPI):
    await connect(authed, ws)
    reg = app.state.agent.registry
    assert "mcp__fake__echo" in reg.deferred_names()
    assert "mcp__fake__echo" not in {d.name for d in reg.core_definitions()}
    assert all(d.deferred for d in reg.definitions() if d.name.startswith("mcp__"))


async def test_search_activate_call_is_tainted_and_governed(authed, ws, llm):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__read_note", {"name": "n1"})
    sid = await new_session(authed, BYPASS)
    events = await run_turn(authed, sid)
    out = tool_events(events)
    assert "Activated 1 tool(s)" in out[0]["output"]
    assert "[MCP server fake]" in out[0]["output"]
    assert out[1]["is_error"] is False
    assert "note n1" in out[1]["output"]
    assert "<system-reminder>" not in out[1]["output"]  # control tags neutralised
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    tool_rows = [m for m in msgs if m["role"] == "tool"]
    assert [m["tainted"] for m in tool_rows] == [False, True]


async def test_plain_tool_asks_in_default_mode(authed, ws, llm, app):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__echo", {"text": "hi"})
    sid = await new_session(authed, "default")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "allow")
    out = tool_events(await events_of(task))
    assert out[1]["output"] == "echo: hi"


async def test_read_only_annotation_never_skips_the_prompt(authed, ws, llm, app):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__read_note", {"name": "x"})
    sid = await new_session(authed, "default")
    task = start_chat(authed, sid)  # a server's own claim never auto-allows
    await resolve_next(app, authed, "allow")
    events = await events_of(task)
    assert tool_events(events)[1]["output"].startswith("note x")


async def test_destructive_and_open_world_hints_always_ask(authed, ws, llm, app):
    await connect(authed, ws)
    reg = app.state.agent.registry
    wipe = reg.get("mcp__fake__wipe").definition
    look = reg.get("mcp__fake__lookup").definition
    ro = reg.get("mcp__fake__read_note").definition
    assert (wipe.mutating, wipe.needs_approval) == (True, True)
    assert (look.mutating, look.needs_approval) == (False, True)
    assert (ro.mutating, ro.needs_approval) == (False, True)
    llm.scripts = search_and_call("mcp__fake__lookup", {"query": "q"})
    sid = await new_session(authed, "default")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "reject")
    out = tool_events(await events_of(task))
    assert out[1]["is_error"] is True
    assert "Denied" in out[1]["output"]


async def test_destructive_asks_even_in_auto_mode(authed, ws, llm, app):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__wipe", {"target": "/"})
    sid = await new_session(authed, "auto")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "reject")  # a human, not the classifier
    out = tool_events(await events_of(task))
    assert "Denied" in out[1]["output"]


async def test_deny_rule_beats_read_only_annotation(authed, ws, llm):
    write_settings(
        ws,
        {
            "mcpServers": {"fake": stdio_cfg()},
            "permissions": {"deny": ["mcp__fake__read_note"]},
        },
    )
    await trust_and_connect(authed, "fake")
    llm.scripts = search_and_call("mcp__fake__read_note", {"name": "x"})
    sid = await new_session(authed, BYPASS)
    out = tool_events(await run_turn(authed, sid))
    assert "Denied" in out[1]["output"]


async def test_rule_glob_covers_a_whole_server(authed, ws, llm):
    write_settings(
        ws,
        {
            "mcpServers": {"fake": stdio_cfg()},
            "permissions": {"allow": ["mcp__fake__*"]},
        },
    )
    await trust_and_connect(authed, "fake")
    llm.scripts = search_and_call("mcp__fake__echo", {"text": "a"})
    sid = await new_session(authed, "default")
    out = tool_events(await run_turn(authed, sid))
    assert out[1]["output"] == "echo: a"


async def test_plan_mode_denies_mutating_mcp_tools(authed, ws, llm):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__echo", {"text": "a"})
    sid = await new_session(authed, "plan")
    out = tool_events(await run_turn(authed, sid))
    assert "Denied" in out[1]["output"]


async def test_server_error_is_a_tainted_error_result(authed, ws, llm):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__fail", {})
    sid = await new_session(authed, BYPASS)
    events = await run_turn(authed, sid)
    res = tool_events(events)[1]
    assert res["is_error"] is True
    assert "<think>" not in res["output"]


async def test_big_output_is_capped_and_spilled(authed, ws, llm):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__big", {"n": 50_000})
    sid = await new_session(authed, BYPASS)
    res = tool_events(await run_turn(authed, sid))[1]
    assert len(res["output"]) < 14_000
    assert "full output at" in res["output"]
    assert res["spill_path"].startswith(str(ws / ".dot" / "tool_outputs"))
    assert len(open(res["spill_path"]).read()) == 50_000  # noqa: ASYNC230, PTH123, SIM115


async def test_call_timeout(authed, ws, llm, app):
    await connect(authed, ws)
    app.state.mcp._s = app.state.mcp._s.model_copy(update={"mcp_call_timeout_s": 0.5})
    llm.scripts = search_and_call("mcp__fake__slow", {"seconds": 0.2})
    sid = await new_session(authed, BYPASS)
    assert tool_events(await run_turn(authed, sid))[1]["output"] == "done"


async def test_env_is_scrubbed_but_explicit_env_passes(authed, ws, llm, monkeypatch):
    monkeypatch.setenv("SECRET_IN_BACKEND", "leak")
    monkeypatch.setenv("DOT_MCP_ENV_ALLOWLIST", "")
    await connect(authed, ws, env={"EXPLICIT": "yes"})
    llm.scripts = [
        *search_and_call("mcp__fake__env_peek", {"name": "EXPLICIT"})[:-1],
        *search_and_call("mcp__fake__env_peek", {"name": "SECRET_IN_BACKEND"})[1:],
    ]
    sid = await new_session(authed, BYPASS)
    out = tool_events(await run_turn(authed, sid))
    assert out[1]["output"] == "yes"
    assert out[2]["output"] == "None"


async def test_list_changed_adds_tools(authed, ws, llm, app):
    await connect(authed, ws)
    llm.scripts = search_and_call("mcp__fake__add_tool", {})
    sid = await new_session(authed, BYPASS)
    await run_turn(authed, sid)
    reg = app.state.agent.registry
    for _ in range(100):
        if reg.get("mcp__fake__extra"):
            break
        await asyncio.sleep(0.05)
    assert reg.get("mcp__fake__extra") is not None
    row = await wait_status(authed, "fake", "connected")
    assert row["tool_count"] == 11


async def test_skills_environment_sees_connected_server(authed, ws, app):
    await connect(authed, ws)
    assert "fake" in app.state.skills.env.mcp
    assert "mcp__fake__echo" in app.state.skills.env.tools


async def test_removing_the_server_unregisters_tools(authed, ws, app):
    await connect(authed, ws)
    write_settings(ws, {})
    for _ in range(100):
        if app.state.agent.registry.get("mcp__fake__echo") is None:
            break
        await asyncio.sleep(0.05)
    assert app.state.agent.registry.get("mcp__fake__echo") is None
    assert (await authed.get("/v1/mcp/servers")).json() == []
    assert "fake" not in app.state.skills.env.mcp


async def test_ready_ignores_mcp_failures(authed, ws, client):
    before = (await client.get("/ready")).status_code
    write_settings(ws, {"mcpServers": {"bad": {"command": "no-such-binary-xyz"}}})
    await wait_status(authed, "bad", "needs_trust")
    await authed.post("/v1/mcp/servers/bad/trust")
    await wait_status(authed, "bad", "failed")
    assert (await client.get("/ready")).status_code == before
