import asyncio

import httpx
import pytest
from backend.core.exceptions import DomainException
from backend.routing.clients.llama_client import LlamaClient
from backend.routing.clients.scripted import ScriptedLLM, reply
from backend.sessions.services.compaction.tokens import ContextMeter
from compaction_helpers import chat, msg, session
from helpers import start_chat, until
from httpx import AsyncClient


async def test_manual_compact_folds_history_and_reports_tokens(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("first answer " * 20), reply("second answer " * 20)]
    sid = await session(authed)
    await chat(authed, sid, "one")
    await chat(authed, sid, "two")
    r = await authed.post(f"/v1/sessions/{sid}/compact")
    body = r.json()
    assert r.status_code == 200
    assert body["compacted"] is True
    assert body["stages"] == ["summary"]
    assert body["tokens_after"] > 0
    assert body["tokens_before"] >= body["tokens_after"]
    live = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert any(m["role"] == "summary" for m in live)
    # the next turn works on top of the summary
    llm.scripts = [reply("third")]
    ev = await chat(authed, sid, "three")
    assert ev[-1]["stop_reason"] == "end_turn"
    assert "SUMMARY-ONE" in llm.requests[-1]["messages"][1]["content"]


async def test_manual_compact_on_an_empty_session_does_nothing(authed: AsyncClient):
    sid = await session(authed)
    body = (await authed.post(f"/v1/sessions/{sid}/compact")).json()
    assert body["compacted"] is False
    assert body["reason"] == "nothing to compact"


async def test_manual_compact_unknown_session_and_busy(
    authed: AsyncClient, llm: ScriptedLLM
):
    r = await authed.post("/v1/sessions/SNOPE/compact")
    assert r.status_code == 404
    gate = asyncio.Event()
    llm.scripts = [[gate, *reply("late")]]
    sid = await session(authed)
    task = start_chat(authed, sid)
    await until(lambda: len(llm.requests) == 1)
    busy = await authed.post(f"/v1/sessions/{sid}/compact")
    assert busy.status_code == 409
    gate.set()
    await task


async def test_manual_compact_reports_llm_failure_as_2020(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("a"), reply("b")]
    sid = await session(authed)
    await chat(authed, sid, "one")
    await chat(authed, sid, "two")

    async def boom(*_a, **_k) -> str:
        raise DomainException(4000)

    llm.complete = boom  # type: ignore[method-assign]
    r = await authed.post(f"/v1/sessions/{sid}/compact")
    assert r.status_code == 502
    assert r.json()[0]["code"] == 2020
    assert not any(
        m["role"] == "summary"
        for m in (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    )


async def test_context_endpoint_breaks_down_tiers_and_history(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("a " * 200), reply("b " * 200)]
    sid = await session(authed)
    await chat(authed, sid, "one")
    await chat(authed, sid, "two")
    await authed.post(f"/v1/sessions/{sid}/compact")
    ctx = (await authed.get(f"/v1/sessions/{sid}/context")).json()
    assert ctx["limit"] == 7200
    assert ctx["threshold"] == 5400
    assert ctx["used"] > 0
    assert ctx["source"] in ("reported", "estimated")
    assert ctx["tiers"]["prefix"] > 100
    assert ctx["tiers"]["global"] > 0
    assert set(ctx["messages"]) <= {"user", "assistant", "tool", "summary"}
    assert ctx["messages"]["summary"] > 0
    (rec,) = ctx["compactions"]
    assert rec["trigger"] == "manual"
    assert rec["stages"] == ["summary"]
    assert rec["undone"] is False
    assert rec["summary_seq"]
    assert (await authed.get("/v1/sessions/SNOPE/context")).status_code == 404


def test_meter_prefers_the_reported_size_plus_new_rows():
    meter = ContextMeter()
    rows = [msg(1, "user", "a" * 400), msg(2, "assistant", "b" * 400)]
    tokens, source = meter.estimate(1, 50, rows)
    assert source == "estimated"
    assert tokens > 200
    meter.observe(1, 5000, seq=2)
    rows.append(msg(3, "tool", "c" * 4000, call_id="x"))
    tokens, source = meter.estimate(1, 50, rows)
    assert source == "reported"
    assert 5000 + 1000 <= tokens < 5000 + 1100  # reported + only the new row
    meter.observe(1, None, seq=3)  # no report keeps the previous one
    assert meter.estimate(1, 50, rows)[1] == "reported"
    meter.reset(1)
    assert meter.estimate(1, 50, rows)[1] == "estimated"


def _client(handler) -> LlamaClient:
    transport = httpx.MockTransport(handler)
    return LlamaClient("http://llm/v1", client=httpx.AsyncClient(transport=transport))


async def test_llama_complete_returns_text_without_reasoning():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = req.content
        content = "<think>hmm</think>the summary"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )

    out = await _client(handler).complete([{"role": "user", "content": "x"}])
    assert out == "the summary"
    assert b'"stream":false' in seen["body"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, text="not json"),
    ],
)
async def test_llama_complete_failures_raise_4000(response):
    with pytest.raises(DomainException) as exc:
        await _client(lambda _r: response).complete([])
    assert exc.value.code == 4000
