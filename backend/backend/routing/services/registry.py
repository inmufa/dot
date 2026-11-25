"""Model registry (models/registry.toml): per-GGUF facts, tolerant of mistakes.

A missing or broken file, or a bad entry, never breaks the backend: unlisted models
get the safe defaults (no effort levels, no vision).
"""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelEntry:
    file: str
    name: str
    mmproj: str | None = None
    context_max: int | None = None
    thinking: bool = False
    effort_levels: tuple[str, ...] = ()
    recommended_profile: str | None = None

    @property
    def vision(self) -> bool:
        return self.mmproj is not None


def _str(v: Any) -> str | None:
    return v if isinstance(v, str) and v else None


def _entry(raw: Any) -> ModelEntry | None:
    if not isinstance(raw, dict) or not (file := _str(raw.get("file"))):
        return None
    ctx = raw.get("context_max")
    levels = raw.get("effort_levels")
    return ModelEntry(
        file=file,
        name=_str(raw.get("name")) or file,
        mmproj=_str(raw.get("mmproj")),
        context_max=ctx if isinstance(ctx, int) and not isinstance(ctx, bool) else None,
        thinking=raw.get("thinking") is True,
        effort_levels=tuple(str(x) for x in levels[:16])
        if isinstance(levels, list)
        else (),
        recommended_profile=_str(raw.get("recommended_profile")),
    )


def parse_registry(text: str) -> dict[str, ModelEntry]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        logger.warning("model registry is not valid TOML, ignored")
        return {}
    out: dict[str, ModelEntry] = {}
    for raw in data.get("model", []) if isinstance(data.get("model"), list) else []:
        entry = _entry(raw)
        if entry is None:
            logger.warning("model registry: entry without a file skipped")
        else:
            out[entry.file] = entry
    return out


def load_registry(path: Path) -> dict[str, ModelEntry]:
    try:
        return parse_registry(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}
