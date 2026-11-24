import json
from pathlib import Path
from typing import Any

from backend.sessions.models import Message
from helpers import new_session, parse_sse
from httpx import AsyncClient

WS = "/ws"


def msg(  # noqa: PLR0913
    seq: int,
    role: str,
    content: str = "",
    *,
    calls: list[dict[str, Any]] | None = None,
    call_id: str | None = None,
    tainted: bool = False,
    reminder: str | None = None,
) -> Message:
    return Message(
        session_id=1,
        seq=seq,
        role=role,
        content=content,
        tool_calls=calls,
        tool_call_id=call_id,
        tainted=tainted,
        reminder=reminder,
        rewound=False,
    )


def call(call_id: str, name: str, **args: Any) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def check_pairing(messages: list[dict[str, Any]]) -> None:
    """Every tool message answers an earlier assistant call; no call is left open."""
    open_ids: set[str] = set()
    for m in messages:
        if m["role"] == "assistant":
            assert not open_ids, f"assistant while calls open: {open_ids}"
            open_ids = {c["id"] for c in m.get("tool_calls") or []}
        elif m["role"] == "tool":
            assert m["tool_call_id"] in open_ids, m["tool_call_id"]
            open_ids.discard(m["tool_call_id"])
        elif m["role"] == "user":
            assert not open_ids, f"user message while calls open: {open_ids}"
    assert not open_ids


def make_files(ws: Path, n: int, chars: int = 2400) -> list[Path]:
    paths = []
    for i in range(n):
        p = ws / f"big{i}.txt"
        text = "".join(
            f"line {i} {n:04d} padding padding padding\n" for n in range(200)
        )
        p.write_text(text[:chars])
        paths.append(p)
    return paths


async def session(c: AsyncClient, mode: str = "bypass") -> str:
    return await new_session(c, mode)


async def chat(c: AsyncClient, sid: str, message: str = "go") -> list[dict]:
    resp = await c.post(f"/v1/sessions/{sid}/chat", json={"message": message})
    return parse_sse(resp.text)


def write_hook(ws: Path, event: str, command: str) -> None:
    (ws / ".dot").mkdir(exist_ok=True)
    spec = {"hooks": {event: [{"matcher": "*", "command": command, "timeout": 10}]}}
    (ws / ".dot" / "settings.json").write_text(json.dumps(spec))
