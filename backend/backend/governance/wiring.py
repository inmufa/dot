"""Builds the governance object graph for the app."""

from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.engine.turn import TurnRegistry
from backend.governance.services.audit import AuditService
from backend.governance.services.auto_classifier import AutoClassifier
from backend.governance.services.checkpoints import CheckpointService
from backend.governance.services.hooks_engine import HooksEngine
from backend.governance.services.path_resolver import PathResolver
from backend.governance.services.permission_engine import PermissionEngine
from backend.governance.services.pipeline import Governance
from backend.governance.services.rules import RuleContext
from backend.governance.services.taint import TaintStore
from backend.governance.settings.loader import SettingsProvider
from backend.routing.clients.sandbox_client import SandboxClient
from backend.sessions.services.transcript import TranscriptStore
from backend.settings import Settings


def build_governance(
    settings: Settings,
    maker: async_sessionmaker,
    store: TranscriptStore,
    sandbox: SandboxClient,
    turns: TurnRegistry,
) -> Governance:
    workspace = settings.workspace.absolute()
    provider = SettingsProvider(
        workspace, settings.user_settings_path, settings.default_permissions_path
    )
    ctx = RuleContext(workspace=str(workspace), home=str(Path.home()))
    taint = TaintStore()
    gov = Governance(
        settings=provider,
        perms=PermissionEngine(provider.rules, ctx),
        hooks=HooksEngine(sandbox, str(workspace)),
        classifier=AutoClassifier(taint, str(workspace)),
        audit=AuditService(maker),
        checkpoints=CheckpointService(maker, store, sandbox, turns, taint.reset),
    )
    gov.resolver = PathResolver(sandbox)
    return gov
