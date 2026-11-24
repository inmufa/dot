"""Startup validation: every misconfiguration as one clear line, never a traceback."""

import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from backend.settings import Settings, get_settings

EXIT_CONFIG = 2


class StartupError(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def _validation_problems(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors(include_input=False, include_url=False):
        name = "DOT_" + str(err["loc"][0]).upper() if err["loc"] else "settings"
        if err["type"] == "missing":
            out.append(f"{name} is required (set it in .env)")
        else:
            msg = str(err["msg"]).removeprefix("Value error, ")
            out.append(f"{name}: {msg}")
    return out


def _writable_dir(path: Path, name: str) -> str | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"{name}={path}: cannot create directory ({exc.strerror})"
    if not os.access(path, os.W_OK | os.X_OK):
        return f"{name}={path}: directory is not writable"
    return None


def _db_problem(db_path: Path) -> str | None:
    if db_path.is_dir():
        return f"DOT_DB_PATH={db_path}: is a directory, expected a file path"
    if db_path.exists() and not os.access(db_path, os.W_OK):
        return f"DOT_DB_PATH={db_path}: file is not writable"
    return _writable_dir(db_path.parent, "DOT_DB_PATH (parent)")


def _path_problems(s: Settings) -> list[str]:
    checks = [
        (s.workspace.is_dir(), f"DOT_WORKSPACE={s.workspace}: not a directory"),
        (s.skills_dir.is_dir(), f"DOT_SKILLS_DIR={s.skills_dir}: not a directory"),
        (
            s.default_permissions_path is None or s.default_permissions_path.is_file(),
            f"DOT_DEFAULT_PERMISSIONS_PATH={s.default_permissions_path}: file not found",
        ),
        (
            s.global_rules_path.is_file(),
            f"DOT_GLOBAL_RULES_PATH={s.global_rules_path}: file not found",
        ),
    ]
    problems = [msg for ok, msg in checks if not ok]
    problems += [
        p
        for p in (
            _db_problem(s.db_path),
            _writable_dir(s.memory_dir.expanduser(), "DOT_MEMORY_DIR"),
        )
        if p
    ]
    return problems


def _value_problems(s: Settings) -> list[str]:
    problems = []
    try:
        ZoneInfo(s.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        problems.append(f"DOT_TIMEZONE={s.timezone}: unknown IANA time zone")
    for name, url in (
        ("DOT_LLM_BASE_URL", s.llm_base_url),
        ("DOT_SANDBOX_URL", s.sandbox_url),
    ):
        if not url.startswith(("http://", "https://")):
            problems.append(f"{name}={url}: must start with http:// or https://")
    return problems


def check_settings(s: Settings) -> list[str]:
    return _path_problems(s) + _value_problems(s)


def load_settings() -> Settings:
    """Read the environment; raise StartupError listing every problem found."""
    try:
        settings = get_settings()
    except ValidationError as exc:
        raise StartupError(_validation_problems(exc)) from None
    problems = check_settings(settings)
    if problems:
        raise StartupError(problems)
    return settings


def exit_with(error: StartupError) -> None:
    """Print the problems to stderr (text plus one JSON line) and exit 2."""
    lines = "\n".join(f"  - {p}" for p in error.problems)
    sys.stderr.write(f"dot-backend: cannot start, fix the configuration:\n{lines}\n")
    sys.stderr.write(
        json.dumps(
            {"level": "CRITICAL", "event": "startup_failed", "problems": error.problems}
        )
        + "\n"
    )
    raise SystemExit(EXIT_CONFIG)
