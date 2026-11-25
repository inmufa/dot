"""Wiring for research (F6), projects (F7) and telemetry/models (F8)."""

from backend.bootstrap.phase5 import Closer, Phase5Deps
from backend.cognition.services.engine.turn import Turn
from backend.cognition.services.research import ResearchMode
from backend.core.exceptions import DomainException
from backend.routing.services.telemetry import TelemetryService
from backend.sessions.services.projects.service import ProjectService
from backend.sessions.services.session_service import SessionService
from backend.voice.client import VoiceClient


async def build_features_e(d: Phase5Deps) -> list[Closer]:
    ResearchMode(d.settings).install(d.react, d.react.runner)
    workspace = str(d.settings.workspace.absolute())
    projects = ProjectService(d.maker, d.sandbox, workspace)
    sessions = SessionService(d.maker)

    async def project_of(session: str) -> str | None:
        try:
            return (await sessions.get(session)).project
        except DomainException:
            return None  # subagent ids and unknown sessions have no project

    async def project_reminder(turn: Turn) -> str:
        name = await project_of(turn.public_id)
        return await projects.reminder(name) if name else ""

    d.react.reminder_providers.append(project_reminder)
    d.app.state.tiers.project_of = project_of
    d.app.state.projects = projects
    voice = VoiceClient(d.settings.voice_url, d.settings.voice_token)
    d.app.state.voice = voice
    d.app.state.voice_buckets = {}
    telemetry = TelemetryService(d.settings, d.sandbox, voice=voice)
    d.app.state.telemetry = telemetry
    return [telemetry.aclose, voice.aclose]
