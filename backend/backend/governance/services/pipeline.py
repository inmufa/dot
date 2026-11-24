"""One place that runs a tool call through the governance steps.

Order (spec 5.1): settings rules, PreToolUse hooks, mode, classifier (auto only),
then the user. The runner asks the user and calls `record_user` with the answer.
"""

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from dot_contracts.permissions import ClassifierVerdict, Decision
from dot_contracts.tools import ToolDefinition, ToolResult

from backend.governance.services.audit import AuditService
from backend.governance.services.auto_classifier import AutoClassifier
from backend.governance.services.checkpoints import CheckpointService
from backend.governance.services.hooks_engine import HookOutcome, HooksEngine
from backend.governance.services.permission_engine import (
    PermissionEngine,
    PermissionResult,
)
from backend.governance.settings.loader import SettingsProvider
from backend.governance.settings.schema import HookEvent

if TYPE_CHECKING:
    from backend.governance.services.path_resolver import PathResolver


@dataclass
class Evaluation:
    arguments: dict[str, Any]  # possibly rewritten by a PreToolUse hook
    verdict: PermissionResult
    classifier: ClassifierVerdict | None = None
    block_text: str | None = None  # hook stderr to hand back to the model


class Governance:
    def __init__(
        self,
        *,
        settings: SettingsProvider,
        perms: PermissionEngine,
        hooks: HooksEngine,
        classifier: AutoClassifier,
        audit: AuditService,
        checkpoints: CheckpointService,
    ) -> None:
        self.resolver: PathResolver | None = None  # set by wiring
        self.settings = settings
        self.perms = perms
        self.hooks = hooks
        self.classifier = classifier
        self.taint = classifier.taint
        self.audit = audit
        self.checkpoints = checkpoints
        self._background: set[asyncio.Task] = set()

    async def fire(
        self,
        event: HookEvent,
        session: str,
        payload: dict[str, Any],
        tool_name: str | None = None,
    ) -> HookOutcome:
        hooks = self.settings.get().hooks
        if not hooks.get(event):
            return HookOutcome()
        return await self.hooks.run(event, session, hooks, payload, tool_name)

    def fire_in_background(
        self, event: HookEvent, session: str, payload: dict[str, Any]
    ) -> None:
        task = asyncio.create_task(self.fire(event, session, payload))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def evaluate(
        self,
        session: str,
        mode: str,
        tool: ToolDefinition,
        args: dict[str, Any],
        allowed: set[str],
    ) -> Evaluation:
        ev = await self._evaluate(session, mode, tool, args, allowed)
        await self.audit.append(
            session=session,
            mode=mode,
            tool=tool.name,
            args=ev.arguments,
            decision=ev.verdict.decision.value,
            source=ev.verdict.source,
            reason=ev.verdict.reason,
        )
        return ev

    async def _evaluate(
        self,
        session: str,
        mode: str,
        tool: ToolDefinition,
        args: dict[str, Any],
        allowed: set[str],
    ) -> Evaluation:
        perm = await self._decide(session, mode, tool, args, allowed)
        if perm.decision == Decision.DENY:
            return Evaluation(args, perm)
        out = await self.fire(
            HookEvent.PRE_TOOL_USE,
            session,
            {"tool_name": tool.name, "tool_input": args},
            tool.name,
        )
        if out.blocked:
            denied = PermissionResult(
                Decision.DENY, f"blocked by a PreToolUse hook: {out.reason}", "hook"
            )
            return Evaluation(args, denied, block_text=out.reason)
        if out.updated_input is not None:
            args = out.updated_input
            perm = await self._decide(session, mode, tool, args, allowed)  # rewrite too
            if perm.decision == Decision.DENY:
                return Evaluation(args, perm)
        if out.decision == "ask" and perm.decision == Decision.ALLOW:
            perm = PermissionResult(Decision.ASK, "a PreToolUse hook asked", "hook")
        if not perm.classify:
            return Evaluation(args, perm)
        return self._classify(session, tool, args)

    async def _decide(
        self,
        session: str,
        mode: str,
        tool: ToolDefinition,
        args: dict[str, Any],
        allowed: set[str],
    ) -> PermissionResult:
        """Rules on the given path, and a deny if the symlink target is denied."""
        perm = self.perms.decide(mode, tool, args, allowed)
        if perm.decision == Decision.DENY or self.resolver is None:
            return perm
        real = await self.resolver.real_args(session, tool.name, args)
        if real is not None:
            other = self.perms.decide(mode, tool, real, allowed)
            if other.decision == Decision.DENY:
                return PermissionResult(
                    Decision.DENY, f"{other.reason} (via symlink)", other.source
                )
        return perm

    def _classify(
        self,
        session: str,
        tool: ToolDefinition,
        args: dict[str, Any],
    ) -> Evaluation:
        verdict = self.classifier.classify(session, tool.name, args)
        reason = f"classifier stage {verdict.stage}: {verdict.reason}"
        result = PermissionResult(verdict.decision, reason, "classifier")
        return Evaluation(args, result, verdict)

    async def record_user(
        self,
        session: str,
        mode: str,
        tool: str,
        args: dict[str, Any],
        decision: Decision,
        reason: str,
    ) -> None:
        await self.audit.append(
            session=session,
            mode=mode,
            tool=tool,
            args=args,
            decision=decision.value,
            source="user",
            reason=reason,
        )

    async def after_tool(
        self,
        session: str,
        tool: str,
        args: dict[str, Any],
        result: ToolResult,
    ) -> ToolResult:
        """Taint tracking and PostToolUse hooks; hook stderr is appended for the model."""
        if result.tainted:
            self.taint.add(session, result.output)
        out = await self.fire(
            HookEvent.POST_TOOL_USE,
            session,
            {
                "tool_name": tool,
                "tool_input": args,
                "tool_response": {"output": result.output, "is_error": result.is_error},
            },
            tool,
        )
        notes = [out.reason] if out.blocked and out.reason else []
        notes += out.warnings
        if not notes:
            return result
        text = result.output + "\n[PostToolUse hook] " + "\n".join(notes)
        return result.model_copy(update={"output": text})
