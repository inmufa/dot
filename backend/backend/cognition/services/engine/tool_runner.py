"""Runs a batch of tool calls: governance, approvals, checkpoints, parallel reads."""

import asyncio
import json
import logging
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
    from backend.cognition.services.engine.images import ImageSource
    from backend.cognition.services.interaction.agent_services import AgentServices

logger = logging.getLogger(__name__)
PERMISSION_DENIED = 3000
ResultObserver = Callable[
    [Turn, ParsedToolCall, dict[str, Any], ToolResult], Awaitable[list[StreamEvent]]
]
CallGate = Callable[[Turn, ParsedToolCall], str | None]
_CHECKPOINTED = frozenset({"Write", "Edit"})


_PATH_ARGS = ("file_path", "path")


def _dealias_workspace(args: dict[str, Any], workspace: str) -> dict[str, Any]:
    """Models habitually write /workspace/... from generic agent training; whatever the
    real workspace root is (host mode uses the owner's own path), treat that prefix as
    an alias for it so the path lands where meant, instead of a literal root /workspace."""
    out = args
    for key in _PATH_ARGS:
        v = args.get(key)
        if isinstance(v, str) and (v == "/workspace" or v.startswith("/workspace/")):
            if out is args:
                out = dict(args)
            out[key] = workspace.rstrip("/") + v[len("/workspace") :]
    return out


_MAX_SAME_FAILS = 3
_MAX_TOOL_FAILS = 4  # consecutive errors from one tool, whatever the arguments
_MAX_SAME_REPEATS = (
    3  # identical call returning the identical result, even without an error
)


def _call_key(name: str, args: dict[str, Any]) -> str:
    return name + json.dumps(args, sort_keys=True, default=str)


def _loop_note(
    turn: Turn, name: str, args: dict[str, Any], result: ToolResult
) -> ToolResult:
    """Count identical failing calls; on the 3rd, tell the model to stop and report.
    Also catches a call that keeps "succeeding" with no progress - same tool, same
    arguments, repeated, regardless of whether the output text itself matches: a
    real page (Google's sign-in, for one) can embed a random token in every
    response, so comparing output text would never catch the loop."""
    turn.last_failed = result.is_error
    key = _call_key(name, args)
    if not result.is_error:
        turn.fail_counts.pop(name, None)  # the tool works again
        turn.repeat_counts[key] = turn.repeat_counts.get(key, 0) + 1
        if turn.repeat_counts[key] < _MAX_SAME_REPEATS:
            return result
        note = (
            "\n[That call keeps returning the same result with no progress. Stop "
            "repeating it: try something different, or tell the user what's stuck.]"
        )
        return result.model_copy(update={"output": result.output + note})
    by_tool = turn.fail_counts[name] = turn.fail_counts.get(name, 0) + 1
    turn.fail_counts[key] = turn.fail_counts.get(key, 0) + 1
    if turn.fail_counts[key] < _MAX_SAME_FAILS and by_tool < _MAX_TOOL_FAILS:
        return result
    note = (
        "\n[This tool keeps failing. Stop retrying it: use another way (for text, plain "
        "markdown) or tell the user plainly what is blocked.]"
    )
    return result.model_copy(update={"output": result.output + note})


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
        # Feature hooks (main agent): extra events after a tool result, and
        # gates that refuse a call with a model-readable error text.
        self.result_observers: list[ResultObserver] = []
        self.call_gates: list[CallGate] = []
        self._agent = agent
        self._registry = registry
        self._gov = gov
        self._approvals = approvals
        self._store = store
        self._sandbox = sandbox
        self._workspace = workspace
        self._timeout = approval_timeout_s
        self.images: ImageSource | None = None  # lets Read return image parts

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
            images=self.images,
        )

    async def _evaluate(
        self, turn: Turn, mode: str, call: ParsedToolCall
    ) -> Evaluation:
        tool = self._registry.get(call.name)
        if tool is None:  # unknown tool -> error result from execute()
            return Evaluation(call.arguments, PermissionResult(Decision.ALLOW))
        args = _dealias_workspace(call.arguments, self._workspace)
        allowed = self._approvals.allowed(turn.public_id)
        return await self._gov.evaluate(
            turn.public_id, mode, tool.definition, args, allowed
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
            async for event in self._finish(turn, call, e.arguments, result):
                yield event

    async def _exec(
        self,
        turn: Turn,
        queue: asyncio.Queue[StreamEvent],
        call: ParsedToolCall,
        args: dict[str, Any],
    ) -> ToolResult:
        ctx = self._ctx(turn, call, queue)
        key = _call_key(call.name, args)
        if turn.fail_counts.get(key, 0) >= _MAX_SAME_FAILS:
            text = (
                "This exact call already failed repeatedly and is blocked. Do not try "
                "it again: tell the user what is blocked and what you need from them."
            )
            return ToolResult(call_id=call.id, output=text, is_error=True)
        if turn.repeat_counts.get(key, 0) >= _MAX_SAME_REPEATS:
            text = (
                "This exact call already ran repeatedly with no progress and is blocked. "
                "Stop: tell the user plainly what you were trying to do and what's stuck, "
                "in words, with no more tool calls this turn."
            )
            return ToolResult(call_id=call.id, output=text, is_error=True)
        for gate in self.call_gates:
            if (refusal := gate(turn, call)) is not None:
                return ToolResult(call_id=call.id, output=refusal, is_error=True)
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
    ) -> AsyncIterator[StreamEvent]:
        result = await self._gov.after_tool(turn.public_id, call.name, args, result)
        result = _loop_note(turn, call.name, args, result)
        await self._store.append(
            turn.pk,
            "tool",
            result.output,
            tool_call_id=call.id,
            tainted=result.tainted,
            meta=_image_meta(result),
        )
        if self._on_result:
            await self._on_result(turn.public_id, call.name, args, result.is_error)
        turn.open_calls.pop(call.id, None)
        yield ToolResultEvent(result=result)
        for observer in self.result_observers:
            try:
                for extra in await observer(turn, call, args, result):
                    yield extra
            except Exception:
                logger.exception("result observer failed")

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
        async for event in self._finish(turn, call, ev.arguments, result):
            yield event

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
                diff=await self._describe(turn, call, ev.arguments),
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

    async def _describe(
        self, turn: Turn, call: ParsedToolCall, args: dict[str, Any]
    ) -> str | None:
        describe = self._registry.describers.get(call.name)
        if describe is not None:
            return await describe(args)
        return await approval_diff(
            self._ctx(turn, call, asyncio.Queue()), call.name, args
        )

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


def _image_meta(result: ToolResult) -> dict[str, Any] | None:
    if not result.image_path:
        return None
    name = result.image_path.rsplit("/", 1)[-1]
    return {"image": {"name": name, "path": result.image_path}}
