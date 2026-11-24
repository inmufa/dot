"""SKILL.md parsing: YAML frontmatter + markdown body. Never raises on bad skills."""

import re
from pathlib import Path
from typing import Any

import yaml
from dot_contracts.skills import SkillSource

from backend.cognition.services.skills.model import (
    DESCRIPTION_CAP,
    Requires,
    Skill,
    SkillIssue,
)

MAX_SKILL_BYTES = 1_000_000  # SKILL.md larger than this is refused
MAX_FRONTMATTER = 32_000


class _NoAliasLoader(yaml.SafeLoader):
    """SafeLoader that refuses anchors/aliases (YAML expansion bombs)."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            msg = "YAML aliases are not allowed"
            raise yaml.YAMLError(msg)
        return super().compose_node(parent, index)


def read_capped(path: Path) -> str:
    """UTF-8 text of SKILL.md (bad bytes replaced), size-capped, never via a link
    that leaves its skill directory (the backend must not read files for the repo)."""
    if not path.resolve().is_relative_to(path.parent.resolve()):
        msg = "SKILL.md points outside its directory"
        raise SkillParseError(msg)
    with path.open("rb") as fh:
        raw = fh.read(MAX_SKILL_BYTES + 1)
    if len(raw) > MAX_SKILL_BYTES:
        msg = "SKILL.md is too large"
        raise SkillParseError(msg)
    return raw.decode("utf-8", errors="replace")


_FM = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class SkillParseError(ValueError):
    pass


def split(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter dict, body). Raises SkillParseError."""
    m = _FM.match(text)
    if not m:
        msg = "missing frontmatter block"
        raise SkillParseError(msg)
    try:
        if len(m.group(1)) > MAX_FRONTMATTER:
            msg = "frontmatter is too large"
            raise SkillParseError(msg)
        data = yaml.load(m.group(1), Loader=_NoAliasLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        msg = f"invalid YAML: {str(exc).splitlines()[0] if str(exc) else exc}"
        raise SkillParseError(msg) from exc
    if not isinstance(data, dict):
        msg = "frontmatter must be a mapping"
        raise SkillParseError(msg)
    return data, text[m.end() :].lstrip("\r\n")


def _strs(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in re.split(r"[,\n]", value) if p.strip()]
    if isinstance(value, list | tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def parse_requires(raw: Any) -> Requires:
    """Accepts {tools, mcp, binaries} with list or comma-string values."""
    if not isinstance(raw, dict):
        return Requires()
    return Requires(
        tools=tuple(_strs(raw.get("tools"))),
        mcp=tuple(_strs(raw.get("mcp"))),
        binaries=tuple(_strs(raw.get("binaries"))),
    )


def _cap(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= DESCRIPTION_CAP:
        return flat
    return flat[: DESCRIPTION_CAP - 3].rstrip() + "..."


def read_skill(
    directory: Path, source: SkillSource
) -> tuple[Skill | None, SkillIssue | None]:
    """Parse `<directory>/SKILL.md`; a problem is returned, not raised."""
    md = directory / "SKILL.md"
    try:
        fm, _ = split(read_capped(md))
    except (OSError, SkillParseError) as exc:
        return None, SkillIssue(str(md), str(exc))
    name = str(fm.get("name") or directory.name).strip()
    if not _NAME.match(name):
        return None, SkillIssue(str(md), f"invalid skill name '{name}'")
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        return None, SkillIssue(str(md), "missing description")
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    triggers = _strs(fm.get("triggers") or meta.get("triggers"))
    lic = fm.get("license")
    skill = Skill(
        name=name,
        description=_cap(desc),
        path=directory,
        source=source,
        license=str(lic) if lic else None,
        allowed_tools=_strs(fm.get("allowed-tools")),
        requires=parse_requires(fm.get("requires")),
        triggers=triggers,
        model_invocable=not _truthy(fm.get("disable-model-invocation")),
    )
    return skill, None


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def read_body(directory: Path) -> str:
    """Body of SKILL.md without frontmatter ('' if unreadable)."""
    try:
        return split(read_capped(directory / "SKILL.md"))[1]
    except (OSError, SkillParseError):
        return ""
