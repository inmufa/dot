"""Real protocol: fake llama-server over HTTP, real sandbox, real backend and SQLite."""

from pathlib import Path

import httpx
import pytest
from drive import AUTH, audit, new_session, run_turn
from fake_llama import FakeLlama, Turn

pytestmark = pytest.mark.integration

SRC = "def add(a, b):\n    return a - b\n"
CHECK = "python3 -c \"import app; assert app.add(1, 2) == 3; print('PASS')\""


def _kinds(ev: list[dict]) -> list[str]:
    return [e["type"] for e in ev]


def test_plan_read_edit_bash_answer(backend_url: str, fake: FakeLlama, workspace: Path):
    target = workspace / "app.py"
    target.write_text(SRC)
    fake.reset(
        [
            Turn(reasoning="plan first", calls=[("EnterPlanMode", {})]),
            Turn(calls=[("Read", {"file_path": str(target)})]),
            Turn(calls=[("ExitPlanMode", {"plan": "1. fix add"})]),
            Turn(
                calls=[
                    (
                        "Edit",
                        {
                            "file_path": str(target),
                            "old_string": "a - b",
                            "new_string": "a + b",
                        },
                    )
                ]
            ),
            Turn(calls=[("Bash", {"command": CHECK})]),
            Turn(content="Fixed add(); the check passes."),
        ]
    )
    sid = new_session(backend_url, "default")
    ev = run_turn(backend_url, sid, "fix add")

    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert not any(e["type"] == "error" for e in ev)
    assert any(e["type"] == "token" and e["thinking"] for e in ev)
    assert _kinds(ev).count("usage") == 6
    assert _kinds(ev).count("approval_required") == 3  # plan, edit, bash
    results = [e["result"] for e in ev if e["type"] == "tool_result"]
    assert len(results) == 5
    assert not any(r["is_error"] for r in results)
    assert "a - b" in results[1]["output"]
    assert "PASS" in results[4]["output"]
    assert target.read_text() == SRC.replace("a - b", "a + b")
    text = "".join(e["text"] for e in ev if e["type"] == "token" and not e["thinking"])
    assert "check passes" in text

    rows = audit(backend_url, sid)
    assert {"Read", "Edit", "Bash", "ExitPlanMode"} <= {r["tool"] for r in rows}
    assert any(r["source"] == "user" and r["tool"] == "Edit" for r in rows)
    msgs = httpx.get(f"{backend_url}/v1/sessions/{sid}/messages", headers=AUTH).json()
    assert msgs[0]["role"] == "user"
    assert msgs[-1]["role"] == "assistant"
    # the prompt prefix is byte-stable across the six real HTTP requests
    firsts = {str(r["messages"][0]) for r in fake.requests}
    assert len(firsts) == 1
    assert fake.requests[0]["stream_options"] == {"include_usage": True}


def test_rejected_edit_leaves_file_alone(
    backend_url: str, fake: FakeLlama, workspace: Path
):
    target = workspace / "keep.py"
    target.write_text(SRC)
    fake.reset(
        [
            Turn(calls=[("Read", {"file_path": str(target)})]),
            Turn(
                calls=[
                    (
                        "Edit",
                        {
                            "file_path": str(target),
                            "old_string": "a - b",
                            "new_string": "a + b",
                        },
                    )
                ]
            ),
            Turn(content="ok, left it"),
        ]
    )
    ev = run_turn(backend_url, new_session(backend_url), "go", decision="reject")
    assert ev[-1]["stop_reason"] == "end_turn"
    assert target.read_text() == SRC


def test_length_finish_is_reported_not_executed(
    backend_url: str, fake: FakeLlama, workspace: Path
):
    out = workspace / "never.txt"
    fake.reset(
        [
            Turn(
                content="partial",
                calls=[("Write", {"file_path": str(out), "content": "x"})],
                finish="length",
            ),
            Turn(content="recovered"),
        ]
    )
    ev = run_turn(backend_url, new_session(backend_url), "go")
    assert not out.exists()
    assert ev[-1]["type"] == "done"
    results = [e["result"] for e in ev if e["type"] == "tool_result"]
    assert results
    assert all(r["is_error"] for r in results)
    assert "truncated" in results[0]["output"]


def test_mid_stream_error_chunk_ends_with_error_then_done(
    backend_url: str, fake: FakeLlama
):
    fake.reset([Turn(content="starting", error_after=True)])
    ev = run_turn(backend_url, new_session(backend_url), "go")
    assert _kinds(ev)[-2:] == ["error", "done"]
    assert ev[-2]["code"] == 4000
    assert ev[-1]["stop_reason"] == "error"


def test_reasoning_content_streams_as_thinking(backend_url: str, fake: FakeLlama):
    fake.reset([Turn(reasoning="let me think", content="answer")])
    ev = run_turn(backend_url, new_session(backend_url), "go")
    think = "".join(e["text"] for e in ev if e["type"] == "token" and e["thinking"])
    said = "".join(e["text"] for e in ev if e["type"] == "token" and not e["thinking"])
    assert think == "let me think"
    assert said == "answer"


def test_public_api_requires_the_token(backend_url: str):
    assert (
        httpx.get(f"{backend_url}/v1/sessions").status_code == httpx.codes.UNAUTHORIZED
    )
    ready = httpx.get(f"{backend_url}/ready")
    assert ready.status_code == httpx.codes.OK
