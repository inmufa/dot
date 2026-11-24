"""Turn a skill into text for the model (Skill tool and /slash expansion)."""

from collections.abc import Callable

from backend.cognition.services.skills import files, frontmatter
from backend.cognition.services.skills.model import Skill


def with_args(body: str, args: str) -> str:
    if not args:
        return body
    if "$ARGUMENTS" in body:
        return body.replace("$ARGUMENTS", args)
    return f"{body}\n\nArguments: {args}"


def render(skill: Skill, args: str = "") -> str:
    body = with_args(frontmatter.read_body(skill.path), args)
    listing = files.list_files(skill.path)
    out = [f"# Skill: {skill.name}", "", body.strip(), ""]
    out.append(f"Skill directory: {skill.path}")
    if listing:
        out.append("Bundled files (read with Skill(name, file=<path>)):")
        out.extend(f"- {f}" for f in listing)
    return "\n".join(out)


def expand_slash(text: str, find: Callable[[str], Skill | None]) -> str | None:
    """`/name args` -> expansion text, or None when it is not a known, usable skill."""
    stripped = text.strip()
    if not stripped.startswith("/") or stripped.startswith("//"):
        return None
    name, _, args = stripped[1:].partition(" ")
    skill = find(name.strip())
    if skill is None or not skill.available:
        return None
    if skill.source == "workspace":
        # Repo-controlled text must arrive as a (tainted) tool result, not user text.
        if not skill.model_invocable:
            return None
        return f'{stripped}\n\nLoad this workspace skill with Skill(name="{skill.name}").'
    return f"{stripped}\n\n<skill name=\"{skill.name}\">\n{render(skill, args.strip())}\n</skill>"
