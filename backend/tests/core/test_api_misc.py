from pathlib import Path

from backend.core.exceptions import DomainException
from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from helpers import new_session, parse_sse, start_chat
from httpx import AsyncClient

SRC = "def add(a, b):\n    return a - b\n"


async def test_max_iterations_guard(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    app.state.react._max = 2
    llm.scripts = [reply(calls=[("Glob", {"pattern": "*"})]) for _ in range(5)]
    sid = await new_session(authed)
    ev = parse_sse((await start_chat(authed, sid)).text)
    assert ev[-1] == {"type": "done", "stop_reason": "max_iterations"}


async def test_unknown_and_invalid_tool_calls_become_errors(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [
        reply(calls=[("Nope", {}), ("Read", {})]),
        reply("fine"),
    ]
    sid = await new_session(authed)
    ev = parse_sse((await start_chat(authed, sid)).text)
    results = [e["result"] for e in ev if e["type"] == "tool_result"]
    assert all(r["is_error"] for r in results)
    assert len(results) == 2


async def test_llm_down_emits_error_event(authed: AsyncClient, llm: ScriptedLLM):
    async def boom(*_a, **_k):
        raise DomainException(4000)
        yield

    llm.stream = boom  # type: ignore[method-assign]
    sid = await new_session(authed)
    ev = parse_sse((await start_chat(authed, sid)).text)
    assert ev[-2]["code"] == 4000
    assert ev[-1]["stop_reason"] == "error"


async def test_auth_required_everywhere(client: AsyncClient):
    for method, path in [
        ("post", "/v1/sessions"),
        ("get", "/v1/sessions/S/messages"),
        ("post", "/v1/sessions/S/mode"),
        ("post", "/v1/sessions/S/chat"),
        ("post", "/v1/sessions/S/stop"),
        ("post", "/v1/approvals/A/resolve"),
    ]:
        r = await getattr(client, method)(path)
        assert r.status_code == 401, path
        assert r.json()[0]["code"] == 1001


async def test_session_crud_and_errors(authed: AsyncClient):
    sid = await new_session(authed)
    r = await authed.post(f"/v1/sessions/{sid}/mode", json={"mode": "plan"})
    assert r.json()["mode"] == "plan"
    assert r.json()["id"] == sid
    assert (
        await authed.post(f"/v1/sessions/{sid}/mode", json={"mode": "x"})
    ).status_code == 422
    assert (await authed.get("/v1/sessions/SNOPE/messages")).json()[0]["code"] == 2000
    r = await authed.post("/v1/sessions/SNOPE/chat", json={"message": "hi"})
    assert r.status_code == 404
    r = await authed.post("/v1/approvals/ANOPE/resolve", json={"decision": "allow"})
    assert r.status_code == 404
    assert r.json()[0]["code"] == 3003
    assert any(s["id"] == sid for s in (await authed.get("/v1/sessions")).json())


async def test_title_set_from_first_message(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply("hi")]
    sid = await new_session(authed)
    await start_chat(authed, sid, "  Fix the   parser please ")
    listed = {s["id"]: s for s in (await authed.get("/v1/sessions")).json()}
    assert listed[sid]["title"] == "Fix the parser please"


async def test_ready_checks_sandbox_and_llm(client: AsyncClient, llm: ScriptedLLM):
    assert (await client.get("/ready")).status_code == 200
    llm.healthy = False
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()[0]["code"] == 1008
    assert (await client.get("/health")).status_code == 200
