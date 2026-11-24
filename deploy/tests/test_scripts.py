"""Shell scripts: syntax and the argument checks that need no network or docker."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SHELL = sorted(SCRIPTS.glob("*.sh"))


def _run(*args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("DOT_MODEL")}
    env.update(env_extra or {})
    return subprocess.run(  # noqa: S603
        ["bash", str(SCRIPTS / "download_models.sh"), *args],  # noqa: S607
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.parametrize("path", SHELL, ids=lambda p: p.name)
def test_shell_syntax(path):
    first = path.read_text().splitlines()[0]
    shell = "bash" if "bash" in first else "sh"
    done = subprocess.run(  # noqa: S603
        [shell, "-n", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr


def test_download_needs_a_source():
    done = _run()
    assert done.returncode == 2
    assert "DOT_MODEL_URL" in done.stderr


def test_download_rejects_bad_sha_http_and_paths():
    assert "64 hex" in _run("--url", "https://x/y.gguf", "--sha256", "abc").stderr
    http = _run("--url", "http://x/y.gguf", "--file", "y.gguf")
    assert http.returncode == 2
    assert "https" in http.stderr
    assert _run("--url", "https://x", "--file", "../evil.gguf").returncode == 2


def test_smoke_real_renders_and_gates():
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "smoke_real", SCRIPTS / "smoke_real.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["smoke_real"] = mod
    spec.loader.exec_module(mod)
    runs = [
        mod.Run(answer="hi", promoted=False, nudged=False, called_bash=True, seconds=2),
        mod.Run(answer="", promoted=False, nudged=True, called_bash=True, seconds=4),
    ]
    text = mod.render(runs)
    assert "empty final answer: 1/2" in text
    assert "mean turn time: 3.0s" in text
    assert mod.main(["-n", "1"]) == 2  # no token: refuses to run
