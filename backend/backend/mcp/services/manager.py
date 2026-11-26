"""Owns every MCP server: config -> trust -> connection -> registered deferred tools."""

import asyncio
import contextlib
import logging
import os
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from dot_contracts.mcp import McpServerInfo
from mcp import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.cognition.services.tools.registry import ToolRegistry
from backend.core.exceptions import DomainException
from backend.governance.services.audit import AuditService
from backend.governance.settings.loader import SettingsProvider
from backend.governance.settings.mcp_spec import McpServerSpec, Scope
from backend.mcp.models import McpTrust
from backend.mcp.services import config, normalize, transports
from backend.mcp.services.connection import McpConnection, Opener
from backend.mcp.services.tools import make_mcp_tool
from backend.routing.clients.sandbox_client import SandboxClient
from backend.settings import Settings

if TYPE_CHECKING:
    from backend.cognition.services.skill_loader import SkillRegistry

logger = logging.getLogger(__name__)
NOT_FOUND = 4030
INVALID = 4039
_FAILED_CONFIG = "config"


class _Entry:
    """Config + state of one server name."""

    def __init__(self, spec: McpServerSpec, scope: Scope, fingerprint: str) -> None:
        self.spec = spec
        self.scope = scope
        self.fingerprint = fingerprint
        self.trusted = scope == "user"
        self.conn: McpConnection | None = None
        self.error: str | None = None
        self.tool_names: list[str] = []


