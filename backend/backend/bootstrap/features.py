"""Wiring for the UI-features batch: services bound to `app.state`, hooks on the engine."""

from backend.bootstrap.features_d import build_features_d
from backend.bootstrap.features_e import build_features_e
from backend.bootstrap.phase5 import Closer, Phase5Deps
from backend.cognition.services.engine.effort.provider import EffortProvider
from backend.cognition.services.engine.plan_turn import (
    PLAN_REMINDER,
    RESEARCH_PLAN_REMINDER,
)
from backend.sessions.services.session_service import SessionService


def _effort(d: Phase5Deps) -> None:
    provider = EffortProvider(d.llm, SessionService(d.maker))

    async def plan_reminder(turn) -> str:
        if turn.options.research and not turn.options.plan:
            return RESEARCH_PLAN_REMINDER
        return PLAN_REMINDER if turn.options.plan else ""

    d.react.reminder_providers.extend([provider.reminder, plan_reminder])
    d.react.options_provider = provider.options


async def build_features(d: Phase5Deps) -> list[Closer]:
    """One block per feature; each binds its service and returns its closers."""
    _effort(d)
    return [*await build_features_d(d), *await build_features_e(d)]
