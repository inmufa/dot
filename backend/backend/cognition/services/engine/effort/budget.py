"""Reasoning budget: cut an over-long thinking stream and re-ask without thinking."""

import dataclasses
from collections.abc import AsyncIterator
from typing import Any

from backend.cognition.services.engine.effort.profiles import CHARS_PER_TOKEN
from backend.routing.clients.llm_types import (
    LLMClient,
    LLMEvent,
    StreamOptions,
    TextDelta,
)


async def budgeted(
    llm: LLMClient,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    options: StreamOptions | None,
    think_cap: int | None,
) -> AsyncIterator[LLMEvent]:
    """Stream like llm.stream; past `think_cap` reasoning tokens, stop that
    request and run it again with thinking off (the cut reasoning is kept in
    the stream so the UI shows it, but the retry does not depend on it)."""
    if not think_cap or options is None or options.thinking is False:
        async for item in llm.stream(messages, tools, options):
            yield item
        return
    limit = think_cap * CHARS_PER_TOKEN
    thought = 0
    stream = llm.stream(messages, tools, options)
    cut = False
    try:
        async for item in stream:
            if isinstance(item, TextDelta) and item.thinking:
                thought += len(item.text)
                yield item
                if thought > limit:
                    cut = True
                    break
                continue
            yield item
    finally:
        await stream.aclose()  # type: ignore[attr-defined]
    if cut:
        retry = dataclasses.replace(options, thinking=False, reasoning_effort=None)
        async for item in llm.stream(messages, tools, retry):
            yield item
