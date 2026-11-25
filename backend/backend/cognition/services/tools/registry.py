from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dot_contracts.events import StreamEvent
from dot_contracts.tools import ToolDefinition, ToolResult

from backend.routing.clients.sandbox_client import SandboxClient

if TYPE_CHECKING:
    from backend.cognition.services.engine.images import ImageSource
    from backend.cognition.services.interaction.agent_services import AgentServices

DEFAULT_MAX_CHARS = 3000


@dataclass
class ToolContext:
    session_id: str
    sandbox: SandboxClient
    workspace: str
    call_id: str = ""
    session_pk: int = 0
    depth: int = 0  # subagent nesting (0 = the main agent)
    label: str | None = None
    emit: Callable[[StreamEvent], None] | None = None  # extra stream events
    agent: "AgentServices | None" = None
    images: "ImageSource | None" = (
        None  # vision: None means the model cannot see images
    )


ToolRun = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolResult]]


@dataclass
class Tool:
    definition: ToolDefinition
    run: ToolRun
    max_chars: int = DEFAULT_MAX_CHARS
    # Overrides the mutating flag for batching only (Agent: depends on the type).
    concurrent: Callable[[dict[str, Any]], bool] | None = None


def schema_of(d: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": d.name,
            "description": d.description,
            "parameters": d.input_schema,
        },
    }


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.definition.name: t for t in tools}
        self.browser: Any = None  # shared BrowserClient, set by add_web_tools
        self.vault: Any = None  # VaultHandle, set by add_web_tools
        # Approval-card text per tool name: async (args) -> str | None. Never secrets.
        self.describers: dict[str, Any] = {}

    def add(self, tool: Tool) -> None:
        self._tools[tool.definition.name] = tool

    def remove(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def core_definitions(self) -> list[ToolDefinition]:
        """Tools whose schemas live in the static prefix (not deferred)."""
        return [d for d in self.definitions() if not d.deferred]

    def deferred_names(self) -> list[str]:
        return [d.name for d in self.definitions() if d.deferred]

    def subset(self, names: Iterable[str]) -> "ToolRegistry":
        wanted = set(names)
        return ToolRegistry([t for n, t in self._tools.items() if n in wanted])

    def openai_schemas(self, active: Iterable[str] = ()) -> list[dict[str, Any]]:
        """Stable OpenAI-style tool list.

        Core tools first in registration order, never reordered; activated
        deferred tools are only ever appended at the end, in activation order.
        """
        out = [schema_of(d) for d in self.core_definitions()]
        for name in active:
            tool = self._tools.get(name)
            if tool is not None and tool.definition.deferred:
                out.append(schema_of(tool.definition))
        return out
