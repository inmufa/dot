import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI

from backend.bootstrap.feature_routers import include_feature_routers
from backend.bootstrap.runtime import build_runtime
from backend.cognition.api.agent_tools import router as agent_tools_router
from backend.cognition.api.chat import router as chat_router
from backend.cognition.api.skills import router as skills_router
from backend.cognition.api.tools_list import router as tools_list_router
from backend.cognition.models import Task as _Task  # noqa: F401  (registers tables)
from backend.core.api.handler import install_handlers
from backend.core.api.health import router as health_router
from backend.core.api.startup import StartupError, exit_with, load_settings
from backend.core.logging import register_secret, setup_logging
from backend.core.middleware import (
    BodyLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from backend.governance import models as _gov_models  # noqa: F401  (registers tables)
from backend.governance.api.approvals import router as approvals_router
from backend.governance.api.audit import router as audit_router
from backend.governance.api.rewind import router as rewind_router
from backend.mcp import models as _mcp_models  # noqa: F401  (registers tables)
from backend.mcp.api.router import router as mcp_router
from backend.memory import models as _memory_models  # noqa: F401  (registers tables)
from backend.memory.api.router import router as memory_router
from backend.routing.clients.llm_types import LLMClient
from backend.routing.clients.sandbox_client import SandboxClient
from backend.scheduler import models as _sched_models  # noqa: F401  (registers tables)
from backend.scheduler.api.router import router as schedules_router
from backend.sessions import models as _models  # noqa: F401  (registers tables)
from backend.sessions.api.context import router as context_router
from backend.sessions.api.router import router as sessions_router
from backend.sessions.services.session_admin import SessionAdmin
from backend.sessions.services.workspace import models as _ws_models  # noqa: F401  (registers tables)
from backend.settings import Settings
from backend.vault import models as _vault_models  # noqa: F401  (registers tables)


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    sandbox: SandboxClient | None = None,
) -> FastAPI:
    """Build the app. `llm` and `sandbox` can be injected (tests, alt backends)."""
    if settings is None:
        try:
            settings = load_settings()
        except StartupError as exc:
            exit_with(exc)
    setup_logging(as_json=settings.log_json)
    for secret in (
        settings.api_token,
        settings.sandbox_token,
        settings.browser_token,
        settings.voice_token,
    ):
        register_secret(secret)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = await build_runtime(app, settings, llm, sandbox)
        try:
            gone = await SessionAdmin(app.state.sessions).purge_empty(
                timedelta(hours=12)
            )
            if gone:
                logging.getLogger(__name__).info("purged %d empty chats", gone)
            yield
        finally:  # stop running turns first, then MCP, scheduler, clients, DB
            await app.state.turns.cancel_all()
            await runtime.close()

    dev = settings.env != "prod"  # Swagger and the schema are dev-only
    app = FastAPI(
        title="Dot",
        lifespan=lifespan,
        docs_url="/docs" if dev else None,
        openapi_url="/openapi.json" if dev else None,
        redoc_url=None,
    )
    upload_limit = settings.upload_max_files * settings.upload_max_bytes + 1_048_576
    app.add_middleware(
        BodyLimitMiddleware,
        limit=settings.max_body_bytes,
        route_limits=[
            (re.compile(r"/v1/sessions/[^/]+/attachments"), upload_limit),
            (
                re.compile(r"/v1/voice/transcribe"),
                settings.voice_max_audio_bytes + 1024,
            ),
        ],
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)  # no CORS middleware: API is closed
    install_handlers(app)
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(context_router)
    app.include_router(memory_router)
    app.include_router(chat_router)
    app.include_router(skills_router)
    app.include_router(approvals_router)
    app.include_router(audit_router)
    app.include_router(rewind_router)
    app.include_router(agent_tools_router)
    app.include_router(mcp_router)
    app.include_router(schedules_router)
    app.include_router(tools_list_router)
    include_feature_routers(app)
    return app
