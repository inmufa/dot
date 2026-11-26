"""Routers for the UI-features batch (docs/api-contract.md "UI features v2")."""

from fastapi import FastAPI

from backend.preferences.api import router as preferences_router
from backend.routing.api.router import router as telemetry_router
from backend.sessions.api.browser import router as browser_router
from backend.sessions.api.files import router as files_router
from backend.sessions.api.manage import router as session_ops_router
from backend.sessions.api.media import router as media_router
from backend.sessions.api.uploads import router as uploads_router
from backend.sessions.services.projects.router import router as projects_router
from backend.vault.api import router as vault_router
from backend.voice.api import router as voice_router


def include_feature_routers(app: FastAPI) -> None:
    """Add one import and one include_router line per feature router."""
    app.include_router(session_ops_router)
    app.include_router(projects_router)
    app.include_router(telemetry_router)
    app.include_router(uploads_router)
    app.include_router(files_router)
    app.include_router(media_router)
    app.include_router(browser_router)
    app.include_router(vault_router)
    app.include_router(voice_router)
    app.include_router(preferences_router)
