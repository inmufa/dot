"""Reasoning effort levels (F13)."""

from enum import StrEnum

from pydantic import BaseModel


class Effort(StrEnum):
    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


class EffortInfo(BaseModel):
    """What a turn actually ran with; sent on the usage event."""

    requested: Effort  # session or request value
    level: Effort  # effective (ultrathink raises it to max, voice forces off)
    thinking: bool
    ultrathink: bool = False
    max_tokens: int | None = None
    temperature: float | None = None
    native: bool = False  # level passed through as reasoning_effort
