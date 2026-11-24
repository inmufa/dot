import asyncio

from agent_helpers import (
    RoutedLLM,
    assert_paired,
    assert_transcript_paired,
    results,
    session,
)
from backend.routing.clients.scripted import reply
from fastapi import FastAPI
from helpers import parse_sse, start_chat, types, until
from httpx import AsyncClient

OPTS = [
    {"label": "Postgres", "description": "heavy"},
    {"label": "SQLite", "description": "light"},
]
ASK = {"question": "Which database?", "options": OPTS}


async def _answer(authed, app, **body):
    await until(lambda: bool(app.state.agent.questions.pending_ids()))
    qid = app.state.agent.questions.pending_ids()[0]
    return qid, await authed.post(f"/v1/questions/{qid}/answer", json=body)


async def test_question_event_and_answer_reach_the_model(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [reply(calls=[("AskUserQuestion", ASK)]), reply("using sqlite")]
    sid = await session(authed)
    task = start_chat(authed, sid)
    qid, r = await _answer(authed, app, selected=["SQLite"], other=None)
    assert r.json() == {"ok": True}
    ev = parse_sse((await task).text)
    q = next(e for e in ev if e["type"] == "question")
    assert q["question_id"] == qid
    assert q["multi_select"] is False
    assert q["options"][0] == {"label": "Postgres", "description": "heavy"}
    assert types(ev).index("tool_call") < types(ev).index("question")
    assert types(ev).index("question") < types(ev).index("tool_result")
    assert_paired(ev)
    assert results(ev)[0]["output"] == "User answered. Selected: SQLite"
    assert ev[-1]["stop_reason"] == "end_turn"


async def test_other_free_text_and_multi_select(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [
        reply(calls=[("AskUserQuestion", {**ASK, "multi_select": True})]),
        reply("ok"),
    ]
    task = start_chat(authed, await session(authed))
    await _answer(authed, app, selected=["Postgres", "SQLite"], other="and DuckDB")
    out = results(parse_sse((await task).text))[0]["output"]
    assert (
        out
        == "User answered. Selected: Postgres; SQLite. Other (free text): and DuckDB"
    )


async def test_invalid_answers_are_rejected_and_question_stays_open(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [reply(calls=[("AskUserQuestion", ASK)]), reply("ok")]
    task = start_chat(authed, await session(authed))
    qid, bad = await _answer(authed, app, selected=["Mongo"])
    assert bad.status_code == 400
    assert bad.json()[0]["code"] == 2005
    two = await authed.post(
        f"/v1/questions/{qid}/answer", json={"selected": ["Postgres", "SQLite"]}
    )
    assert two.status_code == 400  # single select
    empty = await authed.post(f"/v1/questions/{qid}/answer", json={"selected": []})
    assert empty.status_code == 400
    assert app.state.agent.questions.pending_ids() == [qid]
    ok = await authed.post(
        f"/v1/questions/{qid}/answer", json={"selected": [], "other": "x"}
    )
    assert ok.status_code == 200
    await task
    again = await authed.post(
        f"/v1/questions/{qid}/answer", json={"selected": ["SQLite"]}
    )
    assert again.status_code == 404
    assert again.json()[0]["code"] == 2003


async def test_bad_options_are_a_tool_error_without_event(
    authed: AsyncClient, llm: RoutedLLM
):
    one = {"question": "q", "options": [{"label": "a"}]}
    dup = {"question": "q", "options": [{"label": "a"}, {"label": "a"}]}
    llm.scripts = [
        reply(calls=[("AskUserQuestion", one)]),
        reply(calls=[("AskUserQuestion", dup)]),
        reply("ok"),
    ]
    resp = await authed.post(
        f"/v1/sessions/{await session(authed)}/chat", json={"message": "go"}
    )
    ev = parse_sse(resp.text)
    assert "question" not in types(ev)
    assert all(r["is_error"] for r in results(ev))


async def test_unanswered_question_times_out_into_an_error_result(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    app.state.agent.question_timeout_s = 0.2
    llm.scripts = [reply(calls=[("AskUserQuestion", ASK)]), reply("ok")]
    resp = await authed.post(
        f"/v1/sessions/{await session(authed)}/chat", json={"message": "go"}
    )
    ev = parse_sse(resp.text)
    r = results(ev)[0]
    assert r["is_error"]
    assert "did not answer in time" in r["output"]
    assert ev[-1]["stop_reason"] == "end_turn"  # the turn goes on
    assert app.state.agent.questions.pending_ids() == []


async def test_stop_cancels_a_waiting_question(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    llm.scripts = [reply(calls=[("AskUserQuestion", ASK)])]
    sid = await session(authed)
    task = start_chat(authed, sid)
    await until(lambda: bool(app.state.agent.questions.pending_ids()))
    stopped = await authed.post(f"/v1/sessions/{sid}/stop")
    assert stopped.json()["stopped"] is True
    ev = parse_sse((await asyncio.wait_for(task, 5)).text)
    assert ev[-1] == {"type": "done", "stop_reason": "cancelled"}
    await assert_transcript_paired(authed, sid)
    assert app.state.agent.questions.pending_ids() == []
