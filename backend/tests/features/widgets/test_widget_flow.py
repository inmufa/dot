import asyncio
import hashlib
import json
from pathlib import Path

from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from helpers import new_session, parse_sse, start_chat, types, until
from httpx import AsyncClient

TABLE = {
    "kind": "table",
    "title": "Laptops",
    "props": {"columns": ["Name", "RAM"], "rows": [["A", "16"], ["B", "32"]]},
}
FORM = {
    "title": "Setup",
    "fields": [
        {"id": "db", "type": "single_select", "label": "DB", "options": ["pg", "lite"]},
        {"id": "tags", "type": "multi_select", "label": "T", "options": ["a", "b"]},
    ],
}


def _results(ev):
    return [e["result"] for e in ev if e["type"] == "tool_result"]


async def _pending(app: FastAPI) -> str:
    await until(lambda: bool(app.state.agent.questions.pending_ids()))
    return app.state.agent.questions.pending_ids()[0]


async def test_present_emits_widget_after_tool_call(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply(calls=[("Present", TABLE)]), reply("done")]
    sid = await new_session(authed)
    ev = parse_sse(
        (await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})).text
    )
    t = types(ev)
    assert t.index("tool_call") < t.index("widget") < t.index("tool_result")
    w = next(e for e in ev if e["type"] == "widget")
    assert w["kind"] == "table"
    assert w["title"] == "Laptops"
    assert w["props"]["rows"] == [["A", "16"], ["B", "32"]]
    assert w["call_id"] == "call_0_Present"
    res = _results(ev)[0]
    assert not res["is_error"]
    assert not res["tainted"]
    # history re-renders from the stored call arguments
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    stored = next(m for m in msgs if m["tool_calls"])["tool_calls"][0]["function"]
    assert "Laptops" in stored["arguments"]


async def test_invalid_present_is_a_tool_error_without_widget(
    authed: AsyncClient, llm: ScriptedLLM
):
    bad = {
        "kind": "table",
        "props": {"columns": ["A"], "rows": [["<script>x</script>"]]},
    }
    llm.scripts = [
        reply(calls=[("Present", bad)]),
        reply(calls=[("Present", TABLE)]),
        reply("ok"),
    ]
    sid = await new_session(authed)
    ev = parse_sse(
        (await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})).text
    )
    res = _results(ev)
    assert res[0]["is_error"]
    assert "HTML" in res[0]["output"]
    assert not res[1]["is_error"]
    assert types(ev).count("widget") == 1  # only the valid retry


async def test_present_in_plan_mode_and_no_approval_needed(
    authed: AsyncClient, llm: ScriptedLLM, app: FastAPI
):
    llm.scripts = [reply(calls=[("Present", TABLE)]), reply("ok")]
    sid = await new_session(authed, "plan")
    ev = parse_sse(
        (await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})).text
    )
    assert "widget" in types(ev)
    assert "approval_required" not in types(ev)


async def test_deny_rule_still_blocks_present(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    (ws / ".dot").mkdir(exist_ok=True)
    (ws / ".dot" / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["Present"]}})
    )
    llm.scripts = [reply(calls=[("Present", TABLE)]), reply("ok")]
    sid = await new_session(authed, "bypass")
    ev = parse_sse(
        (await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})).text
    )
    assert "widget" not in types(ev)
    assert _results(ev)[0]["is_error"]


