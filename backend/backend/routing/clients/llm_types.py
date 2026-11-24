"""Protocol and event types shared by the real llama client and the test double."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TextDelta:
    text: str
    thinking: bool = False


@dataclass
class ParsedToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str = ""
    error: str | None = None


@dataclass
class LLMFinish:
    reason: str = "stop"
    tool_calls: list[ParsedToolCall] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


LLMEvent = TextDelta | LLMFinish


class LLMClient(Protocol):
    def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        """Yield TextDelta items, then exactly one LLMFinish."""
        ...

    async def complete(
        self, messages: list[dict[str, Any]], max_tokens: int = 1024
    ) -> str:
        """One non-streaming reply (compaction, memory consolidation)."""
        ...

    async def health(self) -> bool: ...

    async def aclose(self) -> None: ...
