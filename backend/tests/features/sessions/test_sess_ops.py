import json

from backend.routing.clients.scripted import ScriptedLLM, reply
from helpers import parse_sse
from httpx import AsyncClient
from sess_helpers import chat, make, rows


async def test_btw_streams_and_stores_nothing(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply("main answer"), reply("side answer")]
    sid = await make(authed)
    await chat(authed, sid, "main question")
    before = await rows(authed, sid)
    r = await authed.post(f"/v1/sessions/{sid}/btw", json={"question": "quick one?"})
    ev = parse_sse(r.text)
    assert "".join(e["text"] for e in ev if e["type"] == "token") == "side answer"
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert await rows(authed, sid) == before
    last = llm.requests[-1]
    assert last["tools"] == []
    assert last["options"].thinking is False
    assert any("main question" in str(m["content"]) for m in last["messages"])
    assert "quick one?" in last["messages"][-1]["content"]
    assert (await authed.get("/v1/sessions?q=quick")).json() == []


async def test_btw_does_not_claim_the_session(
    authed: AsyncClient, llm: ScriptedLLM, app
):
    llm.scripts = [reply("x")]
    sid = await make(authed)
    app.state.turns.claim(sid)
    try:
        r = await authed.post(f"/v1/sessions/{sid}/btw", json={"question": "hi"})
        assert r.status_code == 200
    finally:
        app.state.turns.release(sid)


async def test_export_markdown_and_json(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [
        reply("", [("Glob", {"pattern": "*.x"})], thinking="secret thoughts"),
        reply("final words"),
    ]
    sid = await make(authed)
    await chat(authed, sid, "do the thing")
    r = await authed.get(f"/v1/sessions/{sid}/export")
    assert r.headers["content-disposition"].startswith("attachment")
    md = r.text
    assert "## User" in md
    assert "do the thing" in md
    assert "<details><summary>Tool: Glob</summary>" in md
    assert "final words" in md
    assert "secret thoughts" not in md
    with_thinking = (
        await authed.get(f"/v1/sessions/{sid}/export?include_thinking=1")
    ).text
    assert "secret thoughts" in with_thinking
    data = (await authed.get(f"/v1/sessions/{sid}/export?format=json")).json()
    assert data["id"] == sid
    assert [m["role"] for m in data["messages"]] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assert "secret thoughts" not in json.dumps(data)


async def test_export_rejects_unknown_format(authed: AsyncClient):
    sid = await make(authed)
    assert (
        await authed.get(f"/v1/sessions/{sid}/export?format=pdf")
    ).status_code == 422


async def test_usage_aggregates_stored_records(
    authed: AsyncClient, llm: ScriptedLLM, app
):
    sid = await make(authed)
    pk = (await app.state.agent.sessions.get(sid)).id
    await app.state.store.append(pk, "user", "q")
    for i, ms in enumerate((1000, 2000)):
        await app.state.store.append(
            pk,
            "assistant",
            f"u{i}",
            meta={
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "duration_ms": ms,
                    "effort": "high",
                }
            },
        )
    body = (await authed.get(f"/v1/sessions/{sid}/usage")).json()
    assert body["turns"] == 1
    assert body["prompt_tokens"] == 200
    assert body["completion_tokens"] == 40
    assert body["last_turn_ms"] == 2000
    assert body["tokens_per_s"] == 15.0
    assert body["efforts"] == {"high": 2}
    assert body["context_limit"] > 0


async def test_usage_without_records_is_zero(authed: AsyncClient):
    sid = await make(authed)
    body = (await authed.get(f"/v1/sessions/{sid}/usage")).json()
    assert body["turns"] == 0
    assert body["tokens_per_s"] is None


async def test_compact_focus_reaches_the_summary_prompt(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("a " * 40), reply("b " * 40)]
    sid = await make(authed)
    await chat(authed, sid, "one")
    await chat(authed, sid, "two")
    r = await authed.post(
        f"/v1/sessions/{sid}/compact", json={"focus": "the database schema"}
    )
    assert r.json()["compacted"] is True
    assert "the database schema" in llm.complete_requests[0][0]["content"]


async def test_commands_registry_lists_server_client_and_skills(authed: AsyncClient):
    cmds = (await authed.get("/v1/commands")).json()
    names = {c["name"]: c for c in cmds}
    for n in ("compact", "clear", "retry", "branch", "context", "usage", "btw"):
        assert names[n]["kind"] == "server"
        assert names[n]["endpoint"]["path"].startswith(("/v1/sessions/{id}", "/v1/"))
    for n in ("rename", "export", "resume", "effort", "model"):
        assert n in names
    assert names["retry"]["endpoint"]["stream"] is True
    assert names["help"]["kind"] == "client"
    assert names["compact"]["args"][0]["name"] == "focus"
    assert any(c["kind"] == "skill" and c["group"] == "skills" for c in cmds)
    assert all(c["available"] for c in cmds if c["kind"] != "skill")


async def test_commands_availability_follows_the_session(
    authed: AsyncClient, llm: ScriptedLLM
):
    sid = await make(authed)
    cmds = {
        c["name"]: c for c in (await authed.get(f"/v1/commands?session={sid}")).json()
    }
    assert cmds["retry"]["available"] is False
    assert cmds["retry"]["reason"]
    assert cmds["clear"]["available"] is True
    llm.scripts = [reply("a")]
    await chat(authed, sid, "q")
    cmds = {
        c["name"]: c for c in (await authed.get(f"/v1/commands?session={sid}")).json()
    }
    assert cmds["retry"]["available"] is True


async def test_commands_unknown_session_is_404(authed: AsyncClient):
    assert (await authed.get("/v1/commands?session=Sxxxxxxxxx")).status_code == 404
