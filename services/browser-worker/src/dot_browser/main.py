"""App factory."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from dot_browser.browser import BrowserManager
from dot_browser.errors import install_handlers
from dot_browser.guard import Resolver, UrlGuard
from dot_browser.routes import actions, tabs
from dot_browser.session import ClockFn
from dot_browser.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    *,
    resolver: Resolver | None = None,
    clock: ClockFn | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    guard = UrlGuard(cfg, resolver, **({"clock": clock} if clock else {}))
    manager = BrowserManager(cfg, guard, clock) if clock else BrowserManager(cfg, guard)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        reaper = asyncio.create_task(manager.reap_forever())
        yield
        reaper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reaper
        await manager.shutdown()

    app = FastAPI(title="dot-browser", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = cfg
    app.state.guard = guard
    app.state.manager = manager
    install_handlers(app)
    app.include_router(actions.router)
    app.include_router(tabs.router)

    @app.get("/health", operation_id="health")
    async def health() -> dict[str, object]:
        return {"status": "ok", "sessions": len(manager.sessions)}

    return app


def app_factory() -> FastAPI:
    """Production entry: refuses to serve without a token (compose may pass it empty)."""
    cfg = get_settings()
    if not cfg.token:
        msg = "DOT_BROWSER_TOKEN is empty: refusing to start an open browser worker"
        raise RuntimeError(msg)
    return create_app(cfg)
