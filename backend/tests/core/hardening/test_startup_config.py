import subprocess
import sys
from pathlib import Path

import pytest
from backend.core.api.startup import StartupError, check_settings, load_settings
from backend.settings import Settings, get_settings

ENV_KEYS = ("DOT_API_TOKEN", "DOT_DB_PATH", "DOT_WORKSPACE", "DOT_TIMEZONE")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.chdir(tmp_path)  # no stray .env
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_missing_token_is_one_clear_problem(clean_env: Path):
    with pytest.raises(StartupError) as err:
        load_settings()
    assert err.value.problems == ["DOT_API_TOKEN is required (set it in .env)"]


def test_placeholder_token_rejected_without_echoing_it(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DOT_API_TOKEN", "change-me-to-a-long-random-string")
    with pytest.raises(StartupError) as err:
        load_settings()
    text = " ".join(err.value.problems)
    assert "placeholder" in text
    assert "change-me-to" not in text


def test_bad_paths_and_zone_are_all_listed(settings: Settings, tmp_path: Path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    bad = settings.model_copy(
        update={
            "workspace": tmp_path / "missing",
            "db_path": blocker / "dot.db",
            "default_permissions_path": tmp_path / "nope.json",
            "timezone": "Mars/Base",
            "llm_base_url": "ftp://x",
        }
    )
    problems = "\n".join(check_settings(bad))
    for name in (
        "DOT_WORKSPACE",
        "DOT_DB_PATH",
        "DOT_DEFAULT_PERMISSIONS_PATH",
        "DOT_TIMEZONE",
        "DOT_LLM_BASE_URL",
    ):
        assert name in problems


def test_good_settings_have_no_problems(settings: Settings):
    assert check_settings(settings) == []


def test_bad_numeric_env_names_the_variable(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("DOT_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DOT_MAX_BODY_BYTES", "abc")
    with pytest.raises(StartupError) as err:
        load_settings()
    assert err.value.problems[0].startswith("DOT_MAX_BODY_BYTES")


def test_uvicorn_factory_exits_2_without_traceback(tmp_path: Path):
    env = {"PATH": "/usr/bin:/bin"}
    proc = subprocess.run(
        [sys.executable, "-m", "uvicorn", "backend.main:create_app", "--factory"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 2
    assert "DOT_API_TOKEN is required" in proc.stderr
    assert "Traceback" not in proc.stderr
