"""`dot --once` against a real backend over HTTP (fake llama, real sandbox)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fake_llama import FakeLlama, Turn

pytestmark = pytest.mark.integration

TOKEN = "i" * 32
RUN = "import sys; from dot_cli.app import main; main(sys.argv[1:])"


def _dot(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ.get("PATH", ""), "DOT_URL": url, "DOT_API_TOKEN": TOKEN}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", RUN, *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )


def test_once_prints_final_answer_after_tool_use(
    backend_url: str, fake: FakeLlama, workspace: Path
):
    target = workspace / "note.txt"
    target.write_text("hello\n")
    fake.reset(
        [
            Turn(content="reading", calls=[("Read", {"file_path": str(target)})]),
            Turn(content="The note says hello."),
        ]
    )
    proc = _dot(backend_url, "--once", "what does note.txt say?")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "The note says hello."


def test_once_rejects_approvals_and_exits_zero(
    backend_url: str, fake: FakeLlama, workspace: Path
):
    out = workspace / "blocked.txt"
    fake.reset(
        [
            Turn(calls=[("Write", {"file_path": str(out), "content": "x"})]),
            Turn(content="could not write"),
        ]
    )
    proc = _dot(backend_url, "--once", "write it")
    assert proc.returncode == 0, proc.stderr
    assert "approval required" in proc.stderr
    assert not out.exists()
    assert proc.stdout.strip() == "could not write"


def test_once_exit_code_one_on_llm_failure(backend_url: str, fake: FakeLlama):
    fake.reset([Turn(content="x", error_after=True)])
    proc = _dot(backend_url, "--once", "hi")
    assert proc.returncode == 1
    assert "error" in proc.stderr
