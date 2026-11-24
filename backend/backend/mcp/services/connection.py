"""One MCP server connection: connect, ping, list_changed, reconnect with backoff.

A single task owns the transport and the SDK session (anyio scopes must be exited
by the task that entered them); callers use `call` from any other task.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
from typing import Any

import anyio
import httpx
from mcp import ClientSession, types
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)
Opener = Callable[[], AbstractAsyncContextManager[tuple[Any, Any]]]
OnTools = Callable[[str, list[types.Tool]], None]
BACKOFF_S = (1.0, 2.0, 5.0, 10.0, 30.0)
MAX_PAGES = 5
_DEAD = (anyio.ClosedResourceError, anyio.BrokenResourceError, ConnectionError)


class McpUnavailableError(Exception):
    """The server is not connected right now."""


class McpTimeoutError(Exception):
    """A call exceeded its time limit."""


class McpConnection:
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        opener: Opener,
        on_tools: OnTools,
        *,
        call_timeout_s: float = 60.0,
        connect_timeout_s: float = 20.0,
        ping_s: float = 30.0,
        backoff: tuple[float, ...] = BACKOFF_S,
    ) -> None:
        self.name = name
        self.status = "connecting"
        self.error: str | None = None
        self.tools: list[types.Tool] = []
        self._opener = opener
        self._on_tools = on_tools
        self._call_s = call_timeout_s
        self._connect_s = connect_timeout_s
        self._ping_s = ping_s
        self._backoff = backoff
        self._session: ClientSession | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()  # manual reconnect
        self._refresh = asyncio.Event()  # tools/list_changed
        self.connects = 0
        self._reconnect_now = False

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"mcp-{self.name}")

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, 3)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
                with contextlib.suppress(BaseException):
                    await self._task
        self.status = "stopped"
        self._drop_tools()

    def reconnect(self) -> None:
        """Drop the current session (if any) and retry immediately."""
        self._reconnect_now = True
        self._wake.set()

    def _drop_tools(self) -> None:
        self.tools = []
        self._on_tools(self.name, [])

    async def _on_message(self, message: Any) -> None:
        if isinstance(message, types.ServerNotification) and isinstance(
            message.root, types.ToolListChangedNotification
        ):
            self._refresh.set()

    @asynccontextmanager
    async def _session_cm(self) -> AsyncIterator[ClientSession]:
        async with (
            self._opener() as (read, write),
            ClientSession(
                read,
                write,
                read_timeout_seconds=timedelta(seconds=self._call_s),
                message_handler=self._on_message,
            ) as session,
        ):
            async with asyncio.timeout(self._connect_s):
                await session.initialize()
            yield session

    async def _run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            self.status = "connecting"
            self._wake.clear()
            self._reconnect_now = False
            try:
                async with self._session_cm() as session:
                    failures = 0
                    self.error = None
                    self._session = session
                    await self._refresh_tools(session)
                    self.connects += 1
                    self.status = "connected"
                    await self._serve(session)
            except Exception as exc:  # noqa: BLE001
                self.error = type(exc).__name__
                logger.warning("mcp %s: %s", self.name, self.error)
            self._session = None
            if self._stop.is_set():
                break
            self.status = "failed"
            self._drop_tools()
            if self._reconnect_now:
                continue
            failures += 1
            await self._pause(failures)

    async def _pause(self, failures: int) -> None:
        """Back off before retrying; after many failures wait for a manual reconnect."""
        limit = len(self._backoff)
        delay = None if failures > limit else self._backoff[failures - 1]
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._wake.wait(), delay)

    async def _serve(self, session: ClientSession) -> None:
        """Return when the session should end: stop, reconnect, or a failed ping."""
        while not self._stop.is_set() and not self._reconnect_now:
            waits = [
                asyncio.ensure_future(e.wait()) for e in (self._wake, self._refresh)
            ]
            done, pending = await asyncio.wait(
                waits, timeout=self._ping_s, return_when=asyncio.FIRST_COMPLETED
            )
            for p in pending:
                p.cancel()
            if self._stop.is_set() or self._reconnect_now:
                return
            if self._refresh.is_set():
                self._refresh.clear()
                await self._refresh_tools(session)
            elif not done and not await self._alive(session):
                self.error = "ping failed"
                return

    async def _alive(self, session: ClientSession) -> bool:
        try:
            await asyncio.wait_for(session.send_ping(), self._connect_s)
        except Exception:  # noqa: BLE001
            return False
        return True

    async def _refresh_tools(self, session: ClientSession) -> None:
        tools: list[types.Tool] = []
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            page = await session.list_tools(cursor)
            tools += page.tools
            cursor = page.nextCursor
            if not cursor:
                break
        self.tools = tools
        self._on_tools(self.name, tools)

    async def call(self, tool: str, args: dict[str, Any]) -> types.CallToolResult:
        session = self._session
        if session is None or self.status != "connected":
            raise McpUnavailableError
        try:
            async with asyncio.timeout(self._call_s + 5):
                return await session.call_tool(
                    tool, args, read_timeout_seconds=timedelta(seconds=self._call_s)
                )
        except TimeoutError as exc:
            raise McpTimeoutError from exc
        except McpError as exc:
            if exc.error.code == httpx.codes.REQUEST_TIMEOUT:
                raise McpTimeoutError from exc
            if exc.error.code == types.CONNECTION_CLOSED:
                self.reconnect()
                raise McpUnavailableError from exc
            raise
        except _DEAD as exc:
            self.reconnect()
            raise McpUnavailableError from exc
