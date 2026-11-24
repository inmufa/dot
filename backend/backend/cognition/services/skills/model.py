"""Skill value objects."""

from dataclasses import dataclass, field
from pathlib import Path

from dot_contracts.skills import SkillSource

DESCRIPTION_CAP = 300


@dataclass(frozen=True)
class Requires:
    tools: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    binaries: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, list[str]]:
        data = {"tools": self.tools, "mcp": self.mcp, "binaries": self.binaries}
        return {k: list(v) for k, v in data.items() if v}


@dataclass
class Skill:
    name: str
    description: str
    path: Path  # skill directory
    source: SkillSource
    license: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    requires: Requires = field(default_factory=Requires)
    triggers: list[str] = field(default_factory=list)
    model_invocable: bool = True
    available: bool = True
    reason: str | None = None


@dataclass(frozen=True)
class SkillIssue:
    path: str
    message: str
