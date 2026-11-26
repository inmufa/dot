from agent_helpers import RoutedLLM, assert_paired, chat, results, session
from backend.routing.clients.scripted import reply
from fastapi import FastAPI
from helpers import parse_sse, resolve_next, start_chat, types
from httpx import AsyncClient

PLAN = "## Plan\n1. read\n2. edit"


async def mode(c: AsyncClient, sid: str) -> str:
    sessions = (await c.get("/v1/sessions")).json()
    return next(s["mode"] for s in sessions if s["id"] == sid)


async def audit(c: AsyncClient, sid: str) -> list[dict]:
    return (await c.get(f"/v1/audit?session={sid}&limit=200")).json()["items"]


async def test_enter_plan_blocks_writes_then_exit_restores_previous_mode(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM, ws
):
    llm.scripts = [
        reply(calls=[("EnterPlanMode", {})]),
        reply(calls=[("Write", {"file_path": str(ws / "a.txt"), "content": "x"})]),
        reply(calls=[("ExitPlanMode", {"plan": PLAN})]),
        reply(calls=[("Write", {"file_path": str(ws / "a.txt"), "content": "x"})]),
        reply("done"),
    ]
    sid = await session(authed, "acceptEdits")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "allow")
    ev = parse_sse((await task).text)
    assert_paired(ev)
    r = results(ev)
    assert "Plan mode is on" in r[0]["output"]
    assert r[1]["is_error"]
    assert r[1]["output"].startswith("Denied (error 3000)")
    assert "Plan approved. Mode is now acceptEdits" in r[2]["output"]
    assert not r[3]["is_error"]  # acceptEdits is back: the write goes through
    assert (ws / "a.txt").read_text() == "x"
    appr = next(e for e in ev if e["type"] == "approval_required")
    assert appr["invocation"]["name"] == "ExitPlanMode"
    assert appr["diff"] == PLAN
    assert appr["subagent"] is None
    assert await mode(authed, sid) == "acceptEdits"
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert [m["content"] for m in msgs if m["role"] == "plan"] == [PLAN]
    rows = await audit(authed, sid)
    switches = [x["reason"] for x in rows if x["reason"].startswith("session mode")]
    assert sorted(switches) == [
        "session mode changed acceptEdits -> plan",
        "session mode changed plan -> acceptEdits",
    ]
    assert any(x["source"] == "user" and x["tool"] == "ExitPlanMode" for x in rows)


async def test_plan_message_never_reaches_the_model(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [
        reply(calls=[("EnterPlanMode", {})]),
        reply(calls=[("ExitPlanMode", {"plan": PLAN})]),
        reply("ok"),
    ]
    task = start_chat(authed, await session(authed))
    await resolve_next(app, authed, "allow")
    await task
    roles = [m["role"] for m in llm.requests[-1]["messages"]]
    assert "plan" not in roles
    assert roles == ["system", "user", "assistant", "tool", "assistant", "tool"], roles


async def test_reject_keeps_plan_mode(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [
        reply(calls=[("EnterPlanMode", {})]),
        reply(calls=[("ExitPlanMode", {"plan": PLAN})]),
        reply("revising"),
    ]
    sid = await session(authed)
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "reject")
    ev = parse_sse((await task).text)
    out = results(ev)[1]
    assert out["is_error"]
    assert "did not approve the plan" in out["output"]
    assert await mode(authed, sid) == "plan"
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert not [m for m in msgs if m["role"] == "plan"]


async def test_exit_plan_outside_plan_mode_and_timeout(
    authed: AsyncClient, llm: RoutedLLM
):
    llm.scripts = [reply(calls=[("ExitPlanMode", {"plan": "p"})]), reply("ok")]
    sid = await session(authed, "default")
    out = results(await chat(authed, sid))[0]
    assert out["is_error"]
    assert "Not in plan mode" in out["output"]
    llm.scripts = [
        reply(calls=[("EnterPlanMode", {})]),
        reply(calls=[("ExitPlanMode", {"plan": "p"})]),
        reply("ok"),
    ]
    ev = await chat(authed, sid)  # approval_timeout_s is 0.3 in tests
    assert "did not respond to the plan" in results(ev)[1]["output"]
    assert ev[-1]["stop_reason"] == "end_turn"
    assert await mode(authed, sid) == "plan"
    assert types(ev).count("approval_required") == 1


async def test_user_set_plan_mode_exits_to_default(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    sid = await session(authed, "plan")
    llm.scripts = [reply(calls=[("ExitPlanMode", {"plan": PLAN})]), reply("ok")]
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "always")
    await task
    assert await mode(authed, sid) == "default"
