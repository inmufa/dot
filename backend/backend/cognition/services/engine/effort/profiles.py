# ruff: noqa: FBT003
"""Effort levels -> sampling, token allowance and prompt hints."""

import re
from dataclasses import dataclass

from dot_contracts.ui.effort import Effort, EffortInfo

from backend.routing.clients.llm_types import StreamOptions

_ULTRA = re.compile(r"\bultrathink\b", re.IGNORECASE)
_FENCE = re.compile(r"```.*?(```|$)|`[^`\n]*`", re.DOTALL)
_QUOTE = re.compile(r"^\s*>.*$", re.MULTILINE)
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class Profile:
    thinking: bool
    max_tokens: int | None
    think_cap: int | None  # reasoning tokens before it is cut; None = no cap
    temperature: float | None
    top_p: float | None = None
    presence_penalty: float | None = None
    hint: str = ""
    verify: bool = False


PROFILES: dict[Effort, Profile] = {
    Effort.OFF: Profile(False, 2048, None, 0.7, 0.8, 1.5),
    Effort.LOW: Profile(
        True,
        3072,
        1500,
        0.6,
        hint="Think briefly and answer concisely.",
    ),
    Effort.MEDIUM: Profile(True, None, 4000, None),
    Effort.HIGH: Profile(
        True,
        12000,
        9000,
        0.6,
        hint="Think carefully and double-check your work before answering.",
    ),
    Effort.MAX: Profile(
        True,
        20000,
        15000,
        0.5,
        hint=(
            "Think very carefully, consider edge cases and double-check every "
            "step. Take the time you need."
        ),
        verify=True,
    ),
}


def has_ultrathink(text: str) -> bool:
    """The keyword counts only as plain prose, not inside code or a quote."""
    return bool(_ULTRA.search(_QUOTE.sub("", _FENCE.sub("", text))))


def effective(requested: Effort, text: str, *, voice: bool) -> tuple[Effort, bool]:
    """(level, ultrathink) for one turn. Voice forces off."""
    if voice:
        return Effort.OFF, False
    if has_ultrathink(text):
        return Effort.MAX, True
    return requested, False


@dataclass
class EffortState:
    """Resolved per turn; read by the options provider and the engine."""

    info: EffortInfo
    profile: Profile
    options: StreamOptions
    verified: bool = False


def build_state(
    requested: Effort,
    level: Effort,
    *,
    ultrathink: bool,
    native_levels: list[str],
) -> EffortState:
    p = PROFILES[level]
    native = level != Effort.OFF and level.value in native_levels
    options = StreamOptions(
        thinking=None if level == Effort.MEDIUM else p.thinking,  # client default
        reasoning_effort=level.value if native else None,
        temperature=p.temperature,
        top_p=p.top_p,
        presence_penalty=p.presence_penalty,
        max_tokens=p.max_tokens,
    )
    info = EffortInfo(
        requested=requested,
        level=level,
        thinking=p.thinking,
        ultrathink=ultrathink,
        max_tokens=p.max_tokens,
        temperature=p.temperature,
        native=native,
    )
    return EffortState(info, p, options)
