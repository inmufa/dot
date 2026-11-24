"""App factory."""

import contextlib
import ctypes
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from dot_sandbox.errors import install_handlers
from dot_sandbox.routes import exec_, fs, internal, mcp
from dot_sandbox.runtime.mcp_bridge import McpBridge
from dot_sandbox.runtime.state import ReadTracker
from dot_sandbox.settings import Settings, get_settings
from dot_sandbox.shell import ShellManager

PR_SET_DUMPABLE = 4


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cfg.workspace.mkdir(parents=True, exist_ok=True)
        yield
        await app.state.shells.shutdown()
        await app.state.mcp.shutdown()

    app = FastAPI(title="dot-sandbox", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = cfg
    app.state.tracker = ReadTracker()
    cfg.workspace.mkdir(parents=True, exist_ok=True)
    app.state.shells = ShellManager(cfg.workspace.resolve(), cfg.max_background_jobs)
    app.state.mcp = McpBridge(cfg.max_mcp_servers)
    install_handlers(app)
    app.include_router(fs.router)
    app.include_router(exec_.router)
    app.include_router(internal.router)
    app.include_router(mcp.router)

    @app.get("/health", operation_id="health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def harden_process() -> None:
    """Non-dumpable: the agent's shells (same uid) cannot read /proc/<pid>/environ."""
    if sys.platform == "linux":
        with contextlib.suppress(Exception):
            ctypes.CDLL(None).prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)


def app_factory() -> FastAPI:
    harden_process()
    return create_app()
