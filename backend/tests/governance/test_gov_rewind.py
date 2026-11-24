import shutil
from pathlib import Path

import pytest
from backend.governance.models import Checkpoint
from backend.routing.clients.sandbox_client import SandboxClient, SandboxResponse
from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from gov_helpers import chat, results, session
from helpers import parse_sse, resolve_next, start_chat, until
from httpx import AsyncClient
from sqlalchemy import select


async def two_turns(c: AsyncClient, llm: ScriptedLLM, ws: Path) -> str:
    a, b = ws / "a.txt", ws / "b.txt"
    b.write_text("B0")
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(a), "content": "A1"})]),
        reply(calls=[("Read", {"file_path": str(b)})]),
        reply(
            calls=[
                ("Edit", {"file_path": str(b), "old_string": "B0", "new_string": "B1"})
            ]
        ),
        reply("t1 done"),
        reply(calls=[("Read", {"file_path": str(a)}), ("Read", {"file_path": str(b)})]),
        reply(
            calls=[
                ("Write", {"file_path": str(a), "content": "A2"}),
                ("Edit", {"file_path": str(b), "old_string": "B1", "new_string": "B2"}),
                ("Write", {"file_path": str(ws / "c.txt"), "content": "C"}),
            ]
        ),
        reply("t2 done"),
    ]
    sid = await session(c)
    await chat(c, sid, "turn one")
    await chat(c, sid, "turn two")
    assert (a.read_text(), b.read_text(), (ws / "c.txt").read_text()) == (
        "A2",
        "B2",
        "C",
    )
    return sid


async def msgs(c: AsyncClient, sid: str, query: str = "") -> list[dict]:
    return (await c.get(f"/v1/sessions/{sid}/messages{query}")).json()


async def test_rewind_to_turn_one_restores_turn_two_changes(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid = await two_turns(authed, llm, ws)
    all_rows = await msgs(authed, sid)
    first_user = all_rows[0]["seq"]
    turn_one_end = next(m["seq"] for m in all_rows if m["content"] == "t1 done")
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": first_user})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kept_through_seq"] == turn_one_end
    assert body["rewound_messages"] == len(all_rows) - turn_one_end
    # newest first: c.txt deleted, b.txt back to its turn-one state, a.txt too
    assert [(Path(f["path"]).name, f["action"]) for f in body["restored"]] == [
        ("c.txt", "deleted"),
        ("b.txt", "restored"),
        ("a.txt", "restored"),
    ]
    assert (ws / "a.txt").read_text() == "A1"
    assert (ws / "b.txt").read_text() == "B1"
    assert not (ws / "c.txt").exists()
    kept = await msgs(authed, sid)
    assert [m["seq"] for m in kept] == list(range(1, turn_one_end + 1))
    full = await msgs(authed, sid, "?include_rewound=1")
    assert len(full) == len(all_rows)  # nothing deleted
    assert [m["rewound"] for m in full] == [m["seq"] > turn_one_end for m in full]


