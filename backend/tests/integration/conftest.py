from collections.abc import Iterator
from pathlib import Path

import pytest
from backend.main import create_app
from backend.settings import Settings
from fake_llama import FakeLlama
from servers import sandbox_process, serve_thread

TOKEN = "i" * 32
SANDBOX_TOKEN = "s" * 32


@pytest.fixture(scope="session")
def stack_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("integration").resolve()


@pytest.fixture(scope="session")
def workspace(stack_dir: Path) -> Path:
    root = stack_dir / "ws"
    root.mkdir()
    return root


@pytest.fixture(scope="session")
def fake_llama_server() -> Iterator[tuple[FakeLlama, str]]:
    fake = FakeLlama()
    with serve_thread(fake.app()) as base:
        yield fake, base


@pytest.fixture
def fake(fake_llama_server: tuple[FakeLlama, str]) -> FakeLlama:
    fake_llama_server[0].reset([])
    return fake_llama_server[0]


@pytest.fixture(scope="session")
def sandbox_url(workspace: Path) -> Iterator[str]:
    with sandbox_process(workspace, SANDBOX_TOKEN) as base:
        yield base


@pytest.fixture(scope="session")
def backend_url(
    stack_dir: Path,
    workspace: Path,
    fake_llama_server: tuple[FakeLlama, str],
    sandbox_url: str,
) -> Iterator[str]:
    """The real backend app over real HTTP: real LlamaClient, SandboxClient, SQLite."""
    home = stack_dir / "home"
    settings = Settings(
        api_token=TOKEN,
        db_path=stack_dir / "dot.db",
        workspace=workspace,
        llm_base_url=fake_llama_server[1] + "/v1",
        sandbox_url=sandbox_url,
        sandbox_token=SANDBOX_TOKEN,
        env="test",
        log_json=False,
        approval_timeout_s=20.0,
        user_settings_path=home / "settings.json",
        user_skills_dir=home / "skills",
        user_rules_path=home / "USER_RULES.md",
        memory_dir=home / "memory",
        scheduler_enabled=False,
        chat_rate_burst=10000,
        auto_title=False,
        chat_rate_per_min=100000,
        mcp_enabled=False,
    )
    with serve_thread(create_app(settings)) as base:
        yield base
