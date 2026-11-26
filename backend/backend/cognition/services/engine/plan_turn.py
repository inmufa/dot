"""`plan: true`: one read-only turn using the plan-mode mechanism, mode restored after."""

import logging

from dot_contracts.permissions import PermissionMode

from backend.cognition.services.engine.turn import Turn
from backend.cognition.services.interaction.agent_services import AgentServices

logger = logging.getLogger(__name__)
PLAN = PermissionMode.PLAN.value
PLAN_REMINDER = (
    "<system-reminder>\nPlan turn: explore with read-only tools, then call "
    "ExitPlanMode with the plan in markdown. Do not change anything yet.\n"
    "</system-reminder>"
)


RESEARCH_PLAN_REMINDER = (
    "<system-reminder>\nResearch plan turn: do NOT search yet. Call ExitPlanMode with a "
    "short research plan in markdown: the question restated, 3-6 numbered sub-questions, "
    "the kinds of sources you will prefer, and the shape of the final report. "
    "The user may edit it before you start.\n</system-reminder>"
)


def wants_plan(turn: Turn) -> bool:
    return bool(turn.options.plan or turn.options.research)


async def begin(agent: AgentServices, turn: Turn) -> None:
    """Switch to plan mode for this turn (remembering the mode to return to)."""
    if not wants_plan(turn) or turn.depth:
        return
    mode = await agent.store.mode_of(turn.pk)
    if mode == PLAN:
        return  # already planning: nothing to restore
    agent.previous_mode[turn.public_id] = mode
    await agent.sessions.set_mode(turn.public_id, PLAN)
    turn.plan_restore = mode


async def end(agent: AgentServices, turn: Turn) -> None:
    """Put the previous mode back unless ExitPlanMode or the user already did."""
    mode = turn.plan_restore
    if mode is None:
        return
    turn.plan_restore = None
    try:
        if await agent.store.mode_of(turn.pk) == PLAN and (
            agent.previous_mode.pop(turn.public_id, None) is not None
        ):
            await agent.sessions.set_mode(turn.public_id, mode)
    except Exception:
        logger.exception("could not restore the mode after a plan turn")
