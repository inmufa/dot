import json
import time
from pathlib import Path

from backend.governance.services.hooks_engine import matches
from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from gov_helpers import chat, hook, results, session, write_settings
from helpers import resolve_next, start_chat, until
from httpx import AsyncClient

REWRITE = (
    "import json, sys\n"
    "ti = json.load(sys.stdin)['tool_input']\n"
    "ti['command'] = 'echo rewritten'\n"
    "print(json.dumps({'updatedInput': ti}))\n"
)


def bash(cmd: str) -> list:
    return [("Bash", {"command": cmd})]


def test_matcher_semantics():
    assert matches("*", "Bash")
    assert matches("", "Bash")
    assert matches("Bash", "Bash")
    assert matches("Edit|Write", "Write")
    assert not matches("Edit|Write", "Bash")
    assert not matches("Bash", "BashOutput")  # full match, not prefix
    assert matches("Bash", None)  # non-tool events ignore the matcher
    assert matches("(", "(")  # broken regex falls back to equality
    assert not matches("(", "Bash")


async def test_exit_2_blocks_and_feeds_stderr_to_model(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    cmd = 'cat >/dev/null; echo "no deploys today" >&2; exit 2'
    write_settings(ws, hook("PreToolUse", cmd, "Bash"))
    llm.scripts = [reply(calls=bash(f"touch {ws}/ran")), reply("ok")]
    ev = await chat(authed, await session(authed))
    (res,) = results(ev)
    assert res["is_error"]
    assert "no deploys today" in res["output"]
    assert not (ws / "ran").exists()
    assert ev[-1]["stop_reason"] == "end_turn"
    tool_msg = [m for m in llm.requests[-1]["messages"] if m["role"] == "tool"]
    assert "no deploys today" in tool_msg[0]["content"]


async def test_hook_gets_json_on_stdin(authed: AsyncClient, llm: ScriptedLLM, ws: Path):
    write_settings(ws, hook("PreToolUse", "cat > hook_in.json"))
    llm.scripts = [reply(calls=bash("echo hi")), reply("ok")]
    sid = await session(authed)
    ev = await chat(authed, sid)
    assert not results(ev)[0]["is_error"]
    got = json.loads((ws / "hook_in.json").read_text())
    assert got["hook_event_name"] == "PreToolUse"
    assert got["tool_name"] == "Bash"
    assert got["tool_input"] == {"command": "echo hi"}
    assert got["session_id"] == sid
    assert got["cwd"] == str(ws)


async def test_other_exit_codes_and_timeouts_do_not_block(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    write_settings(ws, hook("PreToolUse", "echo oops >&2; exit 1"))
    llm.scripts = [reply(calls=bash(f"touch {ws}/ran")), reply("ok")]
    ev = await chat(authed, await session(authed))
    assert not results(ev)[0]["is_error"]
    assert (ws / "ran").exists()

    write_settings(ws, hook("PreToolUse", "sleep 5", timeout=0.3))
    llm.scripts = [reply(calls=bash(f"touch {ws}/ran2")), reply("ok")]
    t0 = time.monotonic()
    ev = await chat(authed, await session(authed))
    assert time.monotonic() - t0 < 4
    assert (ws / "ran2").exists()
    assert not results(ev)[0]["is_error"]


async def test_pre_tool_hook_can_rewrite_arguments(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    (ws / "rewrite.py").write_text(REWRITE)
    write_settings(ws, hook("PreToolUse", "python3 rewrite.py", "Bash"))
    llm.scripts = [reply(calls=bash("echo original")), reply("ok")]
    ev = await chat(authed, await session(authed))
    out = results(ev)[0]["output"]
    assert "rewritten" in out
    assert "original" not in out


async def test_rewrite_is_rechecked_against_deny_rules(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    (ws / "rewrite.py").write_text(REWRITE.replace("echo rewritten", "rm -rf victim"))
    (ws / "victim").mkdir()
    cfg = hook("PreToolUse", "python3 rewrite.py", "Bash")
    cfg["permissions"] = {"deny": ["Bash(rm:*)"]}
    write_settings(ws, cfg)
    llm.scripts = [reply(calls=bash("echo harmless")), reply("ok")]
    ev = await chat(authed, await session(authed))
    assert "Denied (error 3000)" in results(ev)[0]["output"]
    assert (ws / "victim").exists()


async def test_matcher_selects_hooks(authed: AsyncClient, llm: ScriptedLLM, ws: Path):
    write_settings(
        ws,
        {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Edit|Write", "command": "touch edit_hook"},
                    {"matcher": "Ba.*", "command": "touch bash_hook"},
                ]
            }
        },
    )
    llm.scripts = [reply(calls=bash("true")), reply("ok")]
    await chat(authed, await session(authed))
    assert (ws / "bash_hook").exists()
    assert not (ws / "edit_hook").exists()


async def test_hook_cannot_loosen_a_deny_rule(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    cfg = hook("PreToolUse", 'touch hook_ran; echo \'{"decision":"allow"}\'')
    cfg["permissions"] = {"deny": ["Bash(rm:*)"]}
    write_settings(ws, cfg)
    (ws / "keep").write_text("x")
    llm.scripts = [reply(calls=bash("rm keep")), reply("ok")]
    ev = await chat(authed, await session(authed))
    assert "Denied (error 3000)" in results(ev)[0]["output"]
    assert (ws / "keep").exists()
    assert not (ws / "hook_ran").exists()  # denied before hooks run


async def test_hook_allow_does_not_skip_approval_and_ask_forces_one(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    write_settings(ws, hook("PreToolUse", 'echo \'{"decision":"allow"}\''))
    llm.scripts = [reply(calls=bash("echo hi")), reply("ok")]
    sid = await session(authed, "default")
    task = start_chat(authed, sid)
    await resolve_next(app, authed, "reject")
    assert "approval_required" in (await task).text  # a hook allow is not a pass

    write_settings(ws, hook("PreToolUse", 'echo \'{"decision":"ask"}\''))
    llm.scripts = [reply(calls=bash("echo hi")), reply("ok")]
    task = start_chat(authed, await session(authed, "bypass"))
    await resolve_next(app, authed, "reject")  # bypass would not have asked
    assert "approval_required" in (await task).text


async def test_post_tool_hook_feedback_reaches_the_model(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    write_settings(
        ws, hook("PostToolUse", "cat >/dev/null; echo lint failed >&2; exit 2")
    )
    llm.scripts = [reply(calls=bash("echo hi")), reply("ok")]
    ev = await chat(authed, await session(authed))
    out = results(ev)[0]["output"]
    assert "hi" in out
    assert "[PostToolUse hook] lint failed" in out


async def test_user_prompt_hook_blocks_the_turn(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    write_settings(
        ws, hook("UserPromptSubmit", "cat >/dev/null; echo 'no secrets' >&2; exit 2")
    )
    sid = await session(authed)
    ev = await chat(authed, sid)
    assert ev[0] == {"type": "error", "code": 3006, "message": "no secrets"}
    assert ev[-1] == {"type": "done", "stop_reason": "blocked"}
    assert (await authed.get(f"/v1/sessions/{sid}/messages")).json() == []
    assert llm.requests == []


async def test_stop_hook_sends_the_model_back_once(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    write_settings(
        ws, hook("Stop", "cat >/dev/null; echo 'run the tests first' >&2; exit 2")
    )
    llm.scripts = [reply("done"), reply("ran them")]
    sid = await session(authed)
    ev = await chat(authed, sid)
    assert ev[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert len(llm.requests) == 2
    assert "[Stop hook] run the tests first" in str(llm.requests[1]["messages"])


async def test_session_start_fires_once_and_notification_on_approval(
    authed: AsyncClient, app: FastAPI, llm: ScriptedLLM, ws: Path
):
    write_settings(
        ws,
        {
            "hooks": {
                "SessionStart": [{"command": "echo x >> starts.log"}],
                "Notification": [{"command": "cat > notified.json"}],
            }
        },
    )
    llm.scripts = [reply("a"), reply(calls=bash("true")), reply("b")]
    sid = await session(authed, "default")
    await chat(authed, sid, "one")
    task = start_chat(authed, sid, "two")
    await resolve_next(app, authed, "allow")
    await task
    await until((ws / "notified.json").exists)
    assert (ws / "starts.log").read_text() == "x\n"
    assert (
        json.loads((ws / "notified.json").read_text())["hook_event_name"]
        == "Notification"
    )


async def test_invalid_settings_fail_closed_with_3005(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    (ws / ".dot").mkdir()
    (ws / ".dot" / "settings.json").write_text('{"permissions": {"deny": ["Bash("]}}')
    llm.scripts = [reply(calls=bash("echo hi")), reply("ok")]
    ev = await chat(authed, await session(authed))
    assert any(e["type"] == "error" and e["code"] == 3005 for e in ev)
    assert ev[-1]["stop_reason"] == "error"
