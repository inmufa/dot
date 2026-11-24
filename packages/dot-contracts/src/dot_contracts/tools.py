from typing import Any

from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    deferred: bool = False
    # Fail closed: a tool is mutating unless it explicitly declares read-only.
    mutating: bool = True
    # Read-only tools that still prompt in every mode but bypass (e.g. open-world MCP tools).
    needs_approval: bool = False


class ToolInvocation(BaseModel):
    call_id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    call_id: str
    output: str
    is_error: bool = False
    # Untrusted content (web, MCP, files outside the workspace); feeds the classifier.
    tainted: bool = False
    spill_path: str | None = None


class ToolInfo(BaseModel):
    """One registry tool as listed by GET /v1/tools."""

    name: str
    description: str
    deferred: bool
    mutating: bool
    source: str  # builtin | mcp
    input_schema: dict[str, Any]
