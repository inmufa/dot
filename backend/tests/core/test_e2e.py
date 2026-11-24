import asyncio
import itertools
import json
from pathlib import Path

from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from helpers import new_session, parse_sse, resolve_next, start_chat, types, until
from httpx import AsyncClient

SRC = "def add(a, b):\n    return a - b\n"


async def test_full_slice_read_edit_test_answer(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    target = ws / "app.py"
    target.write_text(SRC)
    check = "python3 -c \"import app; assert app.add(1, 2) == 3; print('PASS')\""
    llm.scripts = [
        reply(
            "looking",
            [("Read", {"file_path": str(target)}), ("Glob", {"pattern": "*.py"})],
            thinking="hm",
        ),
        reply(
            calls=[
                (
                    "Edit",
                    {
                        "file_path": str(target),
                        "old_string": "a - b",
                        "new_string": "a + b",
                    },
                )
            ]
        ),
        reply(calls=[("Bash", {"command": check})]),
        reply("Fixed add(); the check passes."),
    ]
    sid = await new_session(authed)
    task = start_chat(authed, sid, "fix add")
    await resolve_next(app, authed, "allow")  # Edit
    await resolve_next(app, authed, "allow")  # Bash
    resp = await task
    assert resp.headers["content-type"].startswith("text/event-stream")
    ev = parse_sse(resp.text)
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert any(e["type"] == "token" and e["thinking"] for e in ev)
    assert types(ev).count("approval_required") == 2
    assert types(ev).count("usage") == 4
    results = [e["result"] for e in ev if e["type"] == "tool_result"]
    assert len(results) == 4
    assert "a - b" in results[0]["output"]
    assert "PASS" in results[3]["output"]
    assert not any(r["is_error"] for r in results)
    assert target.read_text() == SRC.replace("a - b", "a + b")

    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert [m["role"] for m in msgs] == [
        "user",
        "assistant",
        "tool",
        "tool",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert [m["seq"] for m in msgs] == list(range(1, 10))
    assert "<system-reminder>" not in msgs[0]["content"]
    sent = llm.requests
    assert len({json.dumps(r["messages"][0]) for r in sent}) == 1
    assert "<system-reminder>" in sent[0]["messages"][1]["content"]
    assert "--- CACHE_BOUNDARY ---" in sent[0]["messages"][0]["content"]
    # history is append-only: each request extends the previous one
    for prev, nxt in itertools.pairwise(sent):
        assert nxt["messages"][: len(prev["messages"])] == prev["messages"]


async def test_plan_mode_refuses_write(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "x.txt"), "content": "hi"})]),
        reply("I will only plan."),
    ]
    sid = await new_session(authed, "plan")
    ev = parse_sse((await start_chat(authed, sid)).text)
    result = next(e["result"] for e in ev if e["type"] == "tool_result")
    assert result["is_error"]
    assert "3000" in result["output"]
    assert "approval_required" not in types(ev)
    assert not (ws / "x.txt").exists()


async def test_reject_path(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    target = ws / "a.py"
    target.write_text(SRC)
    llm.scripts = [
        reply(calls=[("Read", {"file_path": str(target)})]),
        reply(
            calls=[
                (
                    "Edit",
                    {
                        "file_path": str(target),
                        "old_string": "a - b",
                        "new_string": "a + b",
                    },
                )
            ]
        ),
        reply("ok, leaving it"),
    ]
    sid = await new_session(authed)
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "reject")
    ev = parse_sse((await task).text)
    approval = next(e for e in ev if e["type"] == "approval_required")
    assert approval["diff"] == "- a - b\n+ a + b"
    assert [e for e in ev if e["type"] == "tool_result"][-1]["result"]["is_error"]
    assert target.read_text() == SRC


async def test_always_allows_repeat_in_session(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    f = ws / "n.txt"
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(f), "content": "1"})]),
        reply(calls=[("Write", {"file_path": str(ws / "m.txt"), "content": "2"})]),
        reply("done"),
    ]
    sid = await new_session(authed)
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "always")
    ev = parse_sse((await task).text)
    assert types(ev).count("approval_required") == 1
    assert (ws / "m.txt").read_text() == "2"


async def test_bypass_and_accept_edits_skip_prompts(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    for mode in ("bypass", "acceptEdits"):
        llm.scripts = [
            reply(
                calls=[
                    ("Write", {"file_path": str(ws / f"{mode}.txt"), "content": "z"})
                ]
            ),
            reply("ok"),
        ]
        sid = await new_session(authed, mode)
        ev = parse_sse((await start_chat(authed, sid)).text)
        assert "approval_required" not in types(ev)
        assert (ws / f"{mode}.txt").exists()


async def test_stop_cancels_turn_and_keeps_transcript_valid(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    gate = asyncio.Event()
    llm.scripts = [[*reply("thinking...")[:-1], gate, *reply("never")]]
    sid = await new_session(authed)
    task = start_chat(authed, sid)
    await until(lambda: len(llm.requests) == 1)
    busy = await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "again"})
    assert busy.status_code == 409
    assert busy.json()[0]["code"] == 2001
    stop = await authed.post(f"/v1/sessions/{sid}/stop")
    assert stop.json() == {"ok": True, "stopped": True}
    ev = parse_sse((await task).text)
    assert ev[-1] == {"type": "done", "stop_reason": "cancelled"}
    assert not app.state.turns.is_active(sid)
    llm.scripts = [reply("fresh")]
    ev = parse_sse((await start_chat(authed, sid)).text)  # session usable again
    assert ev[-1]["stop_reason"] == "end_turn"


async def test_stop_while_waiting_for_approval(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "q.txt"), "content": "x"})])
    ]
    sid = await new_session(authed)
    task = start_chat(authed, sid)
    await until(lambda: bool(app.state.approvals.pending_ids()))
    await authed.post(f"/v1/sessions/{sid}/stop")
    ev = parse_sse((await task).text)
    assert ev[-1]["stop_reason"] == "cancelled"
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert msgs[-1]["role"] == "tool"
    assert "Cancelled" in msgs[-1]["content"]
    assert not (ws / "q.txt").exists()


async def test_approval_timeout_3001(authed: AsyncClient, llm: ScriptedLLM, ws: Path):
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "t.txt"), "content": "x"})])
    ]
    sid = await new_session(authed)
    ev = parse_sse((await start_chat(authed, sid)).text)
    assert ev[-1] == {"type": "done", "stop_reason": "approval_timeout"}
    assert ev[-2]["type"] == "error"
    assert ev[-2]["code"] == 3001
    assert not (ws / "t.txt").exists()


async def test_malformed_tool_json_retries_once(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    (ws / "r.txt").write_text("hello")
    llm.scripts = [
        reply(calls=[("Read", "{not json")]),
        reply(calls=[("Read", {"file_path": str(ws / "r.txt")})]),
        reply("read it"),
    ]
    sid = await new_session(authed)
    ev = parse_sse((await start_chat(authed, sid)).text)
    assert ev[-1]["stop_reason"] == "end_turn"
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert "not valid" in msgs[2]["content"]


async def test_malformed_twice_is_error_4003(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply(calls=[("Read", "{bad")]), reply(calls=[("Read", "{bad")])]
    sid = await new_session(authed)
    ev = parse_sse((await start_chat(authed, sid)).text)
    assert ev[-2]["code"] == 4003
    assert ev[-1]["stop_reason"] == "error"
