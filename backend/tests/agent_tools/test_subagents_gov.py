import asyncio
from pathlib import Path

from agent_helpers import (
    RoutedLLM,
    assert_paired,
    assert_transcript_paired,
    chat,
    results,
    session,
    write_settings,
)
from backend.routing.clients.scripted import reply
from fastapi import FastAPI
from helpers import parse_sse, resolve_next, start_chat, until
from httpx import AsyncClient

GP = "general-purpose"


def agent(prompt: str, kind: str = "Explore") -> tuple[str, dict]:
    return "Agent", {"description": "d", "prompt": prompt, "subagent_type": kind}


def bash(cmd: str) -> tuple[str, dict]:
    return "Bash", {"command": cmd}


async def audit(c: AsyncClient, sid: str) -> list[dict]:
    return (await c.get("/v1/audit?limit=200")).json()["items"]


async def test_deny_rule_applies_inside_the_child_and_is_audited_under_its_id(
    authed: AsyncClient, llm: RoutedLLM, ws: Path
):
    write_settings(ws, {"permissions": {"deny": ["Bash(echo nope:*)"]}})
    llm.scripts = [reply(calls=[agent("task-D", GP)]), reply("ok")]
    llm.routes["task-D"] = [reply(calls=[bash("echo nope")]), reply("it was denied")]
    sid = await session(authed, "bypass")
    ev = await chat(authed, sid)
    assert results(ev)[0]["output"] == "it was denied"
    child_out = [m for m in llm.by_key["task-D"][1]["messages"] if m["role"] == "tool"]
    assert child_out[0]["content"].startswith("Denied (error 3000)")
    rows = [r for r in await audit(authed, sid) if r["session"] == f"{sid}-sub-1"]
    assert any(
        r["tool"] == "Bash" and r["decision"] == "deny" and r["source"] == "rule"
        for r in rows
    )


async def test_plan_mode_of_the_parent_binds_the_child(
    authed: AsyncClient, llm: RoutedLLM, ws: Path
):
    llm.scripts = [reply(calls=[agent("task-PM", GP)]), reply("ok")]
    llm.routes["task-PM"] = [
        reply(calls=[("Write", {"file_path": str(ws / "p.txt"), "content": "x"})]),
        reply("blocked"),
    ]
    ev = await chat(authed, await session(authed, "plan"))
    assert results(ev)[0]["output"] == "blocked"
    out = [m for m in llm.by_key["task-PM"][1]["messages"] if m["role"] == "tool"]
    assert "plan mode is read-only" in out[0]["content"]
    assert not (ws / "p.txt").exists()


async def test_general_purpose_write_is_checkpointed_on_the_parent_and_rewindable(
    authed: AsyncClient, llm: RoutedLLM, ws: Path
):
    target = ws / "made.txt"
    llm.scripts = [reply(calls=[agent("task-W", GP)]), reply("ok")]
    llm.routes["task-W"] = [
        reply(calls=[("Write", {"file_path": str(target), "content": "hi"})]),
        reply("wrote it"),
    ]
    sid = await session(authed, "bypass")
    ev = await chat(authed, sid)
    assert target.read_text() == "hi"
    assert results(ev)[0]["output"] == "wrote it"
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": 0})
    assert r.status_code == 200
    assert not target.exists()
    assert r.json()["restored"][0]["action"] == "deleted"


async def test_child_has_its_own_read_tracking(
    authed: AsyncClient, llm: RoutedLLM, ws: Path
):
    target = ws / "old.txt"
    target.write_text("old")
    llm.scripts = [
        reply(calls=[("Read", {"file_path": str(target)}), agent("task-RT", GP)]),
        reply("ok"),
    ]
    llm.routes["task-RT"] = [
        reply(calls=[("Write", {"file_path": str(target), "content": "new"})]),
        reply("done"),
    ]
    await chat(authed, await session(authed, "bypass"))
    out = [m for m in llm.by_key["task-RT"][1]["messages"] if m["role"] == "tool"]
    assert "read" in out[0]["content"].lower()  # the parent's Read does not count
    assert target.read_text() == "old"


