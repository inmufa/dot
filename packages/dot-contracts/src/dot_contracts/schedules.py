"""Scheduled job DTOs served under /v1/schedules."""

from typing import Literal

from pydantic import BaseModel, Field

from dot_contracts.types import UtcDatetime


class ScheduleIn(BaseModel):
    cron: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=20_000)
    enabled: bool = True


class RunInfo(BaseModel):
    started_at: UtcDatetime
    finished_at: UtcDatetime | None = None
    status: Literal["ok", "failed", "missed", "running"]
    session_id: str | None = None
    detail: str = ""


class ScheduleInfo(BaseModel):
    id: str
    kind: Literal["user", "builtin"]
    cron: str
    prompt: str
    enabled: bool
    created_at: UtcDatetime
    last_run_at: UtcDatetime | None = None
    next_run_at: UtcDatetime | None = None
    last_status: str | None = None
    runs: list[RunInfo] = Field(default_factory=list)
