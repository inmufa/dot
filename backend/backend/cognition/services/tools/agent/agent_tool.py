"""Agent(description, prompt, subagent_type): delegate to a subagent."""

from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.subagents.types import TYPES
from backend.cognition.services.tools.registry import Tool, ToolContext


async def run_agent(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    name = str(a.get("subagent_type") or "general-purpose")
    kind = TYPES.get(name)
    if kind is None:
        text = f"Unknown subagent_type '{name}'. Use: {', '.join(TYPES)}."
        return ToolResult(call_id="", output=text, is_error=True)
    if ctx.agent is None or ctx.agent.subagents is None:
        return ToolResult(
            call_id="", output="Subagents are not available.", is_error=True
        )
    return await ctx.agent.subagents.run(ctx, kind, str(a["prompt"]))


def _concurrent(args: dict[str, Any]) -> bool:
    kind = TYPES.get(str(args.get("subagent_type") or "general-purpose"))
    return bool(kind and kind.read_only)


AGENT_TOOL = Tool(
    ToolDefinition(
        name="Agent",
        mutating=False,  # the subagent's own tool calls are each governed
        description=(
            "Delegate a self-contained task to a subagent with a fresh context. "
            "subagent_type: Explore (read-only search), Plan (read-only planning), "
            "Verifier (run tests), general-purpose (anything). Returns a short report."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "prompt": {"type": "string"},
                "subagent_type": {
                    "type": "string",
                    "enum": list(TYPES),
                },
            },
            "required": ["description", "prompt"],
        },
    ),
    run_agent,
    max_chars=3000,
    concurrent=_concurrent,
)
