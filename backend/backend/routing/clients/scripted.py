"""Scripted LLM test double implementing the LLMClient protocol."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from backend.routing.clients.llm_types import (
    LLMEvent,
    LLMFinish,
    ParsedToolCall,
    StreamOptions,
    TextDelta,
)

ScriptItem = LLMEvent | asyncio.Event | float


def reply(
    text: str = "",
    calls: list[tuple[str, dict[str, Any] | str]] | None = None,
    thinking: str = "",
) -> list[ScriptItem]:
    """One model turn: optional thinking, text, and tool calls.

    A call's args may be a dict or a raw string (to simulate malformed JSON).
    """
    items: list[ScriptItem] = []
    if thinking:
        items.append(TextDelta(thinking, thinking=True))
    if text:
        items.append(TextDelta(text))
    parsed: list[ParsedToolCall] = []
    for i, (name, args) in enumerate(calls or []):
        raw = args if isinstance(args, str) else json.dumps(args)
        ok = not isinstance(args, str)
        parsed.append(
            ParsedToolCall(
                f"call_{i}_{name}",
                name,
                args if ok else {},
                raw,
                None if ok else "arguments are not a valid JSON object",
            )
        )
    items.append(LLMFinish("tool_calls" if parsed else "stop", parsed, 100, 10))
    return items


class ScriptedLLM:
    """Pops one script per stream() call; asyncio.Event items block until set."""

    def __init__(
        self, scripts: list[list[ScriptItem]], completions: list[str] | None = None
    ) -> None:
        self.scripts = list(scripts)
        self.completions = list(completions or [])  # replies for complete()
        self.complete_requests: list[list[dict[str, Any]]] = []
        # True: report prompt_tokens from the request size, like a real server.
        self.realistic_usage = False
        self.requests: list[dict[str, Any]] = []
        self.healthy = True
        self.has_vision = False  # tests flip this to simulate a loaded projector

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: StreamOptions | None = None,
    ) -> AsyncIterator[LLMEvent]:
        self.requests.append({"messages": messages, "tools": tools, "options": options})
        script = self.scripts.pop(0) if self.scripts else reply("(script exhausted)")
        for item in script:
            if isinstance(item, asyncio.Event):
                await item.wait()
            elif isinstance(item, float):
                await asyncio.sleep(item)
            elif isinstance(
                item, BaseException
            ):  # simulates a backend failure mid-turn
                raise item
            else:
                if self.realistic_usage and isinstance(item, LLMFinish):
                    item.prompt_tokens = _prompt_size(messages)
                yield item

    async def complete(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 1024,
        *,
        thinking: bool = True,
    ) -> str:
        self.complete_requests.append(messages)
        if self.completions:
            return self.completions.pop(0)
        return "Summary: (scripted)"

    async def health(self) -> bool:
        return self.healthy

    async def vision(self) -> bool:
        return self.has_vision

    async def aclose(self) -> None:
        return None


def _prompt_size(messages: list[dict[str, Any]]) -> int:
    return sum(len(json.dumps(m)) // 4 for m in messages)
