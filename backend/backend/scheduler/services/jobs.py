"""Persistent scheduled jobs: CRUD, due lookup, run history."""

import random
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from dot_contracts.schedules import RunInfo, ScheduleInfo
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.exceptions import DomainException
from backend.core.public_id import new_public_id
from backend.scheduler.models import JobRun, ScheduledJob
from backend.scheduler.services import cron
from backend.scheduler.services.clock import Clock

INVALID_CRON = 4035
NOT_FOUND = 4036
TOO_MANY = 4037
BUILTIN = 4038
KEEP_RUNS = 50
DETAIL_CHARS = 500


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; they were stored as UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _info(job: ScheduledJob, runs: list[JobRun]) -> ScheduleInfo:
    return ScheduleInfo(
        id=job.public_id,
        kind=job.kind,  # type: ignore[arg-type]
        cron=job.cron,
        prompt=job.prompt,
        enabled=job.enabled,
        created_at=as_utc(job.created_at),  # type: ignore[arg-type]
        last_run_at=as_utc(job.last_run_at),
        next_run_at=as_utc(job.next_run_at),
        last_status=job.last_status,
        runs=[
            RunInfo(
                started_at=as_utc(r.started_at),  # type: ignore[arg-type]
                finished_at=as_utc(r.finished_at),
                status=r.status,  # type: ignore[arg-type]
                session_id=r.session_id,
                detail=r.detail,
            )
            for r in runs
        ],
    )


