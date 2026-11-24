import asyncio

from backend.core.exceptions import DomainException
from backend.routing.clients.scripted import reply
from backend.scheduler.services.runner import HeadlessRunner, safe_mode
from backend.sessions.services.session_service import SessionService
from helpers import resolve_next, until
from sched_helpers import FakeClock, make_jobs, make_scheduler


def runner_for(app, **kw) -> HeadlessRunner:
    args = {"mode": "default", "timeout_s": 5.0, **kw}
    return HeadlessRunner(
        app.state.react, SessionService(app.state.sessions), app.state.turns, **args
    )


async def test_headless_run_uses_a_fresh_session_through_the_engine(app, llm):
    llm.scripts = [reply("all done")]
    out = await runner_for(app).run("summarise the repo")
    assert out.status == "ok"
    assert out.detail == "all done"
    sessions = SessionService(app.state.sessions)
    row = await sessions.get(out.session_id)
    assert row.mode == "default"
    assert row.title.startswith("[scheduled] summarise")
    msgs = await sessions.messages(out.session_id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == "summarise the repo"
    assert not app.state.turns.is_active(out.session_id)


async def test_every_run_gets_its_own_session(app, llm):
    llm.scripts = [reply("a"), reply("b")]
    r = runner_for(app)
    one, two = await r.run("x"), await r.run("x")
    assert one.session_id != two.session_id


def test_bypass_is_never_used_for_scheduled_runs():
    assert safe_mode("bypass") == "default"
    assert safe_mode("nonsense") == "default"
    assert safe_mode("plan") == "plan"
    assert safe_mode("acceptEdits") == "acceptEdits"


async def test_configured_mode_is_applied(app, llm):
    llm.scripts = [reply("ok")]
    out = await runner_for(app, mode="plan").run("look")
    row = await SessionService(app.state.sessions).get(out.session_id)
    assert row.mode == "plan"


async def test_plan_mode_run_cannot_mutate(app, llm, ws):
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "a.txt"), "content": "x"})]),
        reply("gave up"),
    ]
    out = await runner_for(app, mode="plan").run("write a file")
    assert out.status == "ok"
    assert not (ws / "a.txt").exists()


async def test_unapproved_mutation_waits_then_fails(app, llm, ws):
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "a.txt"), "content": "x"})])
    ]
    out = await runner_for(app).run("write a file")  # approval_timeout_s = 0.3
    assert out.status == "failed"
    assert "3001" in out.detail
    assert not (ws / "a.txt").exists()
    assert not app.state.approvals.pending_ids()


async def test_user_can_approve_a_scheduled_call(app, llm, authed, ws):
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "a.txt"), "content": "x"})]),
        reply("written"),
    ]
    app.state.settings.approval_timeout_s = 5
    task = asyncio.create_task(runner_for(app).run("write"))
    await resolve_next(app, authed, "allow")
    out = await task
    assert out.status == "ok"
    assert (ws / "a.txt").read_text() == "x"


async def test_run_timeout_cancels_the_turn(app, llm):
    gate = asyncio.Event()
    llm.scripts = [[gate]]
    out = await runner_for(app, timeout_s=0.3).run("hang")
    assert out.status == "failed"
    assert out.detail == "timed out"
    assert not app.state.turns.is_active(out.session_id)


async def test_model_failure_is_a_failed_run(app, llm):
    async def down(*_a, **_k):
        raise DomainException(4000)
        yield

    llm.stream = down
    out = await runner_for(app).run("x")
    assert out.status == "failed"


async def test_scheduler_runs_a_job_end_to_end(app, llm):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("0 13 * * *", "daily report")
    llm.scripts = [reply("report ready")]
    sched = make_scheduler(app, jobs)
    clock.advance(hours=1)
    await sched.tick()
    row = await jobs.get(info.id)
    assert row.last_status == "ok"
    assert row.runs[0].session_id
    msgs = await SessionService(app.state.sessions).messages(row.runs[0].session_id)
    assert msgs[0].content == "daily report"


async def test_approval_wait_failure_is_recorded_on_the_job(app, llm, ws):
    clock = FakeClock()
    jobs = make_jobs(app, clock)
    info = await jobs.create("0 13 * * *", "write")
    llm.scripts = [
        reply(calls=[("Write", {"file_path": str(ws / "z.txt"), "content": "x"})])
    ]
    sched = make_scheduler(app, jobs)
    clock.advance(hours=1)
    await sched.tick()
    row = await jobs.get(info.id)
    assert row.last_status == "failed"
    assert "3001" in row.runs[0].detail
    assert (await jobs.get(info.id)).enabled is True
    await until(lambda: not app.state.approvals.pending_ids())
