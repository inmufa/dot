import asyncio
from datetime import timedelta

import pytest
from backend.core.exceptions import DomainException
from backend.scheduler.models import JobRun, ScheduledJob
from backend.scheduler.services.jobs import KEEP_RUNS
from backend.scheduler.services.maintenance import BUILTINS
from backend.scheduler.services.runner import Outcome
from httpx import AsyncClient
from sched_helpers import FakeClock, make_jobs, make_scheduler
from sqlalchemy import func, select, update


async def test_create_list_get_delete(app):
    jobs = make_jobs(app, FakeClock())
    info = await jobs.create("*/10 * * * *", "check the build")
    assert info.id.startswith("J")
    assert len(info.id) == 10
    assert info.next_run_at.isoformat() == "2026-03-02T12:10:00+00:00"
    assert [j.id for j in await jobs.all()] == [info.id]
    assert (await jobs.get(info.id)).prompt == "check the build"
    await jobs.delete(info.id)
    assert await jobs.all() == []


async def test_invalid_cron_and_unknown_id(app):
    jobs = make_jobs(app, FakeClock())
    with pytest.raises(DomainException) as exc:
        await jobs.create("not cron", "x")
    assert exc.value.code == 4035
    with pytest.raises(DomainException) as exc:
        await jobs.get("JXXXXXXXXX")
    assert exc.value.code == 4036


async def test_job_cap(app):
    jobs = make_jobs(app, FakeClock(), max_jobs=2)
    await jobs.create("* * * * *", "a")
    await jobs.create("* * * * *", "b")
    with pytest.raises(DomainException) as exc:
        await jobs.create("* * * * *", "c")
    assert exc.value.code == 4037


async def test_builtin_jobs_exist_once_and_cannot_be_deleted(app):
    jobs = make_jobs(app, FakeClock())
    for b in BUILTINS:
        await jobs.ensure_builtin(b.key, b.cron)
        await jobs.ensure_builtin(b.key, b.cron)
    rows = [j for j in await jobs.all() if j.kind == "builtin"]
    assert sorted(j.prompt for j in rows) == sorted(b.key for b in BUILTINS)
    with pytest.raises(DomainException) as exc:
        await jobs.delete(rows[0].id)
    assert exc.value.code == 4038


async def test_jitter_delays_within_bounds(app):
    jobs = make_jobs(app, FakeClock(), jitter_s=30)
    base = FakeClock().now() + timedelta(minutes=1)
    for _ in range(20):
        nxt = jobs.next_run("* * * * *")
        assert timedelta(0) <= nxt - base <= timedelta(seconds=30)


