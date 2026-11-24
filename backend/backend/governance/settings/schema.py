"""Pydantic schema for `.dot/settings.json` and `~/.dot/settings.json`."""

from enum import StrEnum

from dot_contracts.permissions import Decision, RuleSpec
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.governance.services.rules import parse_rule
from backend.governance.settings.mcp_spec import McpServerSpec, valid_server_name


class HookEvent(StrEnum):
    SESSION_START = "SessionStart"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    NOTIFICATION = "Notification"
    STOP = "Stop"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"


class HookSpec(BaseModel):
    matcher: str = "*"  # tool-name regex (PreToolUse/PostToolUse); "*" matches all
    command: str = Field(min_length=1)
    timeout: float = Field(default=30.0, gt=0, le=600)


class Permissions(BaseModel):
    allow: list[str] = Field(default_factory=list)
    ask: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)

    @field_validator("allow", "ask", "deny")
    @classmethod
    def _valid_rules(cls, rules: list[str]) -> list[str]:
        for rule in rules:
            parse_rule(Decision.ALLOW, rule)  # raises ValueError on bad syntax
        return rules


class DotSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    permissions: Permissions = Field(default_factory=Permissions)
    hooks: dict[HookEvent, list[HookSpec]] = Field(default_factory=dict)
    mcp_servers: dict[str, McpServerSpec] = Field(
        default_factory=dict, alias="mcpServers"
    )

    @field_validator("mcp_servers")
    @classmethod
    def _server_names(cls, v: dict[str, McpServerSpec]) -> dict[str, McpServerSpec]:
        for name in v:
            valid_server_name(name)
        return v

    def rules(self) -> list[RuleSpec]:
        p = self.permissions
        return [
            parse_rule(decision, text)
            for decision, texts in (
                (Decision.DENY, p.deny),
                (Decision.ALLOW, p.allow),
                (Decision.ASK, p.ask),
            )
            for text in texts
        ]

    def merged_over(self, base: "DotSettings") -> "DotSettings":
        """Self wins: its entries come first, lists are unioned (never dropped)."""
        perms = {
            k: list(
                dict.fromkeys(
                    [*getattr(self.permissions, k), *getattr(base.permissions, k)]
                )
            )
            for k in ("allow", "ask", "deny")
        }
        hooks = {
            e: [*self.hooks.get(e, []), *base.hooks.get(e, [])]
            for e in {*self.hooks, *base.hooks}
        }
        return DotSettings(
            permissions=Permissions(**perms),
            hooks=hooks,
            mcpServers={**base.mcp_servers, **self.mcp_servers},
        )
