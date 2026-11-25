import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from backend.cognition.services.tools.registry import Tool
from backend.routing.clients.llm_types import LLMEvent
from backend.routing.clients.scripted import ScriptedLLM, ScriptItem
from dot_contracts.tools import ToolDefinition, ToolResult
from helpers import new_session, parse_sse
from httpx import AsyncClient


class RoutedLLM(ScriptedLLM):
    """Main-agent scripts pop from `scripts`; a subagent run is routed by the
    first line of its task prompt (its first user message) via `routes`."""

    def __init__(self, scripts: list[list[ScriptItem]]) -> None:
        super().__init__(scripts)
        self.routes: dict[str, list[list[ScriptItem]]] = {}
        self.by_key: dict[str, list[dict[str, Any]]] = {}
        self.active = 0
        self.peak = 0

    @staticmethod
    def key_of(messages: list[dict[str, Any]]) -> str:
        if str(messages[0]["content"]).startswith("You are Dot"):
            return "main"
        first = next(m for m in messages if m["role"] == "user")
        return str(first["content"]).splitlines()[0]

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: Any = None,
    ) -> AsyncIterator[LLMEvent]:
        key = self.key_of(messages)
        self.by_key.setdefault(key, []).append({"messages": messages, "tools": tools})
        if key == "main":
            async for item in super().stream(messages, tools, options):
                yield item
            return
        script = self.routes[key].pop(0)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            for item in script:
                if isinstance(item, asyncio.Event):
                    await item.wait()
                elif isinstance(item, float):
                    await asyncio.sleep(item)
                else:
                    yield item
        finally:
            self.active -= 1


def tool_names(tools: list[dict[str, Any]]) -> list[str]:
    return [t["function"]["name"] for t in tools]


async def chat(c: AsyncClient, sid: str, message: str = "go") -> list[dict]:
    resp = await c.post(f"/v1/sessions/{sid}/chat", json={"message": message})
    return parse_sse(resp.text)


async def session(c: AsyncClient, mode: str = "bypass") -> str:
    return await new_session(c, mode)


def results(events: list[dict]) -> list[dict]:
    return [e["result"] for e in events if e["type"] == "tool_result"]


def assert_paired(events: list[dict]) -> None:
    calls = [e["invocation"]["call_id"] for e in events if e["type"] == "tool_call"]
    outs = [r["call_id"] for r in results(events)]
    assert sorted(calls) == sorted(outs)
    assert len(set(calls)) == len(calls)


def deferred_tool(name: str, description: str, seen: list | None = None) -> Tool:
    async def run(_ctx: Any, a: dict[str, Any]) -> ToolResult:
        if seen is not None:
            seen.append(a)
        return ToolResult(call_id="", output=f"{name} ran {json.dumps(a)}")

    definition = ToolDefinition(
        name=name,
        description=description,
        mutating=False,
        deferred=True,
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": [],
        },
    )
    return Tool(definition, run)


async def assert_transcript_paired(c: AsyncClient, sid: str) -> None:
    msgs = (await c.get(f"/v1/sessions/{sid}/messages")).json()
    calls = [tc["id"] for m in msgs for tc in m["tool_calls"] or []]
    outs = [m["tool_call_id"] for m in msgs if m["role"] == "tool"]
    assert sorted(calls) == sorted(outs)


def write_settings(ws: Any, data: dict[str, Any]) -> None:
    (ws / ".dot").mkdir(exist_ok=True)
    (ws / ".dot" / "settings.json").write_text(json.dumps(data))


def hook(event: str, command: str, matcher: str = "*") -> dict:
    return {"hooks": {event: [{"matcher": matcher, "command": command, "timeout": 10}]}}
