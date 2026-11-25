"""Slash-command registry served by GET /v1/commands (F14)."""

from typing import Literal

from pydantic import BaseModel, Field


class CommandArg(BaseModel):
    name: str
    required: bool = False
    hint: str = ""
    choices: list[str] = Field(default_factory=list)


class CommandEndpoint(BaseModel):
    """How a client runs the command; `{id}` is the session id."""

    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str
    stream: bool = False  # response is an SSE chat stream
    body_arg: str | None = None  # command argument that goes into the JSON body


class CommandInfo(BaseModel):
    name: str  # without the leading slash
    description: str
    group: Literal["session", "context", "model", "tools", "skills", "ui"]
    args: list[CommandArg] = Field(default_factory=list)
    kind: Literal["server", "client", "skill"]
    available: bool = True
    reason: str | None = None  # why unavailable
    endpoint: CommandEndpoint | None = None  # server commands only
