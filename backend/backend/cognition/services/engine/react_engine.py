"""ReAct loop: stream the model, run tools, feed results back until done."""

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from dot_contracts.events import (
    DoneEvent,
    ErrorEvent,
    StreamEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)
from dot_contracts.tools import ToolInvocation, ToolResult

from backend.cognition.services.context.engine_support import EngineContext
from backend.cognition.services.context.tiers import ContextTiers
from backend.cognition.services.engine.history import to_chat_messages
from backend.cognition.services.engine.prompt_compiler import PromptCompiler
from backend.cognition.services.engine.tool_runner import ToolRunner
from backend.cognition.services.engine.turn import Turn
from backend.cognition.services.interaction.agent_services import AgentServices
from backend.cognition.services.skill_loader import SkillRegistry
from backend.cognition.services.tools.registry import ToolRegistry
from backend.core.api.envelope import build_envelope
from backend.core.exceptions import DomainException
from backend.governance.services.approvals import APPROVAL_TIMEOUT
from backend.governance.services.pipeline import Governance
from backend.governance.settings.schema import HookEvent
from backend.routing.clients.llama_parse import new_call_id
from backend.routing.clients.llm_types import (
    LLMClient,
    LLMFinish,
    ParsedToolCall,
    TextDelta,
)
from backend.sessions.models import Message
from backend.sessions.services.compactor import Compactor
from backend.sessions.services.transcript import TranscriptStore, estimate_tokens

logger = logging.getLogger(__name__)
MALFORMED_CODE = 4003
PROMPT_BLOCKED = 3006
INTERNAL_ERROR = 1000
_CORRECTION = (
    "Error: this tool call was not valid ({why}). Re-send it with arguments "
    "that are a valid JSON object matching the tool schema."
)
_EMPTY_NUDGE = (
    "<system-reminder>\nYour last reply had no visible answer. "
    "Reply to the user now.\n</system-reminder>"
)
_PROMOTE_MAX = 1200
_SKIPPED = "Skipped: another tool call in the same message was malformed. Re-send it."


def _stored_calls(calls: list[ParsedToolCall]) -> list[dict[str, Any]]:
    return [
        {
            "id": c.id,
            "type": "function",
            "function": {
                "name": c.name,
                # Always valid JSON: llama-server re-parses stored arguments, and a
                # raw malformed string would make every later request fail.
                "arguments": json.dumps(c.arguments),
            },
        }
        for c in calls
    ]


def _unique_ids(
    calls: list[ParsedToolCall], rows: list[Message]
) -> list[ParsedToolCall]:
    """Give every call an id never seen in this transcript (stored ids must pair up)."""
    used = {
        str(tc.get("id"))
        for r in rows
        if r.role == "assistant"
        for tc in r.tool_calls or []
    }
    for c in calls:
        if not c.id or c.id in used:
            c.id = new_call_id()
        used.add(c.id)
    return calls


def _promote(reasoning: str) -> str:
    """Visible fallback: the last paragraphs of the reasoning, within a size cap."""
    kept: list[str] = []
    size = 0
    for para in reversed(reasoning.strip().split("\n\n")):
        if kept and size + len(para) > _PROMOTE_MAX:
            break
        kept.append(para)
        size += len(para) + 2
    return "\n\n".join(reversed(kept))[-_PROMOTE_MAX:].strip()


def _context_used(finish: LLMFinish, messages: list[dict[str, Any]]) -> int:
    return finish.prompt_tokens or sum(
        estimate_tokens(str(m.get("content"))) for m in messages
    )


