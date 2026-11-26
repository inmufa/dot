"""Protocol and event types shared by the real llama client and the test double."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TextDelta:
    text: str
    thinking: bool = False


@dataclass
class ToolDraft:
    """A tool call still being written: its name, a short target hint and the argument size so far."""

    name: str
    target: str = ""
    chars: int = 0


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


LLMEvent = TextDelta | ToolDraft | LLMFinish


@dataclass
class StreamOptions:
    """Per-request overrides on top of the client's default sampling."""

    thinking: bool | None = None  # None: client default
    reasoning_effort: str | None = None  # passed natively when the template has it
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    presence_penalty: float | None = None
    max_tokens: int | None = None


class LLMClient(Protocol):
    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: StreamOptions | None = None,
    ) -> AsyncIterator[LLMEvent]:
        """Yield TextDelta items, then exactly one LLMFinish."""
        ...

    async def complete(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 1024,
        *,
        thinking: bool = True,
    ) -> str:
        """One non-streaming reply (compaction, memory, titles). thinking=False skips reasoning."""
        ...

    async def health(self) -> bool: ...

    async def aclose(self) -> None: ...