async def test_rewind_zero_undoes_everything_and_is_idempotent(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid = await two_turns(authed, llm, ws)
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": 0})
    assert r.status_code == 200
    assert not (ws / "a.txt").exists()  # created in turn 1: deleted, not left at A1
    assert (ws / "b.txt").read_text() == "B0"
    assert not (ws / "c.txt").exists()
    assert await msgs(authed, sid) == []
    again = (await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": 0})).json()
    assert (again["rewound_messages"], again["restored"]) == (0, [])


async def test_rewound_history_is_not_sent_to_the_model_and_seq_continues(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid = await two_turns(authed, llm, ws)
    top = (await msgs(authed, sid))[-1]["seq"]
    await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": 1})
    llm.scripts = [reply("fresh")]
    await chat(authed, sid, "after rewind")
    sent = llm.requests[-1]["messages"]
    assert "turn two" not in str(sent)
    assert "turn one" in str(sent)
    assert "after rewind" in str(sent)
    last = (await msgs(authed, sid))[-1]
    assert last["seq"] == top + 2  # user row + assistant row after the old max


async def test_rewind_target_validation(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid = await two_turns(authed, llm, ws)
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": 9999})
    assert (r.status_code, r.json()[0]["code"]) == (400, 2002)
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": -1})
    assert r.status_code == 422
    r = await authed.post("/v1/sessions/SNOPE/rewind", json={"to_seq": 0})
    assert (r.status_code, r.json()[0]["code"]) == (404, 2000)
    r = await authed.post(
        f"/v1/sessions/{sid}/rewind", json={"to_seq": 1}, headers={"Authorization": "x"}
    )
    assert r.status_code == 401


async def test_mid_turn_target_keeps_the_whole_turn(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid = await two_turns(authed, llm, ws)
    rows = await msgs(authed, sid)
    mid = next(m["seq"] for m in rows if m["role"] == "tool")  # inside turn one
    r = (await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": mid})).json()
    assert r["kept_through_seq"] == next(
        m["seq"] for m in rows if m["content"] == "t1 done"
    )
    assert (ws / "a.txt").read_text() == "A1"


async def test_rewind_refused_while_a_turn_runs(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "x"), "content": "1"})]),
        reply("ok"),
    ]
    sid = await session(authed, "default")
    task = start_chat(authed, sid)
    await _until_pending(app)
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": 0})
    assert (r.status_code, r.json()[0]["code"]) == (409, 2001)
    await resolve_next(app, authed, "reject")
    await task
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": 0})
    assert r.status_code == 200


async def _until_pending(app: FastAPI) -> None:
    await until(lambda: bool(app.state.approvals.pending_ids()))


async def test_checkpoints_are_stored_in_the_workspace_and_recorded(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    sid = await two_turns(authed, llm, ws)
    stored = sorted(p.name for p in (ws / ".dot" / "checkpoints" / sid).iterdir())
    assert stored == [str(i) for i in range(1, 6)]  # 2 + 3 writes, numeric order
    async with app.state.sessions() as db:
        rows = (await db.scalars(select(Checkpoint).order_by(Checkpoint.id))).all()
    assert [r.sandbox_id for r in rows] == stored
    assert all(r.call_id.startswith("call_") for r in rows)
    assert [r.msg_seq for r in rows] == sorted(r.msg_seq for r in rows)


async def test_failed_checkpoint_blocks_the_write(
    authed: AsyncClient,
    llm: ScriptedLLM,
    ws: Path,
    sandbox: SandboxClient,
    monkeypatch: pytest.MonkeyPatch,
):
    real = sandbox.post

    async def flaky(session_id, path, payload, timeout_s=None):
        if path == "/internal/checkpoint":
            return SandboxResponse(500, {})
        return await real(session_id, path, payload, timeout_s)

    monkeypatch.setattr(sandbox, "post", flaky)
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "n"), "content": "x"})]),
        reply("ok"),
    ]
    ev = await chat(authed, await session(authed))
    (res,) = results(ev)
    assert res["is_error"]
    assert "Checkpoint failed" in res["output"]
    assert not (ws / "n").exists()


async def test_write_approval_carries_a_unified_diff(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    target = ws / "f.txt"
    target.write_text("one\ntwo\nthree\n")
    llm.scripts = [
        reply(calls=[("Read", {"file_path": str(target)})]),
        reply(
            calls=[("Write", {"file_path": str(target), "content": "one\n2\nthree\n"})]
        ),
        reply(
            calls=[("Write", {"file_path": str(ws / "new.txt"), "content": "hello\n"})]
        ),
        reply("ok"),
    ]
    sid = await session(authed, "default")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "allow")
    await resolve_next(app, authed, "allow")
    events = parse_sse((await task).text)
    diffs = [e["diff"] for e in events if e["type"] == "approval_required"]
    assert diffs[0].splitlines()[:2] == [f"--- {target}", f"+++ {target}"]
    assert "-two" in diffs[0]
    assert "+2" in diffs[0]
    assert "--- /dev/null" in diffs[1]
    assert "+hello" in diffs[1]
    # peeking for the diff must not satisfy read-before-edit
    assert target.read_text() == "one\n2\nthree\n"


async def test_pruned_checkpoint_fails_rewind_before_touching_any_file(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid = await two_turns(authed, llm, ws)
    rows = await msgs(authed, sid)
    # retention removed a snapshot in the middle of the turn-two set
    shutil.rmtree(ws / ".dot" / "checkpoints" / sid / "4")
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": rows[0]["seq"]})
    assert r.status_code >= 400
    assert r.json()[0]["code"] == 3004
    assert (ws / "a.txt").read_text() == "A2"  # nothing half restored
    assert (ws / "b.txt").read_text() == "B2"
    assert (ws / "c.txt").exists()
    assert len(await msgs(authed, sid)) == len(rows)  # transcript untouched
