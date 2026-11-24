from enum import StrEnum

from pydantic import BaseModel


class PermissionMode(StrEnum):
    PLAN = "plan"
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    AUTO = "auto"
    BYPASS = "bypass"


class Decision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class RuleSpec(BaseModel):
    """One `Tool(specifier)` rule from settings.json, e.g. Bash(git status:*)."""

    decision: Decision
    tool: str
    specifier: str | None = None


class ClassifierVerdict(BaseModel):
    decision: Decision
    stage: str
    reason: str
