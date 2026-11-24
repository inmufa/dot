"""Runs a batch of tool calls: governance, approvals, checkpoints, parallel reads."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from itertools import groupby
from typing import TYPE_CHECKING, Any

from dot_contracts.events import (
    ApprovalRequiredEvent,
    StreamEvent,
    ToolResultEvent,
)
from dot_contracts.permissions import Decision, PermissionMode
from dot_contracts.tools import ToolInvocation, ToolResult

from backend.cognition.services.engine.turn import Turn
from backend.cognition.services.tools.diffs import approval_diff
from backend.cognition.services.tools.executor import execute
from backend.cognition.services.tools.fs_tools import abs_path
from backend.cognition.services.tools.registry import ToolContext, ToolRegistry
from backend.cognition.services.tools.stream_events import Done, drain
from backend.core.exceptions import DomainException
from backend.governance.services.approvals import ApprovalRegistry
from backend.governance.services.permission_engine import (
    PermissionResult,
    always_key,
)
from backend.governance.services.pipeline import Evaluation, Governance
from backend.governance.settings.schema import HookEvent
from backend.routing.clients.llm_types import ParsedToolCall
from backend.routing.clients.sandbox_client import SandboxClient
from backend.sessions.services.transcript import TranscriptStore

if TYPE_CHECKING:
    from backend.cognition.services.interaction.agent_services import AgentServices

PERMISSION_DENIED = 3000
_CHECKPOINTED = frozenset({"Write", "Edit"})


@dataclass
class _Box:
    """Carries the user's verdict out of an async generator."""

    verdict: PermissionResult


