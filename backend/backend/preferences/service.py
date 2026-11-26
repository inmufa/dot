"""Reply style stored in ~/.dot/preferences.json and rendered as a prompt block."""

import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

Tone = Literal["supportive", "balanced", "blunt"]
Emoji = Literal["normal", "less", "none"]

_TONE = {
    "supportive": (
        "Tone: warm and encouraging. Note what works before what does not, "
        "and correct real mistakes gently but clearly."
    ),
    "balanced": "Tone: plain and matter-of-fact. Friendly, no flattery, no filler.",
    "blunt": (
        "Tone: direct and blunt. No softening, compliments or filler. Lead with "
        "the problem and the fix."
    ),
}
_EMOJI = {
    "normal": "Emojis: fine where they help (headings, short lists), not in every line.",
    "less": "Emojis: at most one or two in a long answer, none in short ones.",
    "none": "Emojis: never use them.",
}


class ReplyStyle(BaseModel):
    tone: Tone = "balanced"
    emoji: Emoji = "less"

    def block(self) -> str:
        return f"{_TONE[self.tone]}\n{_EMOJI[self.emoji]}"


class PreferencesService:
    """Reads once, writes atomically; `on_change` lets the prompt suffix rebuild."""

    def __init__(self, path: Path, on_change: Callable[[], None] | None = None) -> None:
        self._path = path.expanduser()
        self.on_change = on_change
        self._style = self._load()

    def _load(self) -> ReplyStyle:
        try:
            return ReplyStyle.model_validate(json.loads(self._path.read_text()))
        except FileNotFoundError:
            return ReplyStyle()
        except (OSError, ValueError, ValidationError):
            logger.warning("unreadable %s, using defaults", self._path)
            return ReplyStyle()

    @property
    def style(self) -> ReplyStyle:
        return self._style

    def save(self, style: ReplyStyle) -> ReplyStyle:
        if style == self._style:
            return style
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".prefs-")
        with os.fdopen(fd, "w") as f:
            f.write(style.model_dump_json(indent=2))
        Path(tmp).replace(self._path)
        self._style = style
        if self.on_change:
            self.on_change()
        return style
