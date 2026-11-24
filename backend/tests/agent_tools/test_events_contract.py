from agent_helpers import RoutedLLM, assert_paired, chat, results, session
from backend.core.error_messages import CATALOG
from backend.routing.clients.scripted import reply
from dot_contracts.events import (
    ApprovalRequiredEvent,
    QuestionEvent,
    StreamEvent,
    SubagentEvent,
)
from pydantic import TypeAdapter

ADAPTER: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)


def test_new_events_roundtrip_and_stay_additive():
    q = ADAPTER.validate_python(
        {
            "type": "question",
            "question_id": "Q1",
            "question": "?",
            "options": [{"label": "a"}, {"label": "b", "description": "bb"}],
        }
    )
    assert isinstance(q, QuestionEvent)
    assert q.multi_select is False
    assert q.options[0].description == ""
    s = ADAPTER.validate_json(
        '{"type":"subagent","label":"Explore 1","subagent_type":"Explore","status":"queued"}'
    )
    assert isinstance(s, SubagentEvent)
    assert s.detail == ""
    old = ADAPTER.validate_python(
        {
            "type": "approval_required",
            "approval_id": "A1",
            "invocation": {"call_id": "c", "name": "Bash"},
        }
    )
    assert isinstance(old, ApprovalRequiredEvent)
    assert old.subagent is None


def test_error_codes_are_translated():
    for code in (2003, 2004, 2005, 4004):
        assert set(CATALOG[code]["messages"]) == {"en", "ru", "uz"}


async def test_child_approval_timeout_is_an_error_report_not_a_crash(
    authed, llm: RoutedLLM
):
    call = (
        "Agent",
        {"description": "d", "prompt": "k-to", "subagent_type": "Verifier"},
    )
    llm.scripts = [reply(calls=[call]), reply("recovered")]
    llm.routes["k-to"] = [reply(calls=[("Bash", {"command": "echo hi"})])]
    ev = await chat(
        authed, await session(authed, "default")
    )  # approvals time out at 0.3 s
    out = results(ev)[0]
    assert out["is_error"]
    assert "3001" in out["output"]
    assert_paired(ev)
