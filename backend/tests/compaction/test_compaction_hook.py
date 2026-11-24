import json
from pathlib import Path

from backend.routing.clients.scripted import ScriptedLLM, reply
from compaction_helpers import chat, check_pairing, make_files, session, write_hook
from httpx import AsyncClient

LOG = 'cat >> hook_log.jsonl; echo >> hook_log.jsonl; echo "not now" >&2; exit 2'


async def test_blocking_precompact_hook_skips_compaction_and_turn_continues(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    write_hook(ws, "PreCompact", LOG)
    files = make_files(ws, 7)
    llm.scripts = [
        *[reply(calls=[("Read", {"file_path": str(p)})]) for p in files],
        reply("fine"),
    ]
    sid = await session(authed)
    events = await chat(authed, sid, "read all")
    assert events[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert all(e["type"] != "compaction" for e in events)
    assert not llm.complete_requests
    lines = [x for x in (ws / "hook_log.jsonl").read_text().splitlines() if x]
    assert len(lines) == 1  # asked once this turn, then left alone
    payload = json.loads(lines[0])
    assert payload["hook_event_name"] == "PreCompact"
    assert payload["trigger"] == "auto"
    for r in llm.requests:
        check_pairing(r["messages"])
    # nothing was folded: no summary row, no compacted rows
    rows = (await authed.get(f"/v1/sessions/{sid}/messages?include_compacted=1")).json()
    assert not any(r["compacted"] or r["role"] == "summary" for r in rows)


async def test_manual_compact_is_blocked_by_the_hook_too(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    write_hook(ws, "PreCompact", LOG)
    llm.scripts = [reply("a"), reply("b")]
    sid = await session(authed)
    await chat(authed, sid, "one")
    await chat(authed, sid, "two")
    r = await authed.post(f"/v1/sessions/{sid}/compact")
    assert r.status_code == 200
    assert r.json()["compacted"] is False
    assert r.json()["reason"] == "blocked"
    payload = json.loads((ws / "hook_log.jsonl").read_text().splitlines()[0])
    assert payload["trigger"] == "manual"


async def test_non_blocking_hook_lets_compaction_run(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    write_hook(ws, "PreCompact", "cat > hook_in.json")
    files = make_files(ws, 7)
    llm.scripts = [
        *[reply(calls=[("Read", {"file_path": str(p)})]) for p in files],
        reply("fine"),
    ]
    events = await chat(authed, await session(authed), "read all")
    assert any(e["type"] == "compaction" for e in events)
    assert json.loads((ws / "hook_in.json").read_text())["tokens"] > 3000
