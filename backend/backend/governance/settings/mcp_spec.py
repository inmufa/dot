"""One `mcpServers` entry of settings.json (Claude Code compatible shapes)."""

import hashlib
import json
import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

NAME = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
Transport = Literal["stdio", "http", "sse"]
Scope = Literal["user", "project"]


class McpServerSpec(BaseModel):
    """stdio: command/args/env/cwd. remote: type http|sse, url, headers."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    type: Transport | None = None
    command: str | None = Field(default=None, max_length=1024)
    args: list[str] = Field(default_factory=list, max_length=64)
    env: dict[str, str] = Field(default_factory=dict, max_length=64)
    cwd: str | None = None
    url: str | None = Field(default=None, max_length=4096)
    headers: dict[str, str] = Field(default_factory=dict, max_length=32)
    # Hosts that skip the SSRF guard (a local MCP server on purpose).
    allow_hosts: list[str] = Field(default_factory=list, alias="allowHosts")
    disabled: bool = False

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if bool(self.command) == bool(self.url):
            msg = "an MCP server needs exactly one of command or url"
            raise ValueError(msg)
        if self.command and self.type not in (None, "stdio"):
            msg = "command servers are stdio"
            raise ValueError(msg)
        if self.url and self.type not in (None, "http", "sse"):
            msg = "url servers are http or sse"
            raise ValueError(msg)
        return self

    @property
    def transport(self) -> Transport:
        return "stdio" if self.command else (self.type or "http")  # type: ignore[return-value]

    def fingerprint(self) -> str:
        """Stable hash of everything that decides what runs or where it connects."""
        blob = json.dumps(self.model_dump(by_alias=True), sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()


def valid_server_name(name: str) -> str:
    if not NAME.match(name):
        msg = f"invalid MCP server name: {name[:40]!r}"
        raise ValueError(msg)
    return name
