"""One browser context per session: tabs, violations, guard wiring."""

import asyncio
import contextlib
from collections.abc import Callable

from playwright.async_api import BrowserContext, Page, Route
from playwright.async_api import Error as PlaywrightError

from dot_browser.errors import BrowserError
from dot_browser.guard import Blocked, UrlGuard
from dot_browser.settings import Settings

SKIPPED_TYPES = {"image", "media", "font"}


class SessionContext:
    def __init__(
        self,
        name: str,
        context: BrowserContext,
        cfg: Settings,
        guard: UrlGuard,
        now: float,
    ) -> None:
        self.name = name
        self.context = context
        self.cfg = cfg
        self.guard = guard
        self.last_used = now
        self.lock = asyncio.Lock()
        self.tabs: dict[str, Page] = {}
        self.active: str | None = None
        self.mark = guard.block_count
        self._seq = 0

    async def wire(self) -> None:
        self.context.set_default_timeout(self.cfg.action_timeout_ms)
        self.context.set_default_navigation_timeout(self.cfg.nav_timeout_ms)
        await self.context.route("**/*", self._route)
        self.context.on("page", self.register)
        for page in self.context.pages:
            self.register(page)

    def register(self, page: Page) -> str:
        for tid, known in self.tabs.items():
            if known is page:
                return tid
        if len(self.tabs) >= self.cfg.max_tabs:
            asyncio.ensure_future(self._close_quietly(page))  # noqa: RUF006
            return ""
        self._seq += 1
        tid = f"t{self._seq}"
        self.tabs[tid] = page
        self.active = self.active or tid
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        page.on("download", lambda d: asyncio.ensure_future(d.cancel()))
        page.on("close", lambda _p, t=tid: self._forget(t))
        return tid

    def _forget(self, tid: str) -> None:
        self.tabs.pop(tid, None)
        if self.active == tid:
            self.active = next(reversed(self.tabs), None)

    @staticmethod
    async def _close_quietly(page: Page) -> None:
        with contextlib.suppress(PlaywrightError):
            await page.close()

    async def _route(self, route: Route) -> None:
        """Early, friendly check; the egress proxy is the enforcing layer."""
        request = route.request
        with contextlib.suppress(PlaywrightError):
            if self.cfg.block_resources and request.resource_type in SKIPPED_TYPES:
                await route.abort("blockedbyclient")
                return
            try:
                await self.guard.check(
                    request.url, navigation=request.is_navigation_request()
                )
            except Blocked as exc:
                self.guard.note(str(exc))
                await route.abort("blockedbyclient")
                return
            await route.continue_()

    def reset_marks(self) -> None:
        self.mark = self.guard.block_count

    def blocked(self) -> list[str]:
        return self.guard.since(self.mark)

    def reason(self) -> str | None:
        found = self.blocked()
        return found[0] if found else None

    async def page(self, tab: str | None) -> Page:
        if tab is None:
            if not self.active:
                return await self.new_tab()
            tab = self.active
        page = self.tabs.get(tab)
        if page is None:
            raise BrowserError(404, "no_such_tab", f"unknown tab {tab!r}")
        return page

    async def new_tab(self) -> Page:
        if len(self.tabs) >= self.cfg.max_tabs:
            raise BrowserError(429, "too_many_tabs", f"limit {self.cfg.max_tabs}")
        page = await self.context.new_page()
        self.active = self.register(page) or self.active
        return page

    def tab_of(self, page: Page) -> str:
        return next((t for t, p in self.tabs.items() if p is page), "")

    async def close(self) -> None:
        with contextlib.suppress(PlaywrightError):
            await self.context.close()


ClockFn = Callable[[], float]
