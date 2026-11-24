import asyncio
import random
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from backend.scheduler.services.jobs import JobService
from backend.scheduler.services.runner import HeadlessRunner
from backend.scheduler.services.scheduler import Scheduler
from backend.sessions.services.session_service import SessionService
from fastapi import FastAPI

START = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)  # a Monday


class FakeClock:
    def __init__(self, start: datetime = START) -> None:
        self.current = start
        self.slept: list[float] = []

    def now(self) -> datetime:
        return self.current

    def advance(self, **kw: float) -> None:
        self.current += timedelta(**kw)

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        await asyncio.sleep(0)


def make_jobs(app: FastAPI, clock: FakeClock, tz: str = "UTC", **kw: Any) -> JobService:
    return JobService(
        app.state.sessions,
        clock,
        ZoneInfo(tz),
        rng=random.Random(1),  # noqa: S311
        **kw,
    )


def make_scheduler(
    app: FastAPI,
    jobs: JobService,
    *,
    handlers: dict | None = None,
    mode: str = "default",
    run_timeout_s: float = 5.0,
    **kw: Any,
) -> Scheduler:
    runner = HeadlessRunner(
        app.state.react,
        SessionService(app.state.sessions),
        app.state.turns,
        mode=mode,
        timeout_s=run_timeout_s,
    )
    return Scheduler(
        jobs, jobs.clock, runner, handlers or {}, run_timeout_s=run_timeout_s, **kw
    )