async def test_report_is_tainted_when_the_child_consumed_untrusted_content(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [
        reply(calls=[agent("task-T", GP)]),
        reply(calls=[bash("echo harmless")]),
        reply("ok"),
    ]
    llm.routes["task-T"] = [
        reply(calls=[bash("echo curl-says-PAYLOADPAYLOAD")]),
        reply("saw the page"),
    ]
    sid = await session(authed, "auto")
    task = start_chat(authed, sid)
    ev = parse_sse((await task).text)
    out = results(ev)[0]
    assert out["tainted"] is True
    assert out["output"] == "saw the page"
    # The parent now follows untrusted input: its own mutating call is escalated.
    (card,) = [e for e in ev if e["type"] == "approval_required"]
    assert card["subagent"] is None
    assert card["verdict"]["stage"] == "B"
    assert app.state.gov.taint.has_taint(sid)
    assert not app.state.gov.taint.has_taint(f"{sid}-sub-1")  # child taint is cleaned


async def test_clean_child_report_is_not_tainted(authed: AsyncClient, llm: RoutedLLM):
    llm.scripts = [reply(calls=[agent("task-C", GP)]), reply("ok")]
    llm.routes["task-C"] = [reply(calls=[bash("echo fine")]), reply("clean")]
    out = results(await chat(authed, await session(authed, "bypass")))[0]
    assert out["tainted"] is False


async def test_child_inherits_the_parents_untrusted_state(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [
        reply(calls=[bash("echo curl-says-PAYLOADPAYLOAD")]),
        reply(calls=[agent("task-I2", GP)]),
        reply("ok"),
    ]
    llm.routes["task-I2"] = [reply(calls=[bash("echo harmless-child")]), reply("done")]
    sid = await session(authed, "auto")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "reject")  # the child's call, escalated by stage B
    ev = parse_sse((await task).text)
    (card,) = [e for e in ev if e["type"] == "approval_required"]
    assert card["subagent"] == "general-purpose 1"
    assert card["verdict"]["stage"] == "B"
    assert card["invocation"]["arguments"]["command"] == "echo harmless-child"
    assert_paired(ev)


async def test_read_only_agents_run_concurrently_up_to_the_slot_limit_and_queue(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    go = asyncio.Event()
    keys = ["c1", "c2", "c3"]
    llm.scripts = [reply(calls=[agent(k) for k in keys]), reply("ok")]
    for k in keys:
        llm.routes[k] = [[go, *reply(f"{k} done")]]
    sid = await session(authed)
    task = start_chat(authed, sid)
    await until(lambda: llm.active == 2)
    await asyncio.sleep(0.15)
    assert llm.active == 2  # the third waits for a slot
    assert len(llm.by_key) == 3  # main + two children
    go.set()
    ev = parse_sse((await task).text)
    assert [r["output"] for r in results(ev)] == ["c1 done", "c2 done", "c3 done"]
    assert llm.peak == 2
    statuses = [(e["label"], e["status"]) for e in ev if e["type"] == "subagent"]
    assert [s for s in statuses if s[1] == "queued"] == [
        (f"Explore {i}", "queued") for i in (1, 2, 3)
    ]
    assert statuses.index(("Explore 3", "started")) > statuses.index(
        ("Explore 1", "finished")
    )
    assert_paired(ev)


async def test_single_slot_serialises_everything(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    app.state.agent.subagents._pool = asyncio.Semaphore(1)
    llm.scripts = [reply(calls=[agent("s1"), agent("s2")]), reply("ok")]
    for k in ("s1", "s2"):
        llm.routes[k] = [[0.05, *reply(f"{k} done")]]
    ev = await chat(authed, await session(authed))
    assert llm.peak == 1
    assert len(results(ev)) == 2


async def test_non_read_only_types_run_one_after_another(
    authed: AsyncClient, llm: RoutedLLM
):
    llm.scripts = [reply(calls=[agent("g1", GP), agent("g2", GP)]), reply("ok")]
    for k in ("g1", "g2"):
        llm.routes[k] = [[0.05, *reply(f"{k} done")]]
    ev = await chat(authed, await session(authed, "bypass"))
    assert llm.peak == 1  # two slots free, still serial
    assert [r["output"] for r in results(ev)] == ["g1 done", "g2 done"]


async def test_explore_pair_overlaps_when_slots_allow(
    authed: AsyncClient, llm: RoutedLLM
):
    llm.scripts = [reply(calls=[agent("e1"), agent("e2")]), reply("ok")]
    for k in ("e1", "e2"):
        llm.routes[k] = [[0.1, *reply(f"{k} done")]]
    await chat(authed, await session(authed))
    assert llm.peak == 2


async def test_stop_cancels_running_children(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    never = asyncio.Event()
    llm.scripts = [reply(calls=[agent("k1"), agent("k2")])]
    for k in ("k1", "k2"):
        llm.routes[k] = [[never, *reply("late")]]
    sid = await session(authed)
    task = start_chat(authed, sid)
    await until(lambda: llm.active == 2)
    assert (await authed.post(f"/v1/sessions/{sid}/stop")).json()["stopped"] is True
    ev = parse_sse((await asyncio.wait_for(task, 5)).text)
    assert ev[-1] == {"type": "done", "stop_reason": "cancelled"}
    await until(lambda: llm.active == 0)
    await assert_transcript_paired(authed, sid)
    # the turn slot is free again
    llm.scripts = [reply("again")]
    assert (await chat(authed, sid))[-1]["stop_reason"] == "end_turn"


async def test_stop_while_a_child_waits_for_approval(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [reply(calls=[agent("k-ap", "Verifier")])]
    llm.routes["k-ap"] = [reply(calls=[bash("echo hi")])]
    sid = await session(authed, "default")
    task = start_chat(authed, sid)
    await until(lambda: bool(app.state.approvals.pending_ids()))
    await authed.post(f"/v1/sessions/{sid}/stop")
    ev = parse_sse((await asyncio.wait_for(task, 5)).text)
    assert ev[-1]["stop_reason"] == "cancelled"
    assert app.state.approvals.pending_ids() == []
    await assert_transcript_paired(authed, sid)