async def test_ask_form_end_to_end(authed: AsyncClient, llm: ScriptedLLM, app: FastAPI):
    llm.scripts = [reply(calls=[("Ask", FORM)]), reply("thanks")]
    sid = await new_session(authed)
    task = start_chat(authed, sid)
    qid = await _pending(app)
    bad = await authed.post(
        f"/v1/questions/{qid}/answer", json={"values": {"db": "mongo", "tags": []}}
    )
    assert bad.status_code == 400
    assert bad.json()[0]["code"] == 2005
    legacy = await authed.post(f"/v1/questions/{qid}/answer", json={"selected": ["pg"]})
    assert legacy.status_code == 400  # form needs values
    ok = await authed.post(
        f"/v1/questions/{qid}/answer",
        json={"values": {"db": "lite", "tags": ["a", "b"]}},
    )
    assert ok.json() == {"ok": True}
    ev = parse_sse((await task).text)
    q = next(e for e in ev if e["type"] == "question")
    assert q["title"] == "Setup"
    assert q["options"] == []
    assert [f["id"] for f in q["fields"]] == ["db", "tags"]
    out = _results(ev)[0]["output"]
    assert out == 'User submitted: {"db": "lite", "tags": ["a", "b"]}'
    assert not _results(ev)[0]["tainted"]


async def test_values_for_legacy_question_rejected(
    authed: AsyncClient, llm: ScriptedLLM, app: FastAPI
):
    opts = {"question": "q?", "options": [{"label": "a"}, {"label": "b"}]}
    llm.scripts = [reply(calls=[("Ask", opts)]), reply("ok")]
    task = start_chat(authed, await new_session(authed))
    qid = await _pending(app)
    r = await authed.post(f"/v1/questions/{qid}/answer", json={"values": {"x": 1}})
    assert r.status_code == 400
    await authed.post(f"/v1/questions/{qid}/answer", json={"selected": ["a"]})
    await task


async def test_invalid_form_is_tool_error_no_event(
    authed: AsyncClient, llm: ScriptedLLM
):
    bad = {"fields": [{"id": "a", "type": "slider", "label": "x"}]}
    neither = {"title": "x"}
    llm.scripts = [
        reply(calls=[("Ask", bad)]),
        reply(calls=[("Ask", neither)]),
        reply("ok"),
    ]
    sid = await new_session(authed)
    ev = parse_sse(
        (await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})).text
    )
    assert "question" not in types(ev)
    assert all(r["is_error"] for r in _results(ev))


async def test_form_timeout_and_cancel(
    authed: AsyncClient, llm: ScriptedLLM, app: FastAPI
):
    app.state.agent.question_timeout_s = 0.2
    llm.scripts = [reply(calls=[("Ask", FORM)]), reply("ok")]
    sid = await new_session(authed)
    ev = parse_sse(
        (await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})).text
    )
    assert "did not answer in time" in _results(ev)[0]["output"]
    app.state.agent.question_timeout_s = 300
    llm.scripts = [reply(calls=[("Ask", FORM)])]
    task = start_chat(authed, sid)
    await _pending(app)
    await authed.post(f"/v1/sessions/{sid}/stop")
    ev = parse_sse((await asyncio.wait_for(task, 5)).text)
    assert ev[-1] == {"type": "done", "stop_reason": "cancelled"}
    assert app.state.agent.questions.pending_ids() == []


def test_subagents_get_neither_tool(app: FastAPI):
    from backend.cognition.services.subagents.types import TYPES, tool_names  # noqa: PLC0415

    names = [d.name for d in app.state.agent.registry.core_definitions()]
    assert {"Ask", "Present"} <= set(names)
    assert "AskUserQuestion" not in names
    for kind in TYPES.values():
        assert not {"Ask", "Present"} & set(tool_names(kind, names))


PREFIX_SHA = "e636ea10898119daf17578b54375381c4603a9002343e50700ae869dc9548684"


async def test_prefix_is_byte_stable_and_pinned(
    authed: AsyncClient, llm: ScriptedLLM, app: FastAPI
):
    before = app.state.react.prefix_text
    for mode in ("default", "plan"):
        llm.scripts = [reply(calls=[("Present", TABLE)]), reply("ok")]
        sid = await new_session(authed, mode)
        await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})
        await authed.post(f"/v1/sessions/{sid}/chat", json={"message": "again"})
        system = {r["messages"][0]["content"] for r in llm.requests}
        assert all(s.startswith(before) for s in system)
    assert app.state.react.prefix_text == before
    assert hashlib.sha256(before.encode()).hexdigest() == PREFIX_SHA
