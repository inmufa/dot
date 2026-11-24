import re
from pathlib import Path

import pytest
from backend.governance.services.audit import AuditService
from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from gov_helpers import chat, session, write_settings
from helpers import resolve_next, start_chat
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

BACKEND_SRC = Path(__file__).resolve().parents[2] / "backend"


async def audit(c: AsyncClient, query: str = "") -> dict:
    r = await c.get(f"/v1/audit{query}")
    assert r.status_code == 200, r.text
    return r.json()


async def test_every_decision_is_logged_with_its_source(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    write_settings(
        ws, {"permissions": {"deny": ["Bash(rm:*)"], "allow": ["Bash(echo:*)"]}}
    )
    (ws / "f.txt").write_text("x")
    llm.scripts = [
        reply(
            calls=[
                ("Read", {"file_path": "f.txt"}),
                ("Bash", {"command": "echo hi"}),
                ("Bash", {"command": "rm f.txt"}),
                ("Bash", {"command": "make"}),
                ("Bash", {"command": "echo $(ls)"}),
            ]
        ),
        reply("ok"),
    ]
    sid = await session(authed, "auto")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "allow")  # only `echo $(ls)` needs a human
    await task
    page = await audit(authed, f"?session={sid}&limit=100")
    rows = list(reversed(page["items"]))  # oldest first
    summary = [(r["tool"], r["decision"], r["source"]) for r in rows]
    assert ("Read", "allow", "mode") in summary
    assert ("Bash", "allow", "rule") in summary  # echo hi
    assert ("Bash", "deny", "rule") in summary  # rm
    assert ("Bash", "ask", "classifier") in summary
    assert ("Bash", "allow", "user") in summary
    assert ("Bash", "allow", "classifier") in summary  # make
    assert all(r["mode"] == "auto" and r["session"] == sid for r in rows)
    assert all(re.fullmatch(r"A[0-9A-Z]{9}", r["id"]) for r in rows)
    assert any("classifier stage A" in r["reason"] for r in rows)


async def test_user_decisions_are_logged_as_user_entries(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM
):
    llm.scripts = [reply(calls=[("Bash", {"command": "echo a"})]), reply("ok")]
    sid = await session(authed, "default")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "reject")
    await task
    rows = (await audit(authed, f"?session={sid}"))["items"]
    assert [(r["decision"], r["source"]) for r in reversed(rows)] == [
        ("ask", "mode"),
        ("deny", "user"),
    ]


async def test_args_are_redacted(authed: AsyncClient, llm: ScriptedLLM):
    cmd = "curl -H 'Authorization: Bearer sk-abcdef123456' https://x"
    llm.scripts = [
        reply(calls=[("Bash", {"command": cmd, "api_key": "hunter2", "cwd": "/"})]),
        reply("ok"),
    ]
    sid = await session(authed, "plan")
    await chat(authed, sid)
    (row,) = (await audit(authed, f"?session={sid}"))["items"]
    assert row["args"]["api_key"] == "***"
    assert "sk-abcdef123456" not in str(row["args"])
    assert "Bearer ***" in row["args"]["command"]


async def test_long_arguments_are_clipped(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    big = "x" * 5000
    llm.scripts = [
        reply(calls=[("Write", {"file_path": "a", "content": big})]),
        reply("ok"),
    ]
    sid = await session(authed, "plan")
    await chat(authed, sid)
    (row,) = (await audit(authed, f"?session={sid}"))["items"]
    assert len(row["args"]["content"]) < 600


async def test_pagination_and_session_filter(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [
        reply(calls=[("Read", {"file_path": f"f{i}"}) for i in range(5)]),
        reply("ok"),
    ]
    sid = await session(authed, "default")
    other = await session(authed, "default")
    await chat(authed, sid)
    llm.scripts = [reply(calls=[("Read", {"file_path": "z"})]), reply("ok")]
    await chat(authed, other)
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        q = f"?session={sid}&limit=2" + (f"&cursor={cursor}" if cursor else "")
        page = await audit(authed, q)
        pages += 1
        assert len(page["items"]) <= 2
        seen += [r["args"]["file_path"] for r in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert pages == 3
    assert seen == ["f4", "f3", "f2", "f1", "f0"]  # newest first, no gaps, no dupes
    everything = (await audit(authed, "?limit=200"))["items"]
    assert {r["session"] for r in everything} == {sid, other}


async def test_audit_requires_auth_and_validates_limit(
    client: AsyncClient, authed: AsyncClient
):
    assert (
        await client.get("/v1/audit", headers={"Authorization": "Bearer nope"})
    ).status_code == 401
    assert (await authed.get("/v1/audit?limit=0")).status_code == 422
    assert (await authed.get("/v1/audit?limit=201")).status_code == 422
    assert (await audit(authed))["items"] == []


async def test_database_rejects_update_and_delete(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM
):
    llm.scripts = [reply(calls=[("Read", {"file_path": "x"})]), reply("ok")]
    await chat(authed, await session(authed))
    async with app.state.sessions() as db:
        for sql in (
            "UPDATE audit_log SET decision = 'allow'",
            "DELETE FROM audit_log",
        ):
            with pytest.raises(DBAPIError, match="append-only"):
                await db.execute(text(sql))
            await db.rollback()
        count = (await db.execute(text("SELECT count(*) FROM audit_log"))).scalar()
    assert count == 1


def test_service_has_no_update_or_delete_path():
    public = {n for n in dir(AuditService) if not n.startswith("_")}
    assert public == {"append", "page"}
    for path in BACKEND_SRC.rglob("*.py"):
        src = path.read_text()
        assert not re.search(r"(update|delete)\(\s*AuditLog", src), path
        assert (
            "AuditLog" not in src or "governance" in str(path) or "main.py" in str(path)
        )
