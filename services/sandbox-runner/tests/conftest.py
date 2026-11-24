import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from dot_sandbox.main import create_app
from dot_sandbox.settings import Settings


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    root.mkdir()
    return root.resolve()


@pytest.fixture
async def client(ws: Path) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Settings(workspace=ws))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://t", headers={"X-Session-Id": "s1"}
    ) as c:
        yield c
    await app.state.shells.shutdown()


@pytest.fixture
def secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOT_SANDBOX_TOKEN", "hunter2")
    monkeypatch.setenv("FOO_TOKEN", "abc")
    monkeypatch.setenv("DOT_SECRET", "xyz")
    assert os.environ["FOO_TOKEN"]