class ReactEngine:
    def __init__(  # noqa: PLR0913
        self,
        *,
        llm: LLMClient,
        registry: ToolRegistry,
        runner: ToolRunner,
        store: TranscriptStore,
        compiler: PromptCompiler,
        cwd: str,
        context_limit: int,
        max_iterations: int,
        skills: SkillRegistry | None = None,
        gov: Governance | None = None,
        agent: AgentServices | None = None,
        compactor: Compactor | None = None,
        tiers: ContextTiers | None = None,
    ) -> None:
        self._ctx = EngineContext(compiler, compactor, tiers)
        self._agent = agent
        self._skills = skills
        self._gov = gov
        self._llm = llm
        self._registry = registry
        self._runner = runner
        self._store = store
        self._compiler = compiler
        self._cwd = cwd
        self._limit = context_limit
        self._max = max_iterations

    def _error(self, turn: Turn, code: int) -> ErrorEvent:
        _, body = build_envelope(code, turn.lang)
        return ErrorEvent(code=code, message=body["messages"][0])

    async def run(self, turn: Turn, user_text: str) -> AsyncIterator[StreamEvent]:
        self._ctx.begin_turn(turn.public_id)
        mode = await self._store.mode_of(turn.pk)
        hint = self._skills.hint(user_text) if self._skills else ""
        reminder = self._compiler.reminder(mode, self._cwd, datetime.now(UTC), hint)
        if self._agent:
            reminder += await self._agent.reminder_extra(turn.public_id)
        if extra := self._ctx.take_reminder(turn.public_id):
            reminder += f"\n{extra}"
        if blocked := await self._gate_prompt(turn, user_text):
            for event in blocked:
                yield event
            return
        await self._store.append(turn.pk, "user", user_text, reminder=reminder)
        try:
            async for event in self._loop(turn):
                yield event
        except DomainException as exc:
            await self._runner.cancel_open(turn, "Cancelled: the turn failed.")
            yield self._error(turn, exc.code)
            reason = "approval_timeout" if exc.code == APPROVAL_TIMEOUT else "error"
            yield DoneEvent(stop_reason=reason)
        except Exception:
            logger.exception("turn crashed")
            await self._runner.cancel_open(turn, "Cancelled: the turn failed.")
            yield self._error(turn, INTERNAL_ERROR)
            yield DoneEvent(stop_reason="error")

    @staticmethod
    def _announce(turn: Turn, calls: list[ParsedToolCall]) -> list[StreamEvent]:
        turn.open_calls.update(dict.fromkeys(c.id for c in calls))
        return [
            ToolCallEvent(
                invocation=ToolInvocation(
                    call_id=c.id, name=c.name, arguments=c.arguments
                )
            )
            for c in calls
        ]

    async def _gate_prompt(self, turn: Turn, text: str) -> list[StreamEvent]:
        """Reset taint, fire SessionStart/UserPromptSubmit hooks; events if blocked."""
        if self._gov is None:
            return []
        sid = turn.public_id
        self._gov.taint.user_turn(sid)
        try:
            if await self._store.last_seq(turn.pk) == 0:
                await self._gov.fire(HookEvent.SESSION_START, sid, {})
            out = await self._gov.fire(
                HookEvent.USER_PROMPT_SUBMIT, sid, {"prompt": text}
            )
        except DomainException as exc:
            return [self._error(turn, exc.code), DoneEvent(stop_reason="error")]
        if not out.blocked:
            return []
        message = ErrorEvent(code=PROMPT_BLOCKED, message=out.reason)
        return [message, DoneEvent(stop_reason="blocked")]

    async def _stop_hook_blocks(self, turn: Turn) -> bool:
        """Stop hook exit 2 sends its stderr back to the model, once per turn."""
        if self._gov is None or turn.stop_hooked:
            return False
        out = await self._gov.fire(HookEvent.STOP, turn.public_id, {})
        if not out.blocked:
            return False
        turn.stop_hooked = True
        await self._store.append(turn.pk, "user", f"[Stop hook] {out.reason}")
        return True

    async def abort(self, turn: Turn) -> StreamEvent:
        """Called by the pump after a stop: close open calls, return the final event."""
        await self._runner.cancel_open(turn, "Cancelled by the user.")
        return DoneEvent(stop_reason="cancelled")

    @property
    def prefix_text(self) -> str:
        return self._compiler.prefix

    def system_for(self, suffix: str) -> str:
        return self._ctx.system_for(suffix)

    async def _loop(self, turn: Turn) -> AsyncIterator[StreamEvent]:  # noqa: C901
        for _ in range(self._max):
            finish = LLMFinish()
            text = ""
            thought = ""
            system = await self._ctx.system(turn.public_id)
            for compacted in await self._ctx.precompact(
                turn.pk, turn.public_id, system
            ):
                yield compacted
            rows = await self._store.load(turn.pk)
            messages = to_chat_messages(await self._ctx.system(turn.public_id), rows)
            active = (
                self._agent.activations.names(turn.public_id) if self._agent else []
            )
            async for item in self._llm.stream(
                messages, self._registry.openai_schemas(active)
            ):
                if isinstance(item, TextDelta):
                    if item.thinking:
                        thought += item.text
                    else:
                        text += item.text
                    yield TokenEvent(text=item.text, thinking=item.thinking)
                else:
                    finish = item
            calls = _unique_ids(finish.tool_calls, await self._store.load(turn.pk))
            nudge, promoted = self._empty_reply(turn, calls, text, thought)
            if promoted:
                text = promoted
                yield TokenEvent(text=text)
            await self._record(turn, calls, text, thought, promoted=bool(promoted))
            if nudge:  # append-only: the empty reply stays, a reminder row follows
                await self._store.append(turn.pk, "user", _EMPTY_NUDGE)
            seq = max((r.seq for r in rows), default=0)
            self._ctx.observe(turn.pk, finish.prompt_tokens, seq)
            used = _context_used(finish, messages)
            yield UsageEvent(context_tokens=used, context_limit=self._limit)
            if nudge:
                continue
            async for event in self._act(turn, calls):
                yield event
                if isinstance(event, DoneEvent):
                    return
        yield DoneEvent(stop_reason="max_iterations")

    async def _record(
        self,
        turn: Turn,
        calls: list[ParsedToolCall],
        text: str,
        thought: str,
        *,
        promoted: bool,
    ) -> None:
        await self._store.append(
            turn.pk,
            "assistant",
            text,
            tool_calls=_stored_calls(calls) or None,
            reasoning=thought,
            meta={"reasoning_promoted": True} if promoted else None,
        )

    @staticmethod
    def _empty_reply(
        turn: Turn, calls: list[ParsedToolCall], text: str, thought: str
    ) -> tuple[bool, str]:
        """(send the nudge, promoted text) for a reply with no visible answer."""
        if calls or text.strip():
            return False, ""
        if not turn.empty_retried:
            turn.empty_retried = True
            return True, ""
        return False, _promote(thought)

    async def _act(
        self, turn: Turn, calls: list[ParsedToolCall]
    ) -> AsyncIterator[StreamEvent]:
        """Handle one model reply; a DoneEvent means the turn is over."""
        if not calls:
            if not await self._stop_hook_blocks(turn):
                yield DoneEvent(stop_reason="end_turn")
            return
        for announced in self._announce(turn, calls):
            yield announced
        if any(c.error for c in calls):
            for result in await self._reject_malformed(turn, calls):
                yield result
            if turn.malformed_streak > 1:
                yield self._error(turn, MALFORMED_CODE)
                yield DoneEvent(stop_reason="error")
            return
        turn.malformed_streak = 0
        async for event in self._runner.run(turn, calls):
            yield event

    async def _reject_malformed(
        self, turn: Turn, calls: list[ParsedToolCall]
    ) -> list[ToolResultEvent]:
        """Answer every call with an error; the caller checks the retry budget."""
        turn.malformed_streak += 1
        events = []
        for c in calls:
            text = _CORRECTION.format(why=c.error) if c.error else _SKIPPED
            await self._store.append(turn.pk, "tool", text, tool_call_id=c.id)
            events.append(
                ToolResultEvent(
                    result=ToolResult(call_id=c.id, output=text, is_error=True)
                )
            )
        turn.open_calls.clear()
        return events
