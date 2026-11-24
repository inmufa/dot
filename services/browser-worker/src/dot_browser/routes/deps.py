"""Shared dependencies: settings, auth, session, manager."""

import hmac
from typing import Annotated

from fastapi import Depends, Header, Request

from dot_browser.browser import BrowserManager
from dot_browser.errors import BrowserError
from dot_browser.guard import UrlGuard
from dot_browser.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_token(
    settings: SettingsDep,
    x_browser_token: Annotated[str | None, Header()] = None,
) -> None:
    if settings.token and not hmac.compare_digest(
        (x_browser_token or "").encode(), settings.token.encode()
    ):
        raise BrowserError(401, "unauthorized", "bad or missing X-Browser-Token")


def get_session(x_session_id: Annotated[str | None, Header()] = None) -> str:
    return x_session_id or "default"


def get_manager(request: Request) -> BrowserManager:
    return request.app.state.manager


def get_guard(request: Request) -> UrlGuard:
    return request.app.state.guard


SessionDep = Annotated[str, Depends(get_session)]
ManagerDep = Annotated[BrowserManager, Depends(get_manager)]
GuardDep = Annotated[UrlGuard, Depends(get_guard)]
