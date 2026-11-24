"""Skill(name, args?, file?): load a skill body or one of its bundled files."""

from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.skill_loader import SkillRegistry
from backend.cognition.services.skills import files
from backend.cognition.services.skills.render import render
from backend.cognition.services.tools.registry import Tool, ToolContext

SKILL_MAX_CHARS = 40_000


def _err(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text, is_error=True)


def make_skill_tool(skills: SkillRegistry) -> Tool:
    async def run(_ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        name = str(a["name"]).lstrip("/")
        skill = skills.get(name)
        if skill is None:
            return _err(f"Unknown skill '{name}'.")
        if not skill.available:
            return _err(f"Skill '{name}' is unavailable: {skill.reason}.")
        if not skill.model_invocable:
            return _err(f"Skill '{name}' can only be started by the user with /{name}.")
        untrusted = skill.source == "workspace"  # the repo wrote it, not the owner
        if rel := a.get("file"):
            try:
                text = files.read_text(
                    skill.path, str(rel), a.get("offset", 0), a.get("limit", 2000)
                )
            except files.SkillFileError as exc:
                return _err(f"Cannot read '{rel}': {exc}.")
            return ToolResult(call_id="", output=text, tainted=untrusted)
        out = render(skill, str(a.get("args", "")))
        return ToolResult(call_id="", output=out, tainted=untrusted)

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "args": {"type": "string"},
            "file": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["name"],
    }
    definition = ToolDefinition(
        name="Skill",
        mutating=False,
        description=(
            "Load a skill's instructions by name (optional args). "
            "Pass file=<relative path> to read a file bundled with the skill."
        ),
        input_schema=schema,
    )
    return Tool(definition, run, max_chars=SKILL_MAX_CHARS)