async def test_due_job_runs_once_and_is_rescheduled(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("*/10 * * * *", "ping")
    ran: list[str] = []

    class Runner:
        async def run(self, prompt: str):
            ran.append(prompt)

            return Outcome("ok", "fine", "SABCDEFGHJ")

    sched = make_scheduler(app, jobs)
    sched._runner = Runner()
    assert await sched.tick() == 0  # nothing due yet
    clock.advance(minutes=10)
    assert await sched.tick() == 1
    assert await sched.tick() == 0  # already rescheduled
    assert ran == ["ping"]
    row = await jobs.get(info.id)
    assert row.last_status == "ok"
    assert row.next_run_at.isoformat() == "2026-03-02T12:20:00+00:00"
    assert row.runs[0].status == "ok"
    assert row.runs[0].detail == "fine"
    assert row.runs[0].session_id == "SABCDEFGHJ"


async def test_missed_runs_are_skipped_not_replayed(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("*/10 * * * *", "ping")
    sched = make_scheduler(app, jobs, missed_grace_s=300)
    sched._runner = None
    clock.advance(hours=5)  # the backend was down
    assert await sched.tick() == 1
    row = await jobs.get(info.id)
    assert row.runs[0].status == "missed"
    assert "skipped" in row.runs[0].detail
    assert row.last_run_at is None
    assert row.next_run_at > clock.now()
    assert await sched.tick() == 0


async def test_failed_run_is_recorded_and_the_job_stays_enabled(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("* * * * *", "boom")

    class Runner:
        async def run(self, prompt: str):
            msg = "kaput"
            raise RuntimeError(msg)

    sched = make_scheduler(app, jobs)
    sched._runner = Runner()
    clock.advance(minutes=1)
    await sched.tick()
    row = await jobs.get(info.id)
    assert row.last_status == "failed"
    assert row.runs[0].detail == "RuntimeError"
    assert row.enabled is True


async def test_disabled_jobs_do_not_run(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    await jobs.create("* * * * *", "x", enabled=False)
    sched = make_scheduler(app, jobs)
    clock.advance(minutes=5)
    assert await sched.tick() == 0


async def test_concurrency_is_one(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    for p in ("a", "b"):
        await jobs.create("* * * * *", p)
    live, peak = 0, 0

    class Runner:
        async def run(self, prompt: str):
            nonlocal live, peak
            live += 1
            peak = max(peak, live)
            await asyncio.sleep(0.05)
            live -= 1

            return Outcome("ok")

    sched = make_scheduler(app, jobs)
    sched._runner = Runner()
    clock.advance(minutes=1)
    await asyncio.gather(sched.tick(), sched.tick())
    assert peak == 1


async def test_run_history_is_trimmed(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("* * * * *", "x")
    sched = make_scheduler(app, jobs, missed_grace_s=1)
    for _ in range(60):
        clock.advance(minutes=5)
        await sched.tick()

    async with app.state.sessions() as db:
        n = await db.scalar(select(func.count()).select_from(JobRun))
    assert n == KEEP_RUNS
    assert (await jobs.get(info.id)).runs[0].status == "missed"


async def test_repair_gives_a_next_run_to_a_job_without_one(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("0 * * * *", "x")
    async with app.state.sessions() as db:
        await db.execute(update(ScheduledJob).values(next_run_at=None))
        await db.commit()
    await jobs.repair()
    assert (
        await jobs.get(info.id)
    ).next_run_at.isoformat() == "2026-03-02T13:00:00+00:00"


async def test_start_registers_builtins_and_stop_is_clean(app):
    jobs = make_jobs(app, FakeClock())
    sched = make_scheduler(app, jobs)
    await sched.start()
    kinds = [j.kind for j in await jobs.all()]
    assert kinds.count("builtin") == len(BUILTINS)
    await sched.stop()
    assert sched._task.done()


async def test_api_crud_and_errors(authed: AsyncClient):
    r = await authed.post(
        "/v1/schedules", json={"cron": "0 9 * * 1-5", "prompt": "standup"}
    )
    assert r.status_code == 201
    job = r.json()
    assert job["id"].startswith("J")
    assert job["kind"] == "user"
    assert job["next_run_at"]
    assert (await authed.get(f"/v1/schedules/{job['id']}")).json()[
        "prompt"
    ] == "standup"
    assert job["id"] in [j["id"] for j in (await authed.get("/v1/schedules")).json()]
    bad = await authed.post("/v1/schedules", json={"cron": "nope", "prompt": "x"})
    assert bad.status_code == 400
    assert bad.json()[0]["code"] == 4035
    assert (await authed.delete(f"/v1/schedules/{job['id']}")).json() == {"ok": True}
    gone = await authed.delete(f"/v1/schedules/{job['id']}")
    assert gone.status_code == 404
    assert gone.json()[0]["code"] == 4036


async def test_api_needs_token(client):
    assert (await client.get("/v1/schedules")).status_code == 401


async def test_slot_is_persisted_before_the_run_executes(app):
    """A crash mid-run must not leave the job due again (no restart duplicates)."""
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("*/10 * * * *", "x")
    clock.advance(minutes=11)
    (job,) = await jobs.due(clock.now())
    await jobs.begin_run(job.id)  # ... and the process dies here
    assert await jobs.due(clock.now()) == []
    after = await jobs.get(info.id)
    assert after.last_run_at is not None
    assert after.next_run_at > clock.now()


async def test_restart_marks_an_open_run_interrupted(app):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("*/10 * * * *", "x")
    (job,) = await jobs.due(clock.now() + timedelta(minutes=11))
    await jobs.begin_run(job.id)
    await jobs.repair()
    run = (await jobs.get(info.id)).runs[0]
    assert (run.status, run.detail) == ("failed", "interrupted by a restart")
