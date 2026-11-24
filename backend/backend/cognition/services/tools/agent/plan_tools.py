"""EnterPlanMode / ExitPlanMode: read-only planning with a user approval gate."""

from typing import Any

from dot_contracts.events import ApprovalRequiredEvent
from dot_contracts.permissions import Decision, PermissionMode
from dot_contracts.tools import ToolDefinition, ToolInvocation, ToolResult

from backend.cognition.services.interaction.agent_services import AgentServices
from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.core.exceptions import DomainException
from backend.governance.services.approvals import APPROVAL_TIMEOUT

PLAN = PermissionMode.PLAN.value
DEFAULT = PermissionMode.DEFAULT.value


def _fail(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text, is_error=True)


async def _switch(
    ctx: ToolContext, agent: AgentServices, tool: str, old: str, new: str
) -> None:
    await agent.sessions.set_mode(ctx.session_id, new)
    await agent.gov.audit.append(
        session=ctx.session_id,
        mode=old,
        tool=tool,
        args={"from": old, "to": new},
        decision=Decision.ALLOW.value,
        source="mode",
        reason=f"session mode changed {old} -> {new}",
    )


async def run_enter(ctx: ToolContext, _a: dict[str, Any]) -> ToolResult:
    if ctx.agent is None:
        return _fail("Plan mode is not available here.")
    mode = await ctx.agent.store.mode_of(ctx.session_pk)
    if mode == PLAN:
        return ToolResult(call_id="", output="Already in plan mode.")
    ctx.agent.previous_mode[ctx.session_id] = mode
    await _switch(ctx, ctx.agent, "EnterPlanMode", mode, PLAN)
    return ToolResult(
        call_id="",
        output=(
            "Plan mode is on: only read-only tools work. Explore, then call "
            "ExitPlanMode with the plan in markdown for the user to approve."
        ),
    )


async def _approve(ctx: ToolContext, agent: AgentServices, plan: str) -> str:
    """The user's decision on a plan: allow | always | reject."""
    approvals = agent.approvals
    aid = approvals.create(ctx.session_id)
    try:
        if ctx.emit is not None:
            ctx.emit(
                ApprovalRequiredEvent(
                    approval_id=aid,
                    invocation=ToolInvocation(
                        call_id=ctx.call_id,
                        name="ExitPlanMode",
                        arguments={"plan": plan},
                    ),
                    diff=plan,
                )
            )
        return await approvals.wait(aid, agent.approval_timeout_s)
    finally:
        approvals.discard(aid)


async def run_exit(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
    agent = ctx.agent
    if agent is None:
        return _fail("Plan mode is not available here.")
    if await agent.store.mode_of(ctx.session_pk) != PLAN:
        return _fail("Not in plan mode; nothing to exit.")
    plan = str(a["plan"])
    try:
        decision = await _approve(ctx, agent, plan)
    except DomainException as exc:
        if exc.code != APPROVAL_TIMEOUT:
            raise
        return _fail(
            "The user did not respond to the plan in time. Still in plan mode."
        )
    approved = decision != "reject"
    await agent.gov.record_user(
        ctx.session_id,
        PLAN,
        "ExitPlanMode",
        {"plan": plan},
        Decision.ALLOW if approved else Decision.DENY,
        decision,
    )
    if not approved:
        return _fail("The user rejected the plan. Stay in plan mode and revise it.")
    await agent.store.append(ctx.session_pk, "plan", plan)
    back = agent.previous_mode.pop(ctx.session_id, DEFAULT)
    if back == PLAN:
        back = DEFAULT
    await _switch(ctx, agent, "ExitPlanMode", PLAN, back)
    return ToolResult(
        call_id="", output=f"Plan approved. Mode is now {back}. Carry out the plan."
    )


ENTER_PLAN = Tool(
    ToolDefinition(
        name="EnterPlanMode",
        mutating=False,
        description="Switch to plan mode: read-only exploration before a risky or large change.",
        input_schema={"type": "object", "properties": {}, "required": []},
    ),
    run_enter,
)
EXIT_PLAN = Tool(
    ToolDefinition(
        name="ExitPlanMode",
        mutating=False,
        description=(
            "Present the finished plan (markdown) for user approval. On approval "
            "the previous mode returns and you can start editing."
        ),
        input_schema={
            "type": "object",
            "properties": {"plan": {"type": "string"}},
            "required": ["plan"],
        },
    ),
    run_exit,
)