class JobService:
    def __init__(
        self,
        maker: async_sessionmaker,
        clock: Clock,
        tz: ZoneInfo,
        *,
        max_jobs: int = 50,
        jitter_s: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        self._maker = maker
        self.clock = clock
        self.tz = tz
        self._max = max_jobs
        self._jitter = jitter_s
        self._rng = rng or random.Random()  # noqa: S311

    def next_run(self, expr: str, after: datetime | None = None) -> datetime:
        base = after or self.clock.now()
        try:
            fire = cron.next_after(expr, base, self.tz)
        except cron.CronError as exc:
            raise DomainException(INVALID_CRON, {"reason": str(exc)}) from exc
        return fire + timedelta(seconds=self._rng.uniform(0, self._jitter))

    async def create(
        self, expr: str, prompt: str, *, enabled: bool = True
    ) -> ScheduleInfo:
        nxt = self.next_run(expr)  # validates the expression first
        async with self._maker() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(ScheduledJob)
                .where(ScheduledJob.kind == "user")
            )
            if (count or 0) >= self._max:
                raise DomainException(TOO_MANY)
            job = ScheduledJob(
                public_id=new_public_id("J"),
                cron=expr.strip(),
                prompt=prompt,
                enabled=enabled,
                next_run_at=nxt,
            )
            db.add(job)
            await db.commit()
            return _info(job, [])

    async def ensure_builtin(self, key: str, expr: str) -> None:
        async with self._maker() as db:
            row = await db.scalar(
                select(ScheduledJob).where(
                    ScheduledJob.kind == "builtin", ScheduledJob.prompt == key
                )
            )
            if row is not None:
                return
            db.add(
                ScheduledJob(
                    public_id=new_public_id("J"),
                    kind="builtin",
                    cron=expr,
                    prompt=key,
                    next_run_at=self.next_run(expr),
                )
            )
            await db.commit()

    async def _get(self, db, public_id: str) -> ScheduledJob:
        job = await db.scalar(
            select(ScheduledJob).where(ScheduledJob.public_id == public_id)
        )
        if job is None:
            raise DomainException(NOT_FOUND)
        return job

    async def get(self, public_id: str) -> ScheduleInfo:
        async with self._maker() as db:
            job = await self._get(db, public_id)
            return _info(job, await self._runs(db, job.id, 10))

    async def all(self) -> list[ScheduleInfo]:
        async with self._maker() as db:
            jobs = (
                await db.scalars(select(ScheduledJob).order_by(ScheduledJob.id))
            ).all()
            return [_info(j, await self._runs(db, j.id, 5)) for j in jobs]

    async def delete(self, public_id: str) -> None:
        async with self._maker() as db:
            job = await self._get(db, public_id)
            if job.kind == "builtin":
                raise DomainException(BUILTIN)
            await db.execute(delete(JobRun).where(JobRun.job_id == job.id))
            await db.delete(job)
            await db.commit()

    @staticmethod
    async def _runs(db, job_id: int, limit: int) -> list[JobRun]:
        q = (
            select(JobRun)
            .where(JobRun.job_id == job_id)
            .order_by(JobRun.id.desc())
            .limit(limit)
        )
        return list((await db.scalars(q)).all())

    # ---- scheduler side ----
    async def due(self, now: datetime) -> list[ScheduledJob]:
        async with self._maker() as db:
            q = (
                select(ScheduledJob)
                .where(ScheduledJob.enabled.is_(True))
                .order_by(ScheduledJob.next_run_at, ScheduledJob.id)
            )
            rows = (await db.scalars(q)).all()
        return [
            j for j in rows if (n := as_utc(j.next_run_at)) is not None and n <= now
        ]

    async def repair(self) -> None:
        """Give enabled jobs without a next run one (fresh row or cleared state)."""
        async with self._maker() as db:
            rows = (
                await db.scalars(
                    select(ScheduledJob).where(
                        ScheduledJob.enabled.is_(True),
                        ScheduledJob.next_run_at.is_(None),
                    )
                )
            ).all()
            for job in rows:
                job.next_run_at = self.next_run(job.cron)
            # A run still open at startup was cut off by a restart.
            await db.execute(
                update(JobRun)
                .where(JobRun.status == "running")
                .values(status="failed", detail="interrupted by a restart")
            )
            await db.commit()

    async def begin_run(self, job_id: int, *, missed: bool = False) -> int:
        """Open a run and move the job to its next slot BEFORE anything executes,
        so a crash or restart mid-run can never fire the same slot twice."""
        async with self._maker() as db:
            job = await db.get(ScheduledJob, job_id)
            if job is not None:
                now = self.clock.now()
                if not missed:
                    job.last_run_at = now
                job.next_run_at = self.next_run(job.cron, now)
            n = await db.scalar(
                select(func.coalesce(func.max(JobRun.seq), 0)).where(
                    JobRun.job_id == job_id
                )
            )
            run = JobRun(job_id=job_id, started_at=self.clock.now(), seq=(n or 0) + 1)
            db.add(run)
            await db.commit()
            return run.id

    async def finish_run(
        self,
        job_id: int,
        run_id: int,
        status: str,
        detail: str = "",
        session_id: str | None = None,
    ) -> None:
        """Close the run and move the job to its next slot (computed from now)."""
        now = self.clock.now()
        async with self._maker() as db:
            run = await db.get(JobRun, run_id)
            job = await db.get(ScheduledJob, job_id)
            if run is None or job is None:
                return
            run.status, run.finished_at = status, now
            run.detail, run.session_id = detail[:DETAIL_CHARS], session_id
            if status != "missed":
                job.last_run_at = now
            job.last_status = status
            job.next_run_at = self.next_run(job.cron, now)
            await db.commit()
            await self._trim(db, job_id)

    async def record_missed(self, job: ScheduledJob, late_s: float) -> None:
        run_id = await self.begin_run(job.id, missed=True)
        await self.finish_run(
            job.id, run_id, "missed", f"skipped: {int(late_s)} s late"
        )

    async def _trim(self, db, job_id: int) -> None:
        keep = (
            select(JobRun.id)
            .where(JobRun.job_id == job_id)
            .order_by(JobRun.id.desc())
            .limit(KEEP_RUNS)
        )
        await db.execute(
            delete(JobRun).where(JobRun.job_id == job_id, JobRun.id.not_in(keep))
        )
        await db.commit()

    async def prune_history(self, days: float) -> int:
        cutoff = self.clock.now() - timedelta(days=days)
        async with self._maker() as db:
            res = await db.execute(
                delete(JobRun).where(
                    JobRun.finished_at.is_not(None), JobRun.finished_at < cutoff
                )
            )
            await db.commit()
            return res.rowcount or 0
