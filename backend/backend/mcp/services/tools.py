"""Discovered MCP tools -> deferred registry tools. Everything from a server is tainted."""

import json
import logging
from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult
from mcp import types
from mcp.shared.exceptions import McpError

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.core.exceptions import DomainException
from backend.mcp.services.connection import (
    McpConnection,
    McpTimeoutError,
    McpUnavailableError,
)
from backend.mcp.services.normalize import TOOL_DESC_CHARS, clean_text, normalize_schema

logger = logging.getLogger(__name__)
MAX_OUTPUT_CHARS = 12_000  # what the model sees (rest: head/tail + spill file)
RAW_CAP = 200_000
SPILL_CAP = 5_000_000
ERROR_CHARS = 400


def flags(ann: types.ToolAnnotations | None) -> tuple[bool, bool]:
    """(mutating, needs_approval) from the server's own hints.

    The hints are a claim by a third party and never auto-allow: every MCP tool
    needs the user's approval (or an explicit allow rule). readOnlyHint only lets
    the call be shown as non-mutating.
    """
    if ann is None:
        return True, True
    read_only = ann.readOnlyHint is True and ann.destructiveHint is not True
    return (not read_only), True


def render(result: types.CallToolResult) -> str:
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
        elif isinstance(block, types.ImageContent | types.AudioContent):
            parts.append(
                f"[{block.type} {block.mimeType}, {len(block.data)} bytes omitted]"
            )
        elif isinstance(block, types.ResourceLink):
            parts.append(f"[resource link: {clean_text(block.uri, 200)}]")
        elif isinstance(block, types.EmbeddedResource):
            res = block.resource
            text = getattr(res, "text", None)
            parts.append(text if text is not None else f"[binary resource {res.uri}]")
    if not parts and result.structuredContent is not None:
        parts.append(json.dumps(result.structuredContent, ensure_ascii=False))
    return "\n".join(parts) or "(empty result)"


async def _spill(ctx: ToolContext, text: str) -> str | None:
    try:
        r = await ctx.sandbox.post(
            ctx.session_id, "/internal/spill", {"content": text[:SPILL_CAP]}
        )
    except DomainException:
        return None
    return r.data.get("path") if r.ok else None


def _fail(text: str) -> ToolResult:
    return ToolResult(call_id="", output=text, is_error=True, tainted=True)


async def _call(
    conn: McpConnection, server: str, tool: str, ctx: ToolContext, args: dict[str, Any]
) -> ToolResult:
    try:
        result = await conn.call(tool, args)
    except McpUnavailableError:
        return _fail(f"MCP server '{server}' is not connected (reconnecting).")
    except McpTimeoutError:
        return _fail(f"MCP tool timed out on server '{server}'.")
    except McpError as exc:
        return _fail(f"MCP error: {clean_text(exc.error.message, ERROR_CHARS)}")
    text = render(result)
    spill = None
    if len(text) > RAW_CAP:
        spill = await _spill(ctx, text)
        text = text[:RAW_CAP]
    elif len(text) > MAX_OUTPUT_CHARS:
        spill = await _spill(ctx, text)
    return ToolResult(
        call_id="",
        output=text,
        is_error=bool(result.isError),
        tainted=True,  # a third party wrote this
        spill_path=spill,
    )


def make_mcp_tool(
    full_name: str, server: str, tool: types.Tool, conn: McpConnection
) -> Tool:
    mutating, ask = flags(tool.annotations)
    desc = clean_text(tool.description or tool.title or tool.name, TOOL_DESC_CHARS)

    async def run(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        return await _call(conn, server, tool.name, ctx, args)

    definition = ToolDefinition(
        name=full_name,
        description=f"[MCP server {clean_text(server, 40)}] {desc}",
        input_schema=normalize_schema(tool.inputSchema),
        deferred=True,
        mutating=mutating,
        needs_approval=ask,
    )
    return Tool(definition, run, max_chars=MAX_OUTPUT_CHARS)
