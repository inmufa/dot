"""Permission decisions: plan mode, settings rules (deny > allow > ask), then mode."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dot_contracts.permissions import Decision, PermissionMode, RuleSpec
from dot_contracts.tools import ToolDefinition

from backend.governance.services.rules import RuleContext, decide_rules

_EDIT_TOOLS = frozenset({"Write", "Edit"})
# Tools that use stored secrets: the owner approves every time, in every mode.
ALWAYS_ASK = frozenset({"BrowserLogin"})
RulesSource = list[RuleSpec] | Callable[[], list[RuleSpec]]


@dataclass
class PermissionResult:
    decision: Decision
    reason: str = ""
    source: str = "mode"  # rule | mode | hook | classifier | user
    classify: bool = False  # auto mode: the classifier must rule on this call


def always_key(name: str, args: dict[str, Any]) -> str:
    """Key for 'always allow for this session'.

    Bash is scoped to the exact command string: a first-word allow would also
    permit `git -c core.sshCommand=...`, `bash -c`, `env`, `sudo`.
    """
    if name == "Bash":
        return f"Bash:{str(args.get('command', '')).strip()}"
    if name in ALWAYS_ASK:  # scoped to one saved login (one site), this session only
        return f"{name}:{str(args.get('credential', '')).strip().lower()}"
    return name


class PermissionEngine:
    def __init__(
        self, rules: RulesSource | None = None, ctx: RuleContext | None = None
    ) -> None:
        self._rules = rules or []
        self.ctx = ctx or RuleContext()

    def rules(self) -> list[RuleSpec]:
        return self._rules() if callable(self._rules) else self._rules

    def decide(  # noqa: PLR0911
        self,
        mode: str,
        tool: ToolDefinition,
        args: dict[str, Any],
        session_allowed: set[str] | None = None,
    ) -> PermissionResult:
        allowed = session_allowed or set()
        if tool.mutating and mode == PermissionMode.PLAN:
            # Plan mode is absolute: no rule may re-enable a mutating tool.
            return PermissionResult(Decision.DENY, "plan mode is read-only")
        if tool.name in ALWAYS_ASK:
            return self._always_ask(tool, args, allowed)
        hit = decide_rules(self.rules(), tool.name, args, self.ctx)
        if hit is not None:
            if hit.decision == Decision.ASK and mode == PermissionMode.BYPASS:
                return PermissionResult(
                    Decision.ALLOW, "bypass mode"
                )  # deny still wins
            text = f"{hit.decision.value} rule {hit.rule}"
            if hit.decision == Decision.ASK and always_key(tool.name, args) in allowed:
                return PermissionResult(
                    Decision.ALLOW, "allowed for this session", "user"
                )
            return PermissionResult(hit.decision, text, "rule")
        if not tool.mutating and not tool.needs_approval:
            return PermissionResult(Decision.ALLOW, "read-only tool")
        if not tool.mutating:
            return self._open_world(mode, tool, args, allowed)
        return self._by_mode(mode, tool, args, allowed)

    def _always_ask(
        self, tool: ToolDefinition, args: dict[str, Any], allowed: set[str]
    ) -> PermissionResult:
        """Deny rules still apply; allow rules, bypass and auto mode never skip the prompt."""
        hit = decide_rules(self.rules(), tool.name, args, self.ctx)
        if hit is not None and hit.decision == Decision.DENY:
            return PermissionResult(Decision.DENY, f"deny rule {hit.rule}", "rule")
        if always_key(tool.name, args) in allowed:
            return PermissionResult(
                Decision.ALLOW, "allowed for this site this session", "user"
            )
        return PermissionResult(Decision.ASK, "saved logins always need approval")

    @staticmethod
    def _open_world(
        mode: str, tool: ToolDefinition, args: dict[str, Any], allowed: set[str]
    ) -> PermissionResult:
        """Read-only by its own claim but reaches outside: ask, never classify."""
        if mode == PermissionMode.BYPASS:
            return PermissionResult(Decision.ALLOW, "bypass mode")
        if always_key(tool.name, args) in allowed:
            return PermissionResult(Decision.ALLOW, "allowed for this session", "user")
        return PermissionResult(Decision.ASK, "open-world tool needs approval")

    @staticmethod
    def _by_mode(
        mode: str, tool: ToolDefinition, args: dict[str, Any], allowed: set[str]
    ) -> PermissionResult:
        if mode == PermissionMode.BYPASS:
            return PermissionResult(Decision.ALLOW, "bypass mode")
        if mode == PermissionMode.ACCEPT_EDITS and tool.name in _EDIT_TOOLS:
            return PermissionResult(Decision.ALLOW, "acceptEdits mode")
        if always_key(tool.name, args) in allowed:
            return PermissionResult(Decision.ALLOW, "allowed for this session", "user")
        if tool.needs_approval:  # the user decides, never the classifier
            return PermissionResult(Decision.ASK, "tool requires approval")
        if mode == PermissionMode.AUTO:
            return PermissionResult(
                Decision.ASK, "auto mode: classifier", classify=True
            )
        return PermissionResult(Decision.ASK, "mutating tool needs approval")
