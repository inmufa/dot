"""Vault startup: service, agent, session refresh timer."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from backend.bootstrap.phase5 import Phase5Deps
from backend.cognition.services.tools.web.browser_client import BrowserClient
from backend.vault.agent import VaultAgent
from backend.vault.service import VaultService
from backend.vault.worker import VaultWorker

logger = logging.getLogger(__name__)
Closer = Callable[[], Awaitable[None]]


async def build_vault(d: Phase5Deps) -> list[Closer]:
    s = d.settings
    browser = d.registry.browser or BrowserClient(s.browser_url, s.browser_token)
    agent = VaultAgent(VaultService(d.maker, d.gov.audit, s), VaultWorker(browser))
    d.app.state.vault = agent
    if d.registry.vault is not None:
        d.registry.vault.agent = agent
        d.registry.describers["BrowserLogin"] = agent.describe
    view = getattr(d.app.state, "browser_view", None)
    if view is not None:
        view.vault = agent
    if not agent.svc.enabled:
        return []

    async def timer() -> None:
        while True:
            await asyncio.sleep(s.vault_session_refresh_s)
            with contextlib.suppress(Exception):
                await agent.refresh()

    task = asyncio.create_task(timer())

    async def close() -> None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        with contextlib.suppress(Exception):
            await agent.refresh()

    return [close]
