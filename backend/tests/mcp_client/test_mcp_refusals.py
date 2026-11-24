"""A server's own requests (sampling, roots, elicitation) are always refused."""

import contextlib

import anyio
from backend.mcp.services.connection import McpConnection
from mcp import types
from mcp.server.fastmcp import Context, FastMCP
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_client_server_memory_streams


async def test_server_initiated_requests_are_refused():
    mcp = FastMCP("evil")
    seen: dict[str, str] = {}

    @mcp.tool()
    async def probe(ctx: Context) -> str:
        """Try every server-to-client request."""
        sess = ctx.session
        msgs = [
            types.SamplingMessage(
                role="user", content=types.TextContent(type="text", text="hi")
            )
        ]
        for key, coro in (
            ("sampling", lambda: sess.create_message(messages=msgs, max_tokens=5)),
            ("roots", sess.list_roots),
        ):
            try:
                await coro()
                seen[key] = "ANSWERED"
            except McpError as exc:
                seen[key] = exc.error.message
        return "done"

    @contextlib.asynccontextmanager
    async def opener():
        async with (
            create_client_server_memory_streams() as (client, server),
            anyio.create_task_group() as tg,
        ):
            tg.start_soon(
                lambda: mcp._mcp_server.run(
                    server[0],
                    server[1],
                    mcp._mcp_server.create_initialization_options(),
                )
            )
            yield client
            tg.cancel_scope.cancel()

    conn = McpConnection("evil", opener, lambda *_: None, ping_s=60)
    conn.start()
    try:
        with anyio.fail_after(10):
            while conn.status != "connected":  # noqa: ASYNC110
                await anyio.sleep(0.02)
        await conn.call("probe", {})
    finally:
        await conn.stop()
    assert seen["sampling"] == "Sampling not supported"
    assert seen["roots"] == "List roots not supported"
