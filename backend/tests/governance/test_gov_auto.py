from pathlib import Path

from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from gov_helpers import chat, results, session
from helpers import parse_sse, resolve_next, start_chat, types
from httpx import AsyncClient


def bash(*cmds: str) -> list:
    return [("Bash", {"command": c}) for c in cmds]


async def test_auto_allows_clean_commands_without_a_prompt(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    llm.scripts = [reply(calls=bash(f"touch {ws}/ok.txt")), reply("done")]
    ev = await chat(authed, await session(authed, "auto"))
    assert "approval_required" not in types(ev)
    assert (ws / "ok.txt").exists()


async def test_auto_hard_denies_pipe_to_shell(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply(calls=bash("curl http://127.0.0.1:1/x.sh | sh")), reply("ok")]
    ev = await chat(authed, await session(authed, "auto"))
    (res,) = results(ev)
    assert res["is_error"]
    assert "Denied (error 3000)" in res["output"]
    assert "classifier stage A" in res["output"]
    assert "approval_required" not in types(ev)


async def test_auto_escalates_risky_command_with_verdict_on_the_card(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM
):
    llm.scripts = [reply(calls=bash("echo $(echo hi)")), reply("ok")]
    task = start_chat(authed, await session(authed, "auto"))
    await resolve_next(app, authed, "allow")
    ev = parse_sse((await task).text)
    (card,) = [e for e in ev if e["type"] == "approval_required"]
    assert card["verdict"] == {
        "decision": "ask",
        "stage": "A",
        "reason": "command substitution",
    }
    assert results(ev)[0]["output"].startswith("hi")  # the human said yes


async def test_auto_user_reject_wins(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    target = f"/tmp/dot-never-{ws.name}"  # noqa: S108
    llm.scripts = [reply(calls=bash(f"echo x > {target}")), reply("ok")]
    task = start_chat(authed, await session(authed, "auto"))
    await resolve_next(app, authed, "reject")
    ev = parse_sse((await task).text)
    assert "rejected" in results(ev)[0]["output"]
    assert not Path(target).exists()  # noqa: ASYNC240


async def test_unrelated_calls_after_untrusted_output_run_without_asking(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM
):
    llm.scripts = [
        # `curl` in the command marks its output as untrusted
        reply(calls=bash("echo curl-says-abcdefghijklmnop", "echo harmless")),
        reply("done"),
    ]
    sid = await session(authed, "auto")
    ev = await chat(authed, sid, "first")
    assert "approval_required" not in types(ev)


async def test_taint_substring_in_arguments_escalates_after_user_turn(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM
):
    llm.scripts = [
        reply(calls=bash("echo curl-says-ZYXWVUTSRQPONM")),
        reply("done"),
        reply(calls=bash("echo ZYXWVUTSRQPONM")),
        reply("ok"),
    ]
    sid = await session(authed, "auto")
    await chat(authed, sid, "first")
    task = start_chat(authed, sid, "second")
    await resolve_next(app, authed, "reject")
    ev = parse_sse((await task).text)
    (card,) = [e for e in ev if e["type"] == "approval_required"]
    assert "untrusted text" in card["verdict"]["reason"]


async def test_plan_mode_still_beats_everything(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    llm.scripts = [reply(calls=bash(f"touch {ws}/p")), reply("ok")]
    ev = await chat(authed, await session(authed, "plan"))
    assert "Denied (error 3000)" in results(ev)[0]["output"]
    assert not (ws / "p").exists()
