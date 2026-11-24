"""Shared dependencies: settings, session, auth, trackers."""

import hmac
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, Request

from dot_sandbox.errors import SandboxError
from dot_sandbox.jail import resolve
from dot_sandbox.runtime.state import ReadTracker
from dot_sandbox.settings import Settings
from dot_sandbox.shell import ShellManager


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_token(
    settings: SettingsDep,
    x_sandbox_token: Annotated[str | None, Header()] = None,
) -> None:
    if settings.token and not hmac.compare_digest(
        x_sandbox_token or "", settings.token
    ):
        raise SandboxError(401, "unauthorized", "bad or missing X-Sandbox-Token")


def get_session(x_session_id: Annotated[str | None, Header()] = None) -> str:
    return x_session_id or "default"


def get_tracker(request: Request) -> ReadTracker:
    return request.app.state.tracker


def get_shells(request: Request) -> ShellManager:
    return request.app.state.shells


SessionDep = Annotated[str, Depends(get_session)]
TrackerDep = Annotated[ReadTracker, Depends(get_tracker)]
ShellsDep = Annotated[ShellManager, Depends(get_shells)]


def jail(settings: Settings, raw: str | None) -> Path:
    return resolve(settings.workspace, raw)
