import json
from pathlib import Path
from typing import Any

from helpers import new_session, parse_sse
from httpx import AsyncClient


def write_settings(ws: Path, data: dict[str, Any]) -> None:
    (ws / ".dot").mkdir(exist_ok=True)
    (ws / ".dot" / "settings.json").write_text(json.dumps(data))


def hook(event: str, command: str, matcher: str = "*", timeout: float = 10) -> dict:
    return {
        "hooks": {event: [{"matcher": matcher, "command": command, "timeout": timeout}]}
    }


async def chat(c: AsyncClient, sid: str, message: str = "go") -> list[dict]:
    resp = await c.post(f"/v1/sessions/{sid}/chat", json={"message": message})
    return parse_sse(resp.text)


async def session(c: AsyncClient, mode: str = "bypass") -> str:
    return await new_session(c, mode)


def results(events: list[dict]) -> list[dict]:
    return [e["result"] for e in events if e["type"] == "tool_result"]
