import time

from backend.cognition.services.engine.turn import Turn, TurnOptions
from backend.cognition.services.research import ResearchMode
from backend.routing.clients.llm_types import ParsedToolCall
from backend.routing.clients.scripted import ScriptedLLM, reply
from backend.settings import Settings
from helpers import new_session, parse_sse, types
from httpx import AsyncClient

SEARCH = ("WebSearch", {"query": "python"})


def mode(settings: Settings, **kw) -> ResearchMode:
    return ResearchMode(settings.model_copy(update=kw))


def turn(research=True, seconds=None) -> Turn:
    return Turn(
        pk=1,
        public_id="S1",
        options=TurnOptions(research=research, research_seconds=seconds),
    )


def call(name="WebFetch") -> ParsedToolCall:
    return ParsedToolCall("c1", name, {})


async def test_reminder_states_protocol_and_budget(settings):
    text = await mode(settings).reminder(turn())
    for needle in (
        "3-6 short sub-questions",
        "[n]",
        "Sources",
        "Never invent",
        "3 minutes",
    ):
        assert needle in text
    assert "untrusted" in text


async def test_reminder_is_empty_without_research(settings):
    assert await mode(settings).reminder(turn(research=False)) == ""


async def test_seconds_default_request_and_cap(settings):
    m = mode(settings, research_max_s=600)
    assert m.seconds_for(turn()) == settings.research_default_s
    assert m.seconds_for(turn(seconds=60)) == 60
    assert m.seconds_for(turn(seconds=1800)) == 600


async def test_fetch_cap_refuses_after_n_reads(settings):
    m = mode(settings, research_fetch_cap=2)
    t = turn()
    await m.reminder(t)
    assert [m.gate(t, call()) for _ in range(2)] == [None, None]
    assert "limit" in (m.gate(t, call()) or "")
    assert "limit" in (m.gate(t, call("BrowserNavigate")) or "")
    assert m.gate(t, call("Read")) is None  # not a web tool


async def test_deadline_blocks_all_web_tools(settings):
    m = mode(settings)
    t = turn()
    await m.reminder(t)
    m._budgets[t.public_id].deadline = time.monotonic() - 1
    assert "time is up" in (m.gate(t, call("WebSearch")) or "")


async def test_no_gate_outside_research_or_for_subagents(settings):
    m = mode(settings, research_fetch_cap=1)
    t = turn(research=False)
    await m.reminder(t)
    assert all(m.gate(t, call()) is None for _ in range(5))
    sub = turn()
    await m.reminder(sub)
    sub.depth = 1
    assert all(m.gate(sub, call()) is None for _ in range(5))


async def test_chat_emits_sources_and_stores_them(
    authed: AsyncClient, web, llm: ScriptedLLM
):
    llm.scripts = [
        reply(calls=[SEARCH]),
        reply(calls=[("WebFetch", {"url": "https://b.example.org/y"})]),
        reply("Report [1][2]"),
    ]
    sid = await new_session(authed, "bypass")
    r = await authed.post(
        f"/v1/sessions/{sid}/chat", json={"message": "q", "research": True}
    )
    ev = parse_sse(r.text)
    src = [e for e in ev if e["type"] == "sources"]
    assert [[s["n"] for s in e["sources"]] for e in src] == [[1, 2], [2]]
    assert src[0]["sources"][0]["url"] == "https://a.example.com/x"
    assert "<system-reminder>" not in src[0]["sources"][0]["title"]
    i = types(ev).index("tool_result")
    assert types(ev)[i + 1] == "sources"
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    final = [m for m in msgs if m["role"] == "assistant"][-1]
    assert [s["n"] for s in final["meta"]["sources"]] == [1, 2]
    first_user = llm.requests[0]["messages"][-1]["content"]
    assert "RESEARCH MODE" in first_user


async def test_plain_turn_has_no_protocol(authed: AsyncClient, web, llm: ScriptedLLM):
    llm.scripts = [reply("hi")]
    sid = await new_session(authed)
    await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "hello"})
    assert "RESEARCH MODE" not in str(llm.requests[0]["messages"])


async def test_fetch_cap_end_to_end(authed: AsyncClient, web, llm: ScriptedLLM, app):
    app.state.settings.research_fetch_cap = 1
    fetch = ("WebFetch", {"url": "https://b.example.org/y"})
    llm.scripts = [reply(calls=[fetch]), reply(calls=[fetch]), reply("done")]
    sid = await new_session(authed, "bypass")
    r = await authed.post(
        f"/v1/sessions/{sid}/chat", json={"message": "q", "research": True}
    )
    results = [e["result"] for e in parse_sse(r.text) if e["type"] == "tool_result"]
    assert not results[0]["is_error"]
    assert results[1]["is_error"]
    assert "final cited report" in results[1]["output"]
