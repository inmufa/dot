from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from backend.main import create_app
from backend.routing.clients.sandbox_client import SandboxClient
from backend.routing.clients.scripted import ScriptedLLM
from backend.settings import Settings
from dot_sandbox.main import create_app as create_sandbox_app
from dot_sandbox.settings import Settings as SandboxSettings
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

AUTH = {"Authorization": "Bearer " + "t" * 32}


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    root.mkdir()
    return root.resolve()


@pytest.fixture
def settings(tmp_path: Path, ws: Path) -> Settings:
    return Settings(
        api_token="t" * 32,
        db_path=tmp_path / "t.db",
        workspace=ws,
        log_json=False,
        env="test",
        approval_timeout_s=0.3,
        user_settings_path=tmp_path / "home" / "settings.json",
        default_permissions_path=None,
        user_skills_dir=tmp_path / "home-skills",
        user_rules_path=tmp_path / "home" / "USER_RULES.md",
        memory_dir=tmp_path / "home" / "memory",
    )


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM([])


@pytest.fixture
async def sandbox(ws: Path) -> AsyncIterator[SandboxClient]:
    app = create_sandbox_app(SandboxSettings(workspace=ws))
    http = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://sb")
    yield SandboxClient("http://sb", client=http)
    await http.aclose()
    await app.state.shells.shutdown()


@pytest.fixture
async def app(
    settings: Settings, llm: ScriptedLLM, sandbox: SandboxClient
) -> AsyncIterator[FastAPI]:
    application = create_app(settings, llm=llm, sandbox=sandbox)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def authed(client: AsyncClient) -> AsyncClient:
    client.headers.update(AUTH)
    return client
