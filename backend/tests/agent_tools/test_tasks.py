import pytest
from agent_helpers import RoutedLLM, assert_paired, chat, results, session
from backend.cognition.services.tasks.summary import open_tasks_summary
from backend.cognition.services.tasks.task_service import TaskError, TaskPatch
from backend.routing.clients.scripted import reply
from fastapi import FastAPI
from httpx import AsyncClient


async def test_dag_rules_in_the_service(authed: AsyncClient, app: FastAPI):
    svc = app.state.agent.tasks
    sid = await session(authed)
    a = await svc.create(sid, "design")
    b = await svc.create(sid, "build", blocked_by=[a.id])
    c = await svc.create(sid, "ship", blocked_by=[b.id])
    assert a.id.startswith("T")
    with pytest.raises(TaskError, match="unknown blocker"):
        await svc.create(sid, "x", blocked_by=["TNOPE00000"])
    with pytest.raises(TaskError, match="cycle"):
        await svc.update(sid, a.id, TaskPatch(blocked_by=[c.id]))  # a<-c<-b<-a
    with pytest.raises(TaskError, match="cycle"):
        await svc.update(sid, a.id, TaskPatch(blocked_by=[a.id]))
    with pytest.raises(TaskError, match="blocked by open"):
        await svc.update(sid, b.id, TaskPatch(status="in_progress"))
    with pytest.raises(TaskError, match="status must be"):
        await svc.update(sid, a.id, TaskPatch(status="weird"))
    await svc.update(sid, a.id, TaskPatch(status="completed"))
    started = await svc.update(sid, b.id, TaskPatch(status="in_progress"))
    assert started.status == "in_progress"
    with pytest.raises(TaskError, match="blocked by open"):
        await svc.update(sid, c.id, TaskPatch(status="completed"))
    # Reopening the blocker does not break renaming the running task.
    await svc.update(sid, a.id, TaskPatch(status="pending"))
    renamed = await svc.update(sid, b.id, TaskPatch(subject="build it"))
    assert renamed.subject == "build it"


async def test_task_tools_report_errors_as_text_not_crashes(
    authed: AsyncClient, llm: RoutedLLM
):
    llm.scripts = [
        reply(calls=[("TaskCreate", {"subject": "one"})]),
        reply(calls=[("TaskList", {})]),
        reply(calls=[("TaskGet", {"task_id": "TNOPE00000"})]),
        reply(calls=[("TaskUpdate", {"task_id": "TNOPE00000", "status": "completed"})]),
        reply(calls=[("TaskCreate", {"subject": "two", "blocked_by": ["TNOPE00000"]})]),
        reply("done"),
    ]
    ev = await chat(authed, await session(authed))
    assert_paired(ev)
    r = results(ev)
    assert r[0]["output"].startswith("Created T")
    assert "[pending] one" in r[0]["output"]
    assert "[pending] one" in r[1]["output"]
    assert all(x["is_error"] for x in r[2:5])
    assert "no task with that id" in r[2]["output"]
    assert "unknown blocker" in r[4]["output"]
    assert ev[-1]["stop_reason"] == "end_turn"


async def test_tools_blocked_start_then_api_and_reminder(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    sid = await session(authed)
    svc = app.state.agent.tasks
    a = await svc.create(sid, "first")
    b = await svc.create(sid, "second", blocked_by=[a.id])
    llm.scripts = [
        reply(calls=[("TaskUpdate", {"task_id": b.id, "status": "in_progress"})]),
        reply(calls=[("TaskUpdate", {"task_id": a.id, "status": "completed"})]),
        reply(calls=[("TaskUpdate", {"task_id": b.id, "status": "in_progress"})]),
        reply("ok"),
    ]
    ev = await chat(authed, sid)
    r = results(ev)
    assert r[0]["is_error"]
    assert "blocked by open task(s)" in r[0]["output"]
    assert not r[1]["is_error"]
    assert not r[2]["is_error"]
    api = (await authed.get(f"/v1/sessions/{sid}/tasks")).json()
    assert [(t["id"], t["status"]) for t in api] == [
        (a.id, "completed"),
        (b.id, "in_progress"),
    ]
    assert api[1]["blocked_by"] == [a.id]
    # The reminder of the next turn lists only unfinished tasks; prefix untouched.
    llm.scripts = [reply("again")]
    await chat(authed, sid)
    user_msgs = [m for m in llm.requests[-1]["messages"] if m["role"] == "user"]
    assert f"Open tasks:\n- {b.id} [in_progress] second" in user_msgs[-1]["content"]
    assert a.id not in user_msgs[-1]["content"]
    assert llm.requests[-1]["messages"][0] == llm.requests[0]["messages"][0]
    assert "second" in await open_tasks_summary(sid)
    assert (await authed.get("/v1/sessions/SNOPE00000/tasks")).status_code == 404


async def test_tasks_are_per_session(authed: AsyncClient, app: FastAPI):
    s1, s2 = await session(authed), await session(authed)
    await app.state.agent.tasks.create(s1, "mine")
    assert (await authed.get(f"/v1/sessions/{s2}/tasks")).json() == []
    assert await open_tasks_summary(s2) == ""
