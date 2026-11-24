"""Runs a subagent: a child ReAct loop with a fresh context and the same governance."""

import asyncio
import logging
from dataclasses import replace
from itertools import count
from typing import Any

from dot_contracts.events import (
    ApprovalRequiredEvent,
    DoneEvent,
    ErrorEvent,
    SubagentEvent,
    TokenEvent,
    ToolCallEvent,
    UsageEvent,
)
from dot_contracts.tools import ToolResult

from backend.cognition.services.engine.react_engine import ReactEngine
from backend.cognition.services.engine.tool_runner import ToolRunner
from backend.cognition.services.engine.turn import Turn
from backend.cognition.services.interaction.agent_services import AgentServices
from backend.cognition.services.subagents.ephemeral import (
    ChildTrimmer,
    EphemeralStore,
    StaticCompiler,
)
from backend.cognition.services.subagents.types import (
    MAX_DEPTH,
    MAX_ITERATIONS,
    MAX_PROMPT_CHARS,
    SubagentType,
    clip_report,
    tool_names,
)
from backend.cognition.services.tools.registry import ToolContext, ToolRegistry
from backend.core.exceptions import DomainException
from backend.core.session_ids import child_id, root_of
from backend.governance.settings.schema import HookEvent
from backend.routing.clients.llm_types import LLMClient
from backend.routing.clients.sandbox_client import SandboxClient

logger = logging.getLogger(__name__)


class _Outcome:
    """What a child loop produced: last step text, stop reason, error text."""

    def __init__(self) -> None:
        self.buffer = ""
        self.report = ""
        self.stop = ""
        self.error = ""
        self.steps = 0


class SubagentRunner:
    def __init__(  # noqa: PLR0913
        self,
        *,
        llm: LLMClient,
        registry: ToolRegistry,
        agent: AgentServices,
        sandbox: SandboxClient,
        workspace: str,
        context_limit: int,
        slots: int,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._agent = agent
        self._sandbox = sandbox
        self._workspace = workspace
        self._limit = context_limit
        self._pool = asyncio.Semaphore(max(1, slots))
        # Nested runs are leaves (MAX_DEPTH): they never wait for another slot, so
        # they must not compete for the slots their ancestors hold (deadlock).
        self._nested = asyncio.Semaphore(max(1, slots))
        self._counters: dict[str, count] = {}

    def _next_id(self, parent: str) -> tuple[str, int]:
        n = next(self._counters.setdefault(parent, count(1)))
        return child_id(parent, n), n

    def _preload(self, registry: ToolRegistry, kind: SubagentType) -> None:
        """Add the type's deferred tools as already loaded (children have no ToolSearch)."""
        for name in kind.loaded:
            tool = self._registry.get(name)
            if tool is not None:
                live = tool.definition.model_copy(update={"deferred": False})
                registry.add(replace(tool, definition=live))

    def _engine(self, kind: SubagentType, ctx: ToolContext) -> ReactEngine:
        names = tool_names(kind, [d.name for d in self._registry.core_definitions()])
        registry = self._registry.subset(names)
        self._preload(registry, kind)
        parent_store = self._agent.store

        async def mode() -> str:
            return await parent_store.mode_of(ctx.session_pk)

        store = EphemeralStore(mode)
        runner = ToolRunner(
            registry=registry,
            gov=self._agent.gov,
            approvals=self._agent.approvals,
            store=store,  # type: ignore[arg-type]
            sandbox=self._sandbox,
            workspace=self._workspace,
            approval_timeout_s=self._agent.approval_timeout_s,
            agent=self._agent,
        )
        return ReactEngine(
            llm=self._llm,
            registry=registry,
            runner=runner,
            store=store,  # type: ignore[arg-type]
            compiler=StaticCompiler(kind.prompt),  # type: ignore[arg-type]
            cwd=self._workspace,
            context_limit=self._limit,
            max_iterations=MAX_ITERATIONS,
            compactor=ChildTrimmer(store, self._limit),  # type: ignore[arg-type]
        )

    async def run(
        self, ctx: ToolContext, kind: SubagentType, prompt: str
    ) -> ToolResult:
        if ctx.depth >= MAX_DEPTH or ctx.emit is None:
            return ToolResult(
                call_id="",
                output=f"Subagent depth limit ({MAX_DEPTH}) reached: do this yourself.",
                is_error=True,
            )
        root = root_of(ctx.session_id)
        sid, n = self._next_id(root)
        label = f"{kind.name} {n}"

        emit = ctx.emit

        def say(status: str, detail: str = "") -> None:
            emit(
                SubagentEvent(
                    label=label,
                    subagent_type=kind.name,
                    status=status,  # type: ignore[arg-type]
                    detail=detail,
                )
            )

        say("queued")
        pool = self._pool if ctx.depth == 0 else self._nested
        try:
            async with pool:
                say("started")
                result = await self._run_child(
                    ctx, kind, prompt[:MAX_PROMPT_CHARS], sid, label, say
                )
        except asyncio.CancelledError:
            say("finished", "cancelled")
            raise
        say("finished", "error" if result.is_error else "ok")
        return result

    async def _run_child(
        self,
        ctx: ToolContext,
        kind: SubagentType,
        prompt: str,
        sid: str,
        label: str,
        say,
    ) -> ToolResult:
        gov = self._agent.gov
        if gov.taint.has_taint(ctx.session_id):
            gov.taint.add(sid, "")  # inherit "follows untrusted input"
        turn = Turn(
            pk=ctx.session_pk,
            public_id=sid,
            depth=ctx.depth + 1,
            label=label,
            parent_id=root_of(ctx.session_id),
        )
        out = _Outcome()
        try:
            async for event in self._engine(kind, ctx).run(turn, prompt):
                self._relay(event, ctx.emit, label, say, out)
        finally:
            consumed = gov.taint.consumed(sid)
            gov.taint.reset(sid)
        report = self._report(out)
        report = await self._stop_hook(sid, kind, report)
        failed = bool(out.error)
        return ToolResult(
            call_id="", output=clip_report(report), is_error=failed, tainted=consumed
        )

    @staticmethod
    def _relay(event: Any, emit, label: str, say, out: _Outcome) -> None:
        if isinstance(event, TokenEvent):
            out.buffer += "" if event.thinking else event.text
        elif isinstance(event, UsageEvent):
            out.report = out.buffer if out.buffer.strip() else out.report
            out.buffer = ""
            out.steps += 1
        elif isinstance(event, ToolCallEvent):
            say("step", event.invocation.name)
        elif isinstance(event, SubagentEvent):
            emit(event)  # nested subagents stay visible to the UI
        elif isinstance(event, ApprovalRequiredEvent):
            emit(event.model_copy(update={"subagent": label}))
        elif isinstance(event, ErrorEvent):
            out.error = f"error {event.code}: {event.message}"
        elif isinstance(event, DoneEvent):
            out.stop = event.stop_reason

    @staticmethod
    def _report(out: _Outcome) -> str:
        if out.error:
            return (
                f"Subagent failed ({out.error}). Partial report: {out.report}".strip()
            )
        if out.stop == "max_iterations":
            return f"{out.report}\n[stopped at the iteration limit]".strip()
        return out.report

    async def _stop_hook(self, sid: str, kind: SubagentType, report: str) -> str:
        try:
            hook = await self._agent.gov.fire(
                HookEvent.SUBAGENT_STOP,
                sid,
                {"subagent_type": kind.name, "report": report},
            )
        except DomainException:
            return report
        if hook.blocked and hook.reason:
            return f"{report}\n[SubagentStop hook] {hook.reason}"
        return report
