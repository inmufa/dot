"""Start real servers on free ports: uvicorn in a thread, sandbox as a subprocess."""

import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import uvicorn


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, limit_s: float = 20.0) -> None:
    end = time.monotonic() + limit_s
    while time.monotonic() < end:
        try:
            if httpx.get(url, timeout=1.0).status_code == httpx.codes.OK:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    msg = f"{url} did not become healthy"
    raise TimeoutError(msg)


@contextmanager
def serve_thread(app: Any, health: str = "/health"):
    port = free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        wait_http(base + health)
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@contextmanager
def sandbox_process(workspace: Path, token: str):
    port = free_port()
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "DOT_WORKSPACE": str(workspace),
        "DOT_SANDBOX_TOKEN": token,
        "HOME": str(workspace.parent),
    }
    cmd = [sys.executable, "-m", "uvicorn", "dot_sandbox.main:app_factory"]
    cmd += ["--factory", "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(  # noqa: S603
        cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait_http(base + "/health")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
