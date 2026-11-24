"""The in-process scheduler loop. One job at a time; missed runs are skipped."""

import asyncio
import contextlib
import logging

from backend.core.exceptions import DomainException
from backend.scheduler.models import ScheduledJob
from backend.scheduler.services.clock import Clock
from backend.scheduler.services.jobs import JobService, as_utc
from backend.scheduler.services.maintenance import BUILTINS, Handler
from backend.scheduler.services.runner import HeadlessRunner

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(  # noqa: PLR0913
        self,
        jobs: JobService,
        clock: Clock,
        runner: HeadlessRunner | None,
        handlers: dict[str, Handler],
        *,
        poll_s: float = 20.0,
        missed_grace_s: float = 300.0,
        run_timeout_s: float = 900.0,
    ) -> None:
        self.jobs = jobs
        self._clock = clock
        self._runner = runner
        self._handlers = handlers
        self._poll = poll_s
        self._grace = missed_grace_s
        self._timeout = run_timeout_s
        self._lock = asyncio.Lock()  # concurrency 1
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        for builtin in BUILTINS:
            await self.jobs.ensure_builtin(builtin.key, builtin.cron)
        await self.jobs.repair()
        self._task = asyncio.create_task(self._loop(), name="scheduler")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _loop(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("scheduler tick failed")
            await self._clock.sleep(self._poll)

    async def tick(self) -> int:
        """Run every due job once; returns how many were started or skipped."""
        handled = 0
        async with self._lock:
            for job in await self.jobs.due(self._clock.now()):
                late = (
                    self._clock.now() - (as_utc(job.next_run_at) or self._clock.now())
                ).total_seconds()
                if late > self._grace:
                    logger.info(
                        "schedule %s missed by %d s, skipped", job.public_id, late
                    )
                    await self.jobs.record_missed(job, late)
                else:
                    await self._execute(job)
                handled += 1
        return handled

    async def _execute(self, job: ScheduledJob) -> None:
        run_id = await self.jobs.begin_run(job.id)
        status, detail, session = "failed", "", None
        try:
            async with asyncio.timeout(self._timeout + 30):
                status, detail, session = await self._dispatch(job)
        except TimeoutError:
            detail = "timed out"
        except DomainException as exc:
            detail = f"error {exc.code}"
        except Exception as exc:
            logger.exception("scheduled job %s crashed", job.public_id)
            detail = type(exc).__name__
        await self.jobs.finish_run(job.id, run_id, status, detail, session)

    async def _dispatch(self, job: ScheduledJob) -> tuple[str, str, str | None]:
        if job.kind == "builtin":
            handler = self._handlers.get(job.prompt)
            if handler is None:
                return "failed", "unknown built-in task", None
            return "ok", await handler(), None
        if self._runner is None:
            return "failed", "no runner", None
        out = await self._runner.run(job.prompt)
        return out.status, out.detail, out.session_id