class ToolRunner:
    def __init__(  # noqa: PLR0913
        self,
        *,
        registry: ToolRegistry,
        gov: Governance,
        approvals: ApprovalRegistry,
        store: TranscriptStore,
        sandbox: SandboxClient,
        workspace: str,
        approval_timeout_s: float,
        agent: "AgentServices | None" = None,
        on_result: Callable[[str, str, dict[str, Any], bool], Awaitable[None]]
        | None = None,
    ) -> None:
        self._on_result = on_result  # session, tool, args, is_error
        self._agent = agent
        self._registry = registry
        self._gov = gov
        self._approvals = approvals
        self._store = store
        self._sandbox = sandbox
        self._workspace = workspace
        self._timeout = approval_timeout_s

    def _serial_only(self, call: ParsedToolCall) -> bool:
        """Calls that must not run alongside others (mutating, or per-call rule)."""
        tool = self._registry.get(call.name)
        if tool is None:
            return False
        if tool.concurrent is not None:
            return not tool.concurrent(call.arguments)
        return tool.definition.mutating

    def _ctx(
        self, turn: Turn, call: ParsedToolCall, queue: asyncio.Queue[StreamEvent]
    ) -> ToolContext:
        return ToolContext(
            turn.public_id,
            self._sandbox,
            self._workspace,
            call_id=call.id,
            session_pk=turn.pk,
            depth=turn.depth,
            label=turn.label,
            emit=queue.put_nowait,
            agent=self._agent,
        )

    async def _evaluate(
        self, turn: Turn, mode: str, call: ParsedToolCall
    ) -> Evaluation:
        tool = self._registry.get(call.name)
        if tool is None:  # unknown tool -> error result from execute()
            return Evaluation(call.arguments, PermissionResult(Decision.ALLOW))
        allowed = self._approvals.allowed(turn.public_id)
        return await self._gov.evaluate(
            turn.public_id, mode, tool.definition, call.arguments, allowed
        )

    async def run(
        self, turn: Turn, calls: list[ParsedToolCall]
    ) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        for mutating, group in groupby(calls, key=self._serial_only):
            batch = list(group)
            if not mutating:
                mode = await self._store.mode_of(turn.pk)
                evals = [await self._evaluate(turn, mode, c) for c in batch]
                if all(e.verdict.decision == Decision.ALLOW for e in evals):
                    async for event in self._parallel(turn, queue, batch, evals):
                        yield event
                    continue
                pairs = list(zip(batch, evals, strict=True))
            else:
                pairs = [(c, None) for c in batch]
            for call, ev in pairs:
                async for event in self._serial(turn, queue, call, ev):
                    yield event

    async def _parallel(
        self,
        turn: Turn,
        queue: asyncio.Queue[StreamEvent],
        batch: list[ParsedToolCall],
        evals: list[Evaluation],
    ) -> AsyncIterator[StreamEvent]:
        work = asyncio.gather(
            *(
                self._exec(turn, queue, c, e.arguments)
                for c, e in zip(batch, evals, strict=True)
            )
        )
        results: list[ToolResult] = []
        async for item in drain(queue, work):
            if isinstance(item, Done):
                results = item.value
            else:
                yield item
        for call, e, result in zip(batch, evals, results, strict=True):
            yield await self._finish(turn, call, e.arguments, result)

    async def _exec(
        self,
        turn: Turn,
        queue: asyncio.Queue[StreamEvent],
        call: ParsedToolCall,
        args: dict[str, Any],
    ) -> ToolResult:
        ctx = self._ctx(turn, call, queue)
        if not self._activated(turn, call.name):
            text = (
                f"Tool '{call.name}' is deferred and not loaded. "
                f"Call ToolSearch with query 'select:{call.name}' first."
            )
            return ToolResult(call_id=call.id, output=text, is_error=True)
        if call.name in _CHECKPOINTED and isinstance(args.get("file_path"), str):
            try:
                await self._gov.checkpoints.record(
                    turn.pk,
                    turn.parent_id or turn.public_id,  # checkpoints live on the root
                    call.id,
                    abs_path(ctx, args["file_path"]) or "",
                )
            except DomainException as exc:
                text = (
                    f"Checkpoint failed (error code {exc.code}); nothing was changed."
                )
                return ToolResult(call_id=call.id, output=text, is_error=True)
        return await execute(self._registry, ctx, call.name, call.id, args)

    def _activated(self, turn: Turn, name: str) -> bool:
        tool = self._registry.get(name)
        if tool is None or not tool.definition.deferred:
            return True
        active = self._agent.activations.names(turn.public_id) if self._agent else []
        return name in active

    async def _finish(
        self,
        turn: Turn,
        call: ParsedToolCall,
        args: dict[str, Any],
        result: ToolResult,
    ) -> StreamEvent:
        result = await self._gov.after_tool(turn.public_id, call.name, args, result)
        await self._store.append(
            turn.pk, "tool", result.output, tool_call_id=call.id, tainted=result.tainted
        )
        if self._on_result:
            await self._on_result(turn.public_id, call.name, args, result.is_error)
        turn.open_calls.pop(call.id, None)
        return ToolResultEvent(result=result)

    async def _serial(
        self,
        turn: Turn,
        queue: asyncio.Queue[StreamEvent],
        call: ParsedToolCall,
        ev: Evaluation | None,
    ) -> AsyncIterator[StreamEvent]:
        mode = await self._store.mode_of(turn.pk)
        ev = ev or await self._evaluate(turn, mode, call)
        box = _Box(ev.verdict)
        if ev.verdict.decision == Decision.ASK:
            async for event in self._ask(turn, call, ev, mode, box):
                yield event
        if box.verdict.decision == Decision.ALLOW:
            result = ToolResult(call_id=call.id, output="")
            async for item in drain(queue, self._exec(turn, queue, call, ev.arguments)):
                if isinstance(item, Done):
                    result = item.value
                else:
                    yield item
        else:
            result = ToolResult(
                call_id=call.id, output=self._denial(ev, box.verdict), is_error=True
            )
        yield await self._finish(turn, call, ev.arguments, result)

    @staticmethod
    def _denial(ev: Evaluation, verdict: PermissionResult) -> str:
        if ev.block_text is not None:
            return f"Blocked by a PreToolUse hook: {ev.block_text}"
        return (
            f"Denied (error {PERMISSION_DENIED}): {verdict.reason}. "
            "Do not retry this call."
        )

    async def _ask(
        self,
        turn: Turn,
        call: ParsedToolCall,
        ev: Evaluation,
        mode: str,
        box: _Box,
    ) -> AsyncIterator[StreamEvent]:
        approval_id = self._approvals.create(turn.public_id)
        self._gov.fire_in_background(
            HookEvent.NOTIFICATION,
            turn.public_id,
            {
                "message": f"Dot needs approval to run {call.name}",
                "tool_name": call.name,
            },
        )
        try:
            yield ApprovalRequiredEvent(
                approval_id=approval_id,
                invocation=ToolInvocation(
                    call_id=call.id, name=call.name, arguments=ev.arguments
                ),
                diff=await approval_diff(
                    self._ctx(turn, call, asyncio.Queue()), call.name, ev.arguments
                ),
                verdict=ev.classifier,
            )
            decision = await self._approvals.wait(approval_id, self._timeout)
        finally:
            self._approvals.discard(approval_id)
        verdict = self._apply_decision(turn, call, ev.arguments, decision)
        if verdict.decision == Decision.ALLOW and (
            await self._store.mode_of(turn.pk) == PermissionMode.PLAN
        ):
            # The mode changed to plan while the user was deciding.
            verdict = PermissionResult(Decision.DENY, "plan mode is read-only")
        await self._gov.record_user(
            turn.public_id, mode, call.name, ev.arguments, verdict.decision, decision
        )
        box.verdict = verdict

    def _apply_decision(
        self, turn: Turn, call: ParsedToolCall, args: dict[str, Any], decision: str
    ) -> PermissionResult:
        if decision == "reject":
            return PermissionResult(
                Decision.DENY, "the user rejected this tool call", "user"
            )
        if decision == "always":
            self._approvals.allowed(turn.public_id).add(always_key(call.name, args))
        return PermissionResult(Decision.ALLOW, "approved by the user", "user")

    async def cancel_open(self, turn: Turn, text: str) -> None:
        """Close dangling tool calls so the transcript stays well-formed."""
        for call_id in list(turn.open_calls):
            await self._store.append(turn.pk, "tool", text, tool_call_id=call_id)
        turn.open_calls.clear()
