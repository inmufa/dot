"""Context budget from llama-server /props: n_ctx per slot and slot count.

The compose/profile values only seed the settings; once the server answers, its
numbers win, so a bigger -c or more --parallel needs no backend change.
"""

import asyncio
import contextlib
import logging
from typing import Any

import httpx

from backend.settings import Settings

logger = logging.getLogger(__name__)
MIN_CTX = 512


def parse_props(data: Any) -> tuple[int | None, int | None]:
    """(n_ctx per slot, slot count) from a /props body; None where absent or bad."""
    if not isinstance(data, dict):
        return None, None
    gen = data.get("default_generation_settings")
    n_ctx = gen.get("n_ctx") if isinstance(gen, dict) else None
    slots = data.get("total_slots")
    ok = lambda v, lo: isinstance(v, int) and not isinstance(v, bool) and v >= lo  # noqa: E731
    return (n_ctx if ok(n_ctx, MIN_CTX) else None, slots if ok(slots, 1) else None)


class LimitWatcher:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        interval_s: float = 30.0,
    ) -> None:
        self._s = settings
        root = settings.llm_base_url.rstrip("/").removesuffix("/v1")
        self._url = f"{root}/props"
        self._http = client or httpx.AsyncClient(
            timeout=httpx.Timeout(3.0), trust_env=False
        )
        self._interval = interval_s
        self._task: asyncio.Task[None] | None = None

    async def refresh(self) -> bool:
        """Apply the server's numbers to the settings. False when unreachable."""
        try:
            r = await self._http.get(self._url)
            data = r.json() if r.status_code == httpx.codes.OK else None
        except (httpx.HTTPError, ValueError):
            return False
        n_ctx, slots = parse_props(data)
        if n_ctx is not None:
            cap = self._s.llm_context_cap
            limit = min(n_ctx, cap) if cap else n_ctx
            if limit != self._s.llm_context_limit:
                logger.info("context limit per slot: %s", limit)
            self._s.llm_context_limit = limit
        if slots is not None:
            self._s.llm_parallel_slots = slots
        return n_ctx is not None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self.refresh()

    async def aclose(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._http.aclose()
