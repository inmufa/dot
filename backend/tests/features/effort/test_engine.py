import asyncio

from backend.routing.clients.scripted import ScriptedLLM, reply
from backend.sessions.models import Session
from backend.sessions.services.session_service import SessionService
from helpers import new_session, parse_sse, resolve_next
from httpx import AsyncClient
from sqlalchemy import update


async def mode_of(app, sid: str) -> str:
    return (await SessionService(app.state.sessions).get(sid)).mode


async def chat(c: AsyncClient, sid: str, msg: str = "go", **extra):
    r = await c.post(f"/v1/sessions/{sid}/chat", json={"message": msg, **extra})
    return parse_sse(r.text)


async def test_options_follow_request_and_session(authed, llm: ScriptedLLM, app):
    llm.scripts = [reply("a"), reply("b"), reply("c")]
    sid = await new_session(authed)
    await chat(authed, sid)
    assert llm.requests[0]["options"].max_tokens is None  # medium
    await chat(authed, sid, effort="off")
    o = llm.requests[1]["options"]
    assert o.thinking is False
    async with app.state.sessions() as db:
        await db.execute(update(Session).values(effort="high"))
        await db.commit()
    await chat(authed, sid)
    assert llm.requests[2]["options"].max_tokens == 12000
    last = llm.requests[2]["messages"][-1]["content"]
    assert "double-check" in last


async def test_ultrathink_is_this_turn_only(authed, llm: ScriptedLLM):
    llm.scripts = [reply("a"), reply("ok"), reply("b")]
    sid = await new_session(authed)
    ev = await chat(authed, sid, "ultrathink: 2+2")
    usage = next(e for e in ev if e["type"] == "usage")
    assert usage["effort"]["level"] == "max"
    assert usage["effort"]["ultrathink"] is True
    assert usage["effort"]["requested"] == "medium"
    await chat(authed, sid, "plain")
    assert llm.requests[-1]["options"].max_tokens is None


async def test_max_adds_one_self_check(authed, llm: ScriptedLLM):
    llm.scripts = [reply("4"), reply("Verified.")]
    sid = await new_session(authed)
    ev = await chat(authed, sid, "ultrathink 2+2")
    assert len(llm.requests) == 2
    assert "Self-check" in llm.requests[1]["messages"][-1]["content"]
    assert ev[-1]["stop_reason"] == "end_turn"
    llm.scripts = [reply("x")]
    await chat(authed, sid, "effort high", effort="high")
    assert len(llm.requests) == 3  # high: no extra step


async def test_voice_forces_off_and_short_hint(authed, llm: ScriptedLLM):
    llm.scripts = [reply("hi")]
    sid = await new_session(authed)
    ev = await chat(authed, sid, "ultrathink", effort="max", voice=True)
    assert llm.requests[0]["options"].thinking is False
    assert next(e for e in ev if e["type"] == "usage")["effort"]["level"] == "off"
    assert "short spoken" in llm.requests[0]["messages"][-1]["content"]


async def test_usage_event_and_meta(authed, llm: ScriptedLLM):
    llm.scripts = [reply("hi")]
    sid = await new_session(authed)
    ev = await chat(authed, sid, effort="low")
    u = next(e for e in ev if e["type"] == "usage")
    assert u["prompt_tokens"] == 100
    assert u["completion_tokens"] == 10
    assert u["duration_ms"] >= 0
    assert u["effort"]["level"] == "low"
    assert u["effort"]["max_tokens"] == 3072
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    meta = msgs[-1]["meta"]["usage"]
    assert meta["effort"] == "low"
    assert meta["completion_tokens"] == 10
    assert meta["thinking"] is True


async def test_overlong_reasoning_is_cut_and_retried_without_thinking(
    authed, llm: ScriptedLLM
):
    llm.scripts = [reply(thinking="x" * 20_000), reply("done")]
    sid = await new_session(authed)
    ev = await chat(authed, sid, effort="low")
    assert len(llm.requests) == 2
    assert llm.requests[0]["options"].thinking is True
    assert llm.requests[1]["options"].thinking is False
    visible = [e["text"] for e in ev if e["type"] == "token" and not e["thinking"]]
    assert visible == ["done"]
    assert ev[-1]["stop_reason"] == "end_turn"


async def test_plan_flag_restores_mode(authed, llm: ScriptedLLM, app):
    llm.scripts = [reply("just an answer")]
    sid = await new_session(authed)
    await chat(authed, sid, plan=True)
    assert "Plan turn" in llm.requests[0]["messages"][-1]["content"]
    assert "Permission mode: plan" in llm.requests[0]["messages"][-1]["content"]
    assert await mode_of(app, sid) == "default"


async def test_plan_flag_exit_plan_approved(authed, llm: ScriptedLLM, app):
    llm.scripts = [
        reply(calls=[("ExitPlanMode", {"plan": "1. do it"})]),
        reply("ok"),
    ]
    sid = await new_session(authed)
    task = asyncio.create_task(
        authed.post(f"/v1/sessions/{sid}/chat", json={"message": "p", "plan": True})
    )
    await resolve_next(app, authed, "allow")
    ev = parse_sse((await task).text)
    assert ev[-1]["stop_reason"] == "end_turn"
    assert await mode_of(app, sid) == "default"
    assert sid not in app.state.agent.previous_mode


async def test_plan_flag_cancel_restores_mode(authed, llm: ScriptedLLM, app):
    gate = asyncio.Event()
    llm.scripts = [[gate, *reply("never")]]
    sid = await new_session(authed)
    task = asyncio.create_task(
        authed.post(f"/v1/sessions/{sid}/chat", json={"message": "p", "plan": True})
    )
    async with asyncio.timeout(5):
        while not llm.requests:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    assert await mode_of(app, sid) == "plan"
    assert (await authed.post(f"/v1/sessions/{sid}/stop")).json()["stopped"]
    await task
    assert await mode_of(app, sid) == "default"
    assert sid not in app.state.agent.previous_mode
