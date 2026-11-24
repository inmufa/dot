"""Scoring logic of deploy/scripts/m1_model_gate.py against a mock llama-server."""

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "m1_model_gate.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("m1_model_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
sys.modules["m1_model_gate"] = gate
spec.loader.exec_module(gate)

ARGS = {
    "Read": {"path": "/workspace/app/main.py README.md big.log"},
    "Bash": {"command": "pytest ls git status uv sync wc"},
    "Grep": {"pattern": "TODO def main"},
    "Glob": {"pattern": "**/*.py *.md"},
    "Write": {"path": "/workspace/hello.py .gitignore", "content": "x"},
    "Edit": {"path": "/workspace/app.py calc.py", "old": "a", "new": "b"},
    "WebSearch": {"query": "llama 3.12"},
    "WebFetch": {"url": "https://example.com example.org"},
}


def _msg(name, args):
    return {"tool_calls": [{"function": {"name": name, "arguments": json.dumps(args)}}]}


def test_score_ok():
    task = gate.TASKS[3]
    assert gate.score_task(task, _msg("Bash", {"command": "uv run pytest"})).ok


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ({"content": "I will run it"}, "no tool call"),
        (_msg("Read", {"path": "x"}), "wrong tool"),
        (_msg("Bash", {}), "missing command"),
        (_msg("Bash", {"command": "ls"}), "command does not match"),
        (
            {"tool_calls": [{"function": {"name": "Bash", "arguments": "{oops"}}]},
            "arguments not a JSON object",
        ),
        (
            {"tool_calls": [{"function": {"name": "Bash", "arguments": "[1]"}}]},
            "arguments not a JSON object",
        ),
    ],
)
def test_score_failures(message, reason):
    result = gate.score_task(gate.TASKS[3], message)
    assert not result.ok
    assert reason in result.reason


def test_twenty_tasks_all_name_a_known_tool():
    names = {t["function"]["name"] for t in gate.TOOLS}
    assert len(gate.TASKS) == gate.TASK_COUNT
    assert {t.tool for t in gate.TASKS} <= names


def test_pass_rate_and_turn_reuse():
    ok = gate.TaskResult(gate.TASKS[0], "ok", ok=True)
    bad = gate.TaskResult(gate.TASKS[0], "x")
    assert gate.pass_rate([ok, bad]) == 0.5
    assert gate.pass_rate([]) == 0.0
    assert gate.Turn(1, 100, 5.0, 300).reuse == 0.75
    assert gate.Turn(1, 0, 0.0, 0).reuse == 0.0


class _Handler(BaseHTTPRequestHandler):
    reuse = True
    wrong_every = 0
    seen: list[str] = []
    count = 0

    def log_message(self, *args):
        return

    def do_POST(self):
        cls = type(self)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        flat = "".join(m.get("content") or "" for m in body["messages"])
        user = body["messages"][-1]["content"]
        if body["max_tokens"] == 24:
            previous = cls.seen[-1] if cls.seen else ""
            common = 0
            while (
                common < min(len(previous), len(flat))
                and previous[common] == flat[common]
            ):
                common += 1
            cached = common if cls.reuse else 0
            cls.seen.append(flat)
            timings = {
                "prompt_n": len(flat) - cached,
                "cache_n": cached,
                "prompt_ms": float(len(flat) - cached),
            }
            msg = {"content": "fine"}
        else:
            task = next(t for t in gate.TASKS if t.prompt == user)
            cls.count += 1
            if cls.wrong_every and cls.count % cls.wrong_every == 0:
                msg = {"content": "no tool"}
            else:
                msg = _msg(task.tool, ARGS[task.tool])
            timings = {}
        payload = json.dumps(
            {"choices": [{"message": msg}], "timings": timings}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def server():
    _Handler.reuse, _Handler.wrong_every, _Handler.seen, _Handler.count = True, 0, [], 0
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1", _Handler
    httpd.shutdown()


def test_tasks_pass_against_mock(server):
    url, _ = server
    results = gate.run_tasks(url, "m", "k", 10)
    assert gate.pass_rate(results) == 1.0
    assert "**PASS**" in gate.render_tasks(results)


def test_tasks_fail_when_model_skips_tools(server):
    url, handler = server
    handler.wrong_every = 4
    results = gate.run_tasks(url, "m", "k", 10)
    assert gate.pass_rate(results) == 0.75
    assert "**FAIL**" in gate.render_tasks(results)


def test_probe_detects_reuse_and_its_absence(server):
    url, handler = server
    probe = gate.run_probe(url, "m", "k", 10)
    assert len(probe.turns) == 10
    assert probe.ok
    handler.seen, handler.reuse = [], False
    cold = gate.run_probe(url, "m", "k", 10)
    assert not cold.ok
    assert "**FAIL**" in gate.render_probe(cold)


def test_main_exit_code(server, capsys):
    url, _ = server
    assert gate.main(["--base-url", url]) == 0
    assert "Prefix reuse" in capsys.readouterr().out
    assert gate.run_tasks("http://127.0.0.1:9/v1", "m", "k", 1)[0].reason.startswith(
        "request failed"
    )