class McpManager:
    def __init__(  # noqa: PLR0913
        self,
        *,
        settings: Settings,
        provider: SettingsProvider,
        registry: ToolRegistry,
        sandbox: SandboxClient,
        maker: async_sessionmaker,
        audit: AuditService,
        skills: "SkillRegistry | None" = None,
        environ: Mapping[str, str] | None = None,
        opener_for: Callable[[str, McpServerSpec], Opener] | None = None,
    ) -> None:
        self._s = settings
        self._provider = provider
        self._registry = registry
        self._sandbox = sandbox
        self._maker = maker
        self._audit = audit
        self._skills = skills
        self._environ = environ
        self._opener_for = opener_for
        self._allowed = config.allowlist(settings.mcp_env_allowlist)
        self._entries: dict[str, _Entry] = {}
        self._slugs: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._watch: asyncio.Task[None] | None = None

    # ---- lifecycle ----
    async def start(self) -> None:
        await self.reconcile()
        self._watch = asyncio.create_task(self._watcher(), name="mcp-watch")

    async def stop(self) -> None:
        if self._watch is not None:
            self._watch.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watch
        async with self._lock:
            for name in list(self._entries):
                await self._drop(name)

    async def _watcher(self) -> None:
        while True:
            await asyncio.sleep(self._s.mcp_reconcile_interval_s)
            try:
                await self.reconcile()
            except Exception:
                logger.exception("mcp reconcile failed")

    # ---- reconcile ----
    async def reconcile(self) -> None:
        try:
            wanted = self._provider.mcp_servers() if self._s.mcp_enabled else {}
        except DomainException:
            logger.warning("mcp: settings invalid, keeping current servers")
            return
        async with self._lock:
            for name in list(self._entries):
                entry = self._entries[name]
                new = wanted.get(name)
                if new is None or new[0].fingerprint() != entry.fingerprint:
                    await self._drop(name)
            self._slugs = normalize.server_slugs(sorted(wanted))
            for name, (spec, scope) in wanted.items():
                if name not in self._entries:
                    await self._add(name, spec, scope)
            self._publish()

    async def _add(self, name: str, spec: McpServerSpec, scope: Scope) -> None:
        entry = _Entry(spec, scope, spec.fingerprint())
        self._entries[name] = entry
        if scope == "project":
            entry.trusted = await self._is_trusted(name, entry.fingerprint)
        if spec.disabled or not entry.trusted:
            return
        opener = self._opener(name, spec)
        if opener is None:
            entry.error = _FAILED_CONFIG
            return
        entry.conn = McpConnection(
            name,
            opener,
            self._on_tools,
            call_timeout_s=self._s.mcp_call_timeout_s,
            connect_timeout_s=self._s.mcp_connect_timeout_s,
            ping_s=self._s.mcp_ping_interval_s,
        )
        entry.conn.start()

    def _opener(self, name: str, spec: McpServerSpec) -> Opener | None:
        if self._opener_for is not None:
            return self._opener_for(name, spec)
        try:
            env, headers = config.resolve_maps(
                spec, self._allowed, self._environ or os.environ
            )
        except config.McpConfigError as exc:
            logger.warning("mcp %s: bad config: %s", name, exc)
            return None
        if spec.transport == "stdio":
            return lambda: transports.sandbox_stdio(self._sandbox, name, spec, env)
        return lambda: transports.remote_streams(spec, headers)

    async def _drop(self, name: str) -> None:
        entry = self._entries.pop(name, None)
        if entry is None:
            return
        self._unregister(entry)
        if entry.conn is not None:
            await entry.conn.stop()
        self._publish()

    # ---- trust ----
    async def _is_trusted(self, name: str, fingerprint: str) -> bool:
        async with self._maker() as db:
            row = await db.scalar(
                select(McpTrust.id).where(
                    McpTrust.name == name, McpTrust.fingerprint == fingerprint
                )
            )
        return row is not None

    async def trust(self, name: str) -> McpServerInfo:
        entry = self._entries.get(name)
        if entry is None:
            await self.reconcile()
            entry = self._entries.get(name)
        if entry is None:
            raise DomainException(NOT_FOUND)
        if entry.scope == "project" and not entry.trusted:
            async with self._maker() as db:
                db.add(McpTrust(name=name, fingerprint=entry.fingerprint))
                await db.commit()
            await self._audit.append(
                session="mcp",
                mode="n/a",
                tool="mcp_trust",
                args={"server": name, "fingerprint": entry.fingerprint[:12]},
                decision="allow",
                source="user",
                reason="project MCP server approved by the user",
            )
            async with self._lock:
                await self._drop(name)
                await self._add(name, entry.spec, entry.scope)
                self._publish()
        return self.info(name)

    async def reconnect(self, name: str) -> McpServerInfo:
        await self.reconcile()
        entry = self._entries.get(name)
        if entry is None:
            raise DomainException(NOT_FOUND)
        if entry.conn is not None:
            entry.conn.reconnect()
        return self.info(name)

    # ---- tools ----
    def _on_tools(self, name: str, tools: list[types.Tool]) -> None:
        entry = self._entries.get(name)
        if entry is None or entry.conn is None:
            return
        self._unregister(entry)
        taken = {d.name for d in self._registry.definitions()}
        slug = self._slugs.get(name, normalize.slug(name))
        for tool in tools[: self._s.mcp_max_tools_per_server]:
            full = normalize.tool_name(slug, tool.name, taken)
            self._registry.add(make_mcp_tool(full, name, tool, entry.conn))
            entry.tool_names.append(full)
        self._publish()

    def _unregister(self, entry: _Entry) -> None:
        for full in entry.tool_names:
            self._registry.remove(full)
        entry.tool_names = []

    def _publish(self) -> None:
        """Tell the skill loader which tools and MCP servers exist right now."""
        if self._skills is None:
            return
        connected = {
            n
            for n, e in self._entries.items()
            if e.conn and e.conn.status == "connected"
        }
        self._skills.set_environment(
            {d.name for d in self._registry.definitions()}, connected
        )

    # ---- status ----
    def info(self, name: str) -> McpServerInfo:
        entry = self._entries[name]
        conn = entry.conn
        if conn is not None:
            status, error = conn.status, conn.error
        elif entry.spec.disabled:
            status, error = "stopped", None
        elif not entry.trusted:
            status, error = "needs_trust", None
        else:
            status, error = "failed", entry.error
        return McpServerInfo(
            name=name,
            transport=entry.spec.transport,
            scope=entry.scope,
            status=status,  # type: ignore[arg-type]
            tool_count=len(entry.tool_names),
            trusted=entry.trusted,
            error=error,
        )

    def infos(self) -> list[McpServerInfo]:
        return [self.info(n) for n in sorted(self._entries)]
