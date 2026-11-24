import asyncio
import json
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from backend.routing.clients.scripted import reply
from helpers import parse_sse
from httpx import AsyncClient

SERVER = str(Path(__file__).with_name("fake_mcp_server.py"))


def stdio_cfg(**extra: Any) -> dict[str, Any]:
    return {"command": sys.executable, "args": [SERVER, "stdio"], **extra}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def http_server(kind: str = "http") -> Iterator[int]:
    port = free_port()
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, SERVER, kind, str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), 0.1).close()
                break
            except OSError:
                time.sleep(0.1)
        yield port
    finally:
        proc.kill()
        proc.wait()


async def wait_status(
    c: AsyncClient, name: str, status: str, limit_s: float = 15
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(limit_s):
            while True:
                rows = (await c.get("/v1/mcp/servers")).json()
                row = next((r for r in rows if r["name"] == name), None)
                if row and row["status"] == status:
                    return row
                await asyncio.sleep(0.05)
    except TimeoutError:
        msg = f"{name} never became {status}: {rows}"
        raise AssertionError(msg) from None


def tool_events(events: list[dict]) -> list[dict]:
    return [e["result"] for e in events if e["type"] == "tool_result"]


def search_and_call(name: str, args: dict[str, Any]) -> list[list]:
    """Model scripts: activate the tool with ToolSearch, call it, then finish."""
    return [
        reply(calls=[("ToolSearch", {"query": f"select:{name}"})]),
        reply(calls=[(name, args)]),
        reply("done"),
    ]


async def run_turn(c: AsyncClient, sid: str) -> list[dict]:
    r = await c.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})
    return parse_sse(r.text)


async def events_of(task: Any) -> list[dict]:
    return parse_sse((await task).text)


def write_settings(ws: Path, data: dict[str, Any]) -> None:
    (ws / ".dot").mkdir(exist_ok=True)
    (ws / ".dot" / "settings.json").write_text(json.dumps(data))


async def trust_and_connect(c: AsyncClient, name: str) -> dict[str, Any]:
    """Approve a project-scoped server (first launch needs it) and wait for it."""
    await wait_status(c, name, "needs_trust")
    r = await c.post(f"/v1/mcp/servers/{name}/trust")
    assert r.status_code == 200, r.text
    return await wait_status(c, name, "connected")
