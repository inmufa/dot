"""Telemetry, models and usage (F8, F14 /usage)."""

from pydantic import BaseModel, Field

from dot_contracts.types import UtcDatetime


class SlotInfo(BaseModel):
    id: int
    busy: bool
    context_used: int | None = None
    context_size: int | None = None


class Telemetry(BaseModel):
    llm_up: bool
    model: str | None = None
    context_size: int | None = None
    slots: list[SlotInfo] = Field(default_factory=list)
    tokens_per_s: float | None = None  # last generation speed, null if unknown
    prompt_tokens_per_s: float | None = None
    vram_used_mb: int | None = None
    vram_total_mb: int | None = None
    sandbox_up: bool = False
    voice_up: bool = False  # voice worker reachable with a speech model loaded
    uptime_s: float
    reasoning_effort_levels: list[str] | None = None  # from llama /props template caps
    vision: bool = False  # true only when the running server has the projector loaded


class ModelInfo(BaseModel):
    name: str  # file name
    size_mb: int
    active: bool
    vision: bool = False
    # From models/registry.toml; unlisted files get the defaults (no effort, no vision).
    display_name: str | None = None
    listed: bool = False
    context_max: int | None = None
    thinking: bool = False
    effort_levels: list[str] = Field(default_factory=list)
    recommended_profile: str | None = None
    # Run on the host to switch to this file; the backend cannot switch by itself.
    switch_command: str = ""


class ModelSelectIn(BaseModel):
    name: str


class UsageOut(BaseModel):
    """GET /v1/sessions/{id}/usage, aggregated from per-turn records."""

    turns: int
    prompt_tokens: int
    completion_tokens: int
    context_tokens: int
    context_limit: int
    tokens_per_s: float | None = None  # mean over turns with timing
    last_turn_ms: int | None = None
    last_turn_at: UtcDatetime | None = None
    efforts: dict[str, int] = Field(default_factory=dict)  # turns per effective level
