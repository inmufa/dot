import asyncio

from backend.routing.clients.scripted import ScriptedLLM, reply
from helpers import parse_sse
from httpx import AsyncClient
from sess_helpers import chat, make, rows


async def test_regenerate_reruns_the_last_user_message(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("first try"), reply("second try")]
    sid = await make(authed)
    await chat(authed, sid, "question")
    r = await authed.post(f"/v1/sessions/{sid}/regenerate")
    ev = parse_sse(r.text)
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    msgs = await rows(authed, sid)
    assert [m["content"] for m in msgs] == ["question", "second try"]
    hidden = (await authed.get(f"/v1/sessions/{sid}/messages?include_rewound=1")).json()
    assert [m["content"] for m in hidden if m["rewound"]] == ["question", "first try"]
    # the model saw the question exactly once
    sent = llm.requests[-1]["messages"]
    assert sum(1 for m in sent if m["role"] == "user") == 1


async def test_regenerate_after_tools_drops_the_whole_turn(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [
        reply("", [("Glob", {"pattern": "*.x"})]),
        reply("v1"),
        reply("v2"),
    ]
    sid = await make(authed)
    await chat(authed, sid, "go")
    await authed.post(f"/v1/sessions/{sid}/regenerate")
    assert [m["role"] for m in await rows(authed, sid)] == ["user", "assistant"]


async def test_regenerate_needs_a_finished_turn(authed: AsyncClient):
    sid = await make(authed)
    r = await authed.post(f"/v1/sessions/{sid}/regenerate")
    assert r.status_code == 409
    assert r.json()[0]["code"] == 2032


async def test_regenerate_reruns_a_turn_that_failed_before_a_reply(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [[RuntimeError("llm down")], reply("answer")]
    sid = await make(authed)
    await chat(authed, sid, "question")
    assert [m["role"] for m in await rows(authed, sid)] == ["user"]
    r = await authed.post(f"/v1/sessions/{sid}/regenerate")
    assert parse_sse(r.text)[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert [m["content"] for m in await rows(authed, sid)] == ["question", "answer"]


async def test_regenerate_is_busy_while_a_turn_runs(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("a")]
    sid = await make(authed)
    await chat(authed, sid, "q")
    gate = asyncio.Event()
    llm.scripts = [[gate, *reply("b")]]
    task = asyncio.create_task(authed.post(f"/v1/sessions/{sid}/regenerate"))
    await asyncio.sleep(0.1)
    r = await authed.post(f"/v1/sessions/{sid}/regenerate")
    assert r.status_code == 409
    gate.set()
    await task


async def test_regenerate_restore_files_undoes_the_turn_writes(
    authed: AsyncClient, llm: ScriptedLLM, ws
):
    target = ws / "made.txt"
    llm.scripts = [
        reply("", [("Write", {"file_path": str(target), "content": "hello"})]),
        reply("wrote it"),
        reply("no file this time"),
    ]
    sid = await make(authed)
    await chat(authed, sid, "make a file")
    assert target.exists()
    r = await authed.post(
        f"/v1/sessions/{sid}/regenerate", json={"restore_files": True}
    )
    assert parse_sse(r.text)[-1]["stop_reason"] == "end_turn"
    assert not target.exists()


async def test_regenerate_keeps_files_by_default(
    authed: AsyncClient, llm: ScriptedLLM, ws
):
    target = ws / "kept.txt"
    llm.scripts = [
        reply("", [("Write", {"file_path": str(target), "content": "hello"})]),
        reply("wrote it"),
        reply("again"),
    ]
    sid = await make(authed)
    await chat(authed, sid, "make a file")
    await authed.post(f"/v1/sessions/{sid}/regenerate")
    assert target.exists()
