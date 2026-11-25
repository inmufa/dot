"""Research mode, projects and telemetry over real HTTP (fake llama, real sandbox)."""

import json

import httpx
import pytest
from drive import AUTH, new_session, run_turn
from fake_llama import FakeLlama, Turn

pytestmark = pytest.mark.integration


def _post_chat(base: str, sid: str, body: dict) -> list[dict]:
    url = f"{base}/v1/sessions/{sid}/chat"
    with httpx.stream("POST", url, json=body, headers=AUTH, timeout=40.0) as resp:
        assert resp.status_code == httpx.codes.OK, resp.read()
        lines = resp.iter_lines()
        return [json.loads(x[6:]) for x in lines if x.startswith("data: ")]


def test_research_reminder_reaches_the_model(backend_url: str, fake: FakeLlama):
    fake.reset([Turn(content="Report. [1]")])
    sid = new_session(backend_url)
    ev = _post_chat(
        backend_url, sid, {"message": "who?", "research": True, "research_seconds": 60}
    )
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    last_user = fake.requests[0]["messages"][-1]["content"]
    assert "RESEARCH MODE" in last_user
    assert "about 1 minutes" in last_user


def test_plain_turn_has_no_research_reminder(backend_url: str, fake: FakeLlama):
    fake.reset([Turn(content="hi")])
    run_turn(backend_url, new_session(backend_url), "hello")
    assert "RESEARCH MODE" not in json.dumps(fake.requests[0]["messages"])


def test_web_failure_is_a_tool_error_without_sources(backend_url: str, fake: FakeLlama):
    fake.reset([Turn(calls=[("WebSearch", {"query": "x"})]), Turn(content="none")])
    sid = new_session(backend_url, "bypass")
    ev = _post_chat(backend_url, sid, {"message": "q", "research": True})
    assert [e["type"] for e in ev].count("sources") == 0
    assert any(e["type"] == "tool_result" and e["result"]["is_error"] for e in ev)


def test_project_lifecycle_and_telemetry(backend_url: str, workspace):
    r = httpx.post(
        f"{backend_url}/v1/projects",
        json={"name": "itest", "instructions": "be brief"},
        headers=AUTH,
    )
    assert r.status_code == httpx.codes.CREATED
    assert (workspace / "projects" / "itest" / "DOT.md").read_text() == "be brief"
    listed = httpx.get(f"{backend_url}/v1/projects", headers=AUTH).json()
    assert "itest" in [p["name"] for p in listed]
    t = httpx.get(f"{backend_url}/v1/telemetry", headers=AUTH).json()
    assert t["llm_up"] is True
    assert t["sandbox_up"] is True
    r = httpx.post(
        f"{backend_url}/v1/models/select", json={"name": "x.gguf"}, headers=AUTH
    )
    assert r.status_code in (httpx.codes.NOT_IMPLEMENTED, httpx.codes.NOT_FOUND)
