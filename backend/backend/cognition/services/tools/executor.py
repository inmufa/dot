"""Validate, run and post-process tool calls."""

import logging
import re
from typing import Any

from dot_contracts.tools import ToolResult

from backend.cognition.services.skill_loader import SkillRegistry
from backend.cognition.services.tools.agent import AGENT_TOOLS
from backend.cognition.services.tools.agent.tool_search import make_tool_search
from backend.cognition.services.tools.fs_tools import FS_TOOLS
from backend.cognition.services.tools.registry import (
    Tool,
    ToolContext,
    ToolRegistry,
)
from backend.cognition.services.tools.shell_tools import SHELL_TOOLS
from backend.cognition.services.tools.skill_tool import make_skill_tool
from backend.core.exceptions import DomainException

logger = logging.getLogger(__name__)
_PY_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "number": (int, float),
}


_SPOOF = re.compile(r"<(/?)(system-reminder|tool_call|think|function=)", re.IGNORECASE)


def neutralize(text: str) -> str:
    """Break control tags inside tool output so file or web content cannot
    impersonate the system, the model's own tool calls or its reasoning."""
    return _SPOOF.sub(lambda m: f"<\u200b{m[1]}{m[2]}", text)


def default_registry(skills: SkillRegistry | None = None) -> ToolRegistry:
    extra = [make_skill_tool(skills)] if skills else []
    registry = ToolRegistry([*FS_TOOLS, *SHELL_TOOLS, *extra, *AGENT_TOOLS])
    registry.add(make_tool_search(registry))
    return registry


def summarize(text: str, limit: int, hint: str = "") -> str:
    """Keep head and tail of oversized output; the middle is dropped."""
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    tail = limit - head
    cut = len(text) - head - tail
    note = f"\n... [{cut} chars omitted{'; ' + hint if hint else ''}] ...\n"
    return text[:head] + note + text[-tail:]


def validate(tool: Tool, args: dict[str, Any]) -> str | None:
    """Minimal JSON-schema check: required keys and primitive types."""
    schema = tool.definition.input_schema
    for key in schema.get("required", []):
        if key not in args:
            return f"missing required argument '{key}'"
    for key, spec in schema.get("properties", {}).items():
        expected = _PY_TYPES.get(spec.get("type", ""))
        if key in args and expected and not isinstance(args[key], expected):
            return f"argument '{key}' must be {spec['type']}"
        if (
            key in args
            and spec.get("type") == "integer"
            and isinstance(args[key], bool)
        ):
            return f"argument '{key}' must be integer"
    return None


async def execute(
    registry: ToolRegistry,
    ctx: ToolContext,
    name: str,
    call_id: str,
    args: dict[str, Any],
) -> ToolResult:
    """Run one tool call; always returns a ToolResult (errors become is_error)."""
    tool = registry.get(name)
    if tool is None:
        return ToolResult(
            call_id=call_id, output=f"Unknown tool '{name}'", is_error=True
        )
    problem = validate(tool, args)
    if problem:
        return ToolResult(
            call_id=call_id, output=f"Invalid arguments: {problem}", is_error=True
        )
    try:
        result = await tool.run(ctx, args)
    except DomainException as exc:
        text = f"Tool failed (error code {exc.code})"
        return ToolResult(call_id=call_id, output=text, is_error=True)
    except Exception:
        logger.exception("tool %s crashed", name)
        return ToolResult(call_id=call_id, output="Tool crashed", is_error=True)
    hint = (
        f"full output at {result.spill_path}"
        if result.spill_path
        else "narrow the query or use offset/limit"
    )
    out = neutralize(summarize(result.output, tool.max_chars, hint))
    return result.model_copy(update={"call_id": call_id, "output": out})
