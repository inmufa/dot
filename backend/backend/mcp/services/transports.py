"""Transports for the MCP SDK: stdio inside the sandbox, guarded HTTP, guarded SSE."""

import contextlib
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import httpx
from mcp import types
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.message import SessionMessage
from pydantic import ValidationError

from backend.core.exceptions import DomainException
from backend.core.ssrf import Blocked, vet
from backend.governance.settings.mcp_spec import McpServerSpec
from backend.mcp.services.config import McpConfigError
from backend.routing.clients.sandbox_client import SandboxClient

logger = logging.getLogger(__name__)
RECV_WAIT_S = 20.0
_QUEUE = 64
_ID = re.compile(r"[^A-Za-z0-9_-]")


class McpTransportError(Exception):
    """The server could not be started or reached."""


async def _pump_in(
    sandbox: SandboxClient, sid: str, proc: str, tx: Any, *, wait_s: float
) -> None:
    """Sandbox stdout lines -> SDK read stream. Closing it ends the session."""
    try:
        async with tx:
            while True:
                try:
                    r = await sandbox.post(
                        sid,
                        f"/internal/mcp/{proc}/recv",
                        {"timeout_s": wait_s},
                        timeout_s=wait_s,
                    )
                except DomainException:
                    return
                if not r.ok:
                    return
                for line in r.data.get("lines", []):
                    try:
                        msg = types.JSONRPCMessage.model_validate_json(line)
                    except ValidationError as exc:
                        await tx.send(exc)
                        continue
                    await tx.send(SessionMessage(msg))
                if not r.data.get("alive", False) and not r.data.get("lines"):
                    return
    except (anyio.ClosedResourceError, anyio.BrokenResourceError):
        return


async def _pump_out(sandbox: SandboxClient, sid: str, proc: str, rx: Any) -> None:
    """SDK write stream -> sandbox stdin."""
    async with rx:
        async for item in rx:
            line = item.message.model_dump_json(by_alias=True, exclude_none=True)
            try:
                r = await sandbox.post(
                    sid, f"/internal/mcp/{proc}/send", {"line": line}
                )
            except DomainException:
                return
            if not r.ok:
                return


@asynccontextmanager
async def sandbox_stdio(
    sandbox: SandboxClient,
    name: str,
    spec: McpServerSpec,
    env: dict[str, str],
    *,
    wait_s: float = RECV_WAIT_S,
) -> AsyncIterator[tuple[Any, Any]]:
    """Spawn the server inside the sandbox and expose it as SDK message streams."""
    sid = "mcp-" + _ID.sub("_", name)[:50]
    try:
        r = await sandbox.post(
            sid,
            "/internal/mcp/spawn",
            {
                "command": spec.command,
                "args": spec.args,
                "env": env,
                "cwd": spec.cwd,
            },
        )
    except DomainException as exc:
        msg = "sandbox unavailable"
        raise McpTransportError(msg) from exc
    if not r.ok:
        raise McpTransportError(r.error_text())
    proc = r.data["proc_id"]
    in_tx, in_rx = anyio.create_memory_object_stream[Any](_QUEUE)
    out_tx, out_rx = anyio.create_memory_object_stream[Any](_QUEUE)
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(lambda: _pump_in(sandbox, sid, proc, in_tx, wait_s=wait_s))
            tg.start_soon(lambda: _pump_out(sandbox, sid, proc, out_rx))
            try:
                yield in_rx, out_tx
            finally:
                tg.cancel_scope.cancel()
    finally:
        with contextlib.suppress(DomainException), anyio.CancelScope(shield=True):
            await sandbox.post(sid, f"/internal/mcp/{proc}/close", {})


class GuardedTransport(httpx.AsyncBaseTransport):
    """Vets every request host (SSRF guard) unless the config allows it explicitly."""

    def __init__(self, allow_hosts: frozenset[str]) -> None:
        self._inner = httpx.AsyncHTTPTransport()
        self._allow = allow_hosts

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = (request.url.host or "").lower()
        if host not in self._allow:
            try:
                target = await vet(str(request.url))
            except Blocked as exc:
                msg = f"blocked: {exc}"
                raise httpx.ConnectError(msg, request=request) from exc
            # Connect to the vetted address: no second DNS lookup (rebinding).
            request = httpx.Request(
                request.method,
                request.url.copy_with(host=target.ip),
                headers=request.headers,  # Host stays the real name
                stream=request.stream,
                extensions={**request.extensions, "sni_hostname": target.host},
            )
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


async def check_url(spec: McpServerSpec) -> frozenset[str]:
    """Up-front URL vetting; returns the lower-cased allowed hosts."""
    allow = frozenset(h.lower() for h in spec.allow_hosts)
    url = spec.url or ""
    try:
        host = (httpx.URL(url).host or "").lower()
    except httpx.InvalidURL as exc:
        msg = "malformed URL"
        raise McpConfigError(msg) from exc
    if host not in allow:
        try:
            await vet(url)
        except Blocked as exc:
            msg = f"URL not allowed: {exc}"
            raise McpConfigError(msg) from exc
    return allow


def _client(headers: dict[str, str], allow: frozenset[str]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=headers,
        transport=GuardedTransport(allow),
        trust_env=False,
        timeout=httpx.Timeout(30.0, read=300.0),
    )


@asynccontextmanager
async def remote_streams(
    spec: McpServerSpec, headers: dict[str, str]
) -> AsyncIterator[tuple[Any, Any]]:
    allow = await check_url(spec)
    url = spec.url or ""
    if spec.transport == "sse":

        def factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None,
        ) -> httpx.AsyncClient:
            client = _client({**(headers or {})}, allow)
            client.auth = auth  # type: ignore[assignment]
            if timeout is not None:
                client.timeout = timeout
            return client

        async with sse_client(url, headers=headers, httpx_client_factory=factory) as s:
            yield s[0], s[1]
        return
    async with (
        _client(headers, allow) as http,
        streamable_http_client(url, http_client=http) as s,
    ):
        yield s[0], s[1]
