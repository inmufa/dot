from pathlib import Path

from backend.governance.models import Checkpoint
from backend.routing.clients.scripted import ScriptedLLM, reply
from compaction_helpers import chat, check_pairing, make_files, session
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select


async def two_turns_with_compaction(
    c: AsyncClient, llm: ScriptedLLM, ws: Path
) -> tuple[str, Path]:
    a = ws / "a.txt"
    files = make_files(ws, 6, 3000)
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(a), "content": "A1"})]),
        reply("t1 done"),
        reply(calls=[("Read", {"file_path": str(a)})]),
        reply(
            calls=[
                ("Edit", {"file_path": str(a), "old_string": "A1", "new_string": "A2"})
            ]
        ),
        *[reply(calls=[("Read", {"file_path": str(p)})]) for p in files],
        reply("t2 done"),
    ]
    sid = await session(c)
    await chat(c, sid, "turn one")
    ev = await chat(c, sid, "turn two")
    assert any(e["type"] == "compaction" for e in ev)
    assert a.read_text() == "A2"
    return sid, a


async def seqs(c: AsyncClient, sid: str, query: str = "") -> list[dict]:
    return (await c.get(f"/v1/sessions/{sid}/messages{query}")).json()


async def test_rewind_below_a_compaction_uncompacts_and_restores_files(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid, a = await two_turns_with_compaction(authed, llm, ws)
    before = await seqs(authed, sid, "?include_compacted=1")
    assert any(m["compacted"] for m in before)
    end_t1 = next(m["seq"] for m in before if m["content"] == "t1 done")
    r = await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": end_t1})
    assert r.status_code == 200
    assert r.json()["kept_through_seq"] == end_t1
    assert a.read_text() == "A1"  # file restored from its checkpoint
    # turn one is whole again: the summary that had folded it was rewound
    live = await seqs(authed, sid)
    assert [m["role"] for m in live] == ["user", "assistant", "tool", "assistant"]
    assert not any(m["compacted"] for m in live)
    full = await seqs(authed, sid, "?include_compacted=1&include_rewound=1")
    assert any(m["role"] == "summary" and m["rewound"] for m in full)  # never deleted
    ctx = (await authed.get(f"/v1/sessions/{sid}/context")).json()
    assert ctx["compactions"]
    assert all(c["undone"] for c in ctx["compactions"])
    # the next turn sees the original turn one, with no summary
    llm.scripts = [reply("after rewind")]
    await chat(authed, sid, "turn three")
    sent = llm.requests[-1]["messages"]
    assert "SUMMARY-ONE" not in str(sent)
    assert "turn one" in sent[1]["content"]
    check_pairing(sent)


async def test_rewind_after_a_compaction_keeps_the_summary(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid, _ = await two_turns_with_compaction(authed, llm, ws)
    llm.scripts = [reply("t3 done")]
    await chat(authed, sid, "turn three")
    rows = await seqs(authed, sid, "?include_compacted=1")
    end_t2 = next(m["seq"] for m in rows if m["content"] == "t2 done")
    await authed.post(f"/v1/sessions/{sid}/rewind", json={"to_seq": end_t2})
    live = await seqs(authed, sid)
    assert any(m["role"] == "summary" for m in live)
    assert live[-1]["content"] == "t2 done"
    ctx = (await authed.get(f"/v1/sessions/{sid}/context")).json()
    assert not any(c["undone"] for c in ctx["compactions"])
    llm.scripts = [reply("t3 again")]
    await chat(authed, sid, "turn three again")
    sent = llm.requests[-1]["messages"]
    assert "SUMMARY-ONE" in sent[1]["content"]
    check_pairing(sent)


async def test_checkpoint_seqs_still_point_at_real_tool_rows(
    app: FastAPI, authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    sid, _ = await two_turns_with_compaction(authed, llm, ws)
    rows = {m["seq"]: m for m in await seqs(authed, sid, "?include_compacted=1")}
    async with app.state.sessions() as db:
        cps = list((await db.scalars(select(Checkpoint))).all())
    assert cps
    for cp in cps:
        assert rows[cp.msg_seq]["role"] == "tool"
        assert rows[cp.msg_seq]["tool_call_id"]
