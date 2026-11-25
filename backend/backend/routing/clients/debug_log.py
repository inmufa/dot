"""Opt-in LLM request capture (DOT_LLM_DEBUG_FILE): private, scrubbed and size-capped."""

import json
import os
from pathlib import Path
from typing import Any

from backend.core.logging import scrub

MAX_BYTES = 5_000_000


def append_payload(
    path: Path, payload: dict[str, Any], max_bytes: int = MAX_BYTES
) -> None:
    """One JSON line per request; the previous file is rotated once at the cap."""
    line = scrub(json.dumps(payload)) + "\n"
    if path.exists() and path.stat().st_size + len(line) > max_bytes:
        path.replace(path.with_name(path.name + ".1"))
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as fh:
        fh.write(line)
