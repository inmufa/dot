"""Scrubbed environment for every subprocess (allowlist, no inherited secrets)."""

import os

ALLOWED = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TERM",
)


def scrubbed_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in ALLOWED if k in os.environ}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    env.setdefault("TERM", "dumb")
    return env
