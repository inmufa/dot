"""Browser lifecycle: lazy Chromium, per-session contexts, idle reaping."""

import asyncio
import contextlib
import hashlib
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from dot_browser.errors import BrowserError
from dot_browser.guard import UrlGuard
from dot_browser.proxy import EgressProxy
from dot_browser.session import ClockFn, SessionContext
from dot_browser.settings import Settings

MAX_VIEWPORTS = 256
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
HARDENING_ARGS = [
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--no-first-run",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
]


def profile_name(session: str) -> str:
    if SAFE_NAME.match(session):
        return session
    return "s-" + hashlib.sha256(session.encode()).hexdigest()[:24]


class BrowserManager:
    def __init__(
        self, cfg: Settings, guard: UrlGuard, clock: ClockFn = time.monotonic
    ) -> None:
        self.cfg = cfg
        self.guard = guard
        self.clock = clock
        self.sessions: dict[str, SessionContext] = {}
        # Owner view size per session; outlives a reaped context so the next one starts at it.
        self.viewports: dict[str, dict[str, int]] = {}
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._create_lock = asyncio.Lock()
        self.proxy = EgressProxy(guard, cfg)

    def _args(self) -> list[str]:
        args = [
            *HARDENING_ARGS,
            f"--proxy-server=http://127.0.0.1:{self.proxy.port}",
            "--proxy-bypass-list=<-loopback>",
            *self.cfg.extra_chromium_args,
        ]
        if self.cfg.no_sandbox:
            args.append("--no-sandbox")
        return args

    async def _ensure_browser(self) -> None:
        if self._pw is None:
            await self.proxy.start()
            self._pw = await async_playwright().start()
        if self._browser is None and self.cfg.profiles_dir is None:
            self._browser = await self._pw.chromium.launch(
                headless=self.cfg.headless, args=self._args()
            )

    def _context_options(self, session: str) -> dict:
        size = self.viewports.get(session) or {
            "width": self.cfg.viewport_width,
            "height": self.cfg.viewport_height,
        }
        return {
            "viewport": dict(size),
            "accept_downloads": False,
            "service_workers": "block",
            "ignore_https_errors": False,
            "locale": "en-US",
        }

    async def _new_context(self, session: str) -> BrowserContext:
        opts = self._context_options(session)
        if self.cfg.profiles_dir is not None:
            path = self.cfg.profiles_dir / profile_name(session)
            await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
            assert self._pw is not None  # noqa: S101
            return await self._pw.chromium.launch_persistent_context(
                str(path), headless=self.cfg.headless, args=self._args(), **opts
            )
        assert self._browser is not None  # noqa: S101
        return await self._browser.new_context(**opts)

    async def acquire(self, session: str) -> SessionContext:
        entry = self.sessions.get(session)
        if entry:
            return entry
        async with self._create_lock:
            if session in self.sessions:
                return self.sessions[session]
            if len(self.sessions) >= self.cfg.max_contexts:
                raise BrowserError(
                    429, "too_many_sessions", f"limit {self.cfg.max_contexts}"
                )
            try:
                await self._ensure_browser()
                ctx = await self._new_context(session)
            except (PlaywrightError, OSError) as exc:
                raise BrowserError(
                    503, "browser_unavailable", str(exc).splitlines()[0][:300]
                ) from exc
            entry = SessionContext(session, ctx, self.cfg, self.guard, self.clock())
            entry.viewport = self.viewports.get(session)
            await entry.wire()
            self.sessions[session] = entry
            return entry

    @asynccontextmanager
    async def use(self, session: str) -> AsyncIterator[SessionContext]:
        entry = await self.acquire(session)
        async with entry.lock:
            entry.last_used = self.clock()
            try:
                yield entry
            except PlaywrightTimeout as exc:
                raise BrowserError(504, "timeout", _short(exc)) from exc
            except PlaywrightError as exc:
                raise BrowserError(502, "action_failed", _short(exc)) from exc
            finally:
                entry.last_used = self.clock()

    def remember_viewport(self, session: str, size: dict[str, int]) -> None:
        self.viewports.pop(session, None)
        self.viewports[session] = size
        while len(self.viewports) > MAX_VIEWPORTS:
            self.viewports.pop(next(iter(self.viewports)))

    async def close_session(self, session: str) -> bool:
        entry = self.sessions.pop(session, None)
        if entry is None:
            return False
        await entry.close()
        return True

    async def reap(self) -> list[str]:
        limit = self.cfg.idle_minutes * 60
        now = self.clock()
        stale = [
            n
            for n, e in self.sessions.items()
            if not e.lock.locked() and now - e.last_used > limit
        ]
        for name in stale:
            await self.close_session(name)
        return stale

    async def reap_forever(self) -> None:
        while True:
            await asyncio.sleep(self.cfg.reap_interval_s)
            with contextlib.suppress(Exception):
                await self.reap()

    async def shutdown(self) -> None:
        for name in list(self.sessions):
            await self.close_session(name)
        with contextlib.suppress(PlaywrightError):
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        await self.proxy.stop()
        self._browser = self._pw = None


def _short(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0][:300] if str(exc).strip() else "failed"
