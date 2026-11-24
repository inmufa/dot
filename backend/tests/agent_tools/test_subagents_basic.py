import json
from pathlib import Path

from agent_helpers import (
    RoutedLLM,
    assert_paired,
    chat,
    hook,
    results,
    session,
    tool_names,
    write_settings,
)
from backend.cognition.services.subagents.types import REPORT_MAX_CHARS
from backend.routing.clients.scripted import reply
from fastapi import FastAPI
from helpers import parse_sse, resolve_next, start_chat
from httpx import AsyncClient


def agent(prompt: str, kind: str = "Explore") -> tuple[str, dict]:
    return "Agent", {"description": "d", "prompt": prompt, "subagent_type": kind}


def sub_events(ev: list[dict]) -> list[tuple[str, str]]:
    return [(e["status"], e["detail"]) for e in ev if e["type"] == "subagent"]


async def test_explore_runs_a_fresh_context_and_returns_only_the_report(
    authed: AsyncClient, llm: RoutedLLM, ws: Path
):
    (ws / "a.txt").write_text("hello world\n")
    llm.scripts = [reply(calls=[agent("task-A")]), reply("all done")]
    llm.routes["task-A"] = [
        reply("let me look", [("Read", {"file_path": str(ws / "a.txt")})]),
        reply("a.txt says: hello world"),
    ]
    sid = await session(authed, "default")
    ev = await chat(authed, sid, "please investigate")
    assert_paired(ev)
    assert ev[-1]["stop_reason"] == "end_turn"
    assert sub_events(ev) == [
        ("queued", ""),
        ("started", ""),
        ("step", "Read"),
        ("finished", "ok"),
    ]
    assert next(e for e in ev if e["type"] == "subagent")["label"] == "Explore 1"
    out = results(ev)[0]
    assert out["output"] == "a.txt says: hello world"  # no tokens, no steps
    assert not out["is_error"]
    assert not out["tainted"]
    # The child never saw the parent's conversation and has its own short prompt.
    first = llm.by_key["task-A"][0]
    assert first["messages"][0]["content"].startswith("You are Explore")
    assert [m["role"] for m in first["messages"]] == ["system", "user"]
    assert "please investigate" not in json.dumps(first["messages"])
    assert set(tool_names(first["tools"])) == {
        "Read",
        "Glob",
        "Grep",
        "Skill",
        "WebSearch",
        "WebFetch",
    }
    # The parent transcript holds only the Agent call and its report.
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool", "assistant"]


async def test_explore_and_plan_cannot_mutate(
    authed: AsyncClient, llm: RoutedLLM, ws: Path
):
    target = ws / "evil.txt"
    write = ("Write", {"file_path": str(target), "content": "x"})
    bash = ("Bash", {"command": f"touch {target}"})
    llm.scripts = [
        reply(calls=[agent("task-E"), agent("task-P", "Plan")]),
        reply("ok"),
    ]
    for key in ("task-E", "task-P"):
        llm.routes[key] = [
            reply(calls=[write, bash, ("Agent", {"description": "x", "prompt": "y"})]),
            reply("could not"),
        ]
    ev = await chat(authed, await session(authed, "bypass"))
    assert not target.exists()
    assert [r["output"] for r in results(ev)] == ["could not", "could not"]
    for key in ("task-E", "task-P"):
        tool_msgs = [m for m in llm.by_key[key][1]["messages"] if m["role"] == "tool"]
        assert all(m["content"].startswith("Unknown tool") for m in tool_msgs)
        assert len(tool_msgs) == 3
        assert "Agent" not in tool_names(llm.by_key[key][0]["tools"])


async def test_verifier_runs_bash_through_normal_approval_tagged_with_its_label(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM, ws: Path
):
    llm.scripts = [reply(calls=[agent("task-V", "Verifier")]), reply("verified")]
    llm.routes["task-V"] = [
        reply(
            calls=[
                ("Bash", {"command": "echo tests-pass"}),
                ("Write", {"file_path": str(ws / "w"), "content": "x"}),
            ]
        ),
        reply("PASS: tests-pass"),
    ]
    task = start_chat(authed, await session(authed, "default"), "verify")
    aid = await resolve_next(app, authed, "allow")
    ev = parse_sse((await task).text)
    appr = next(e for e in ev if e["type"] == "approval_required")
    assert appr["approval_id"] == aid
    assert appr["subagent"] == "Verifier 1"
    assert appr["invocation"]["name"] == "Bash"
    assert results(ev)[0]["output"] == "PASS: tests-pass"
    assert not (ws / "w").exists()  # Verifier has no Write
    child = llm.by_key["task-V"][1]["messages"]
    bash_out = next(m for m in child if m["role"] == "tool")
    assert "tests-pass" in bash_out["content"]
    assert set(tool_names(llm.by_key["task-V"][0]["tools"])) == {
        "Read",
        "Glob",
        "Grep",
        "Skill",
        "Bash",
        "BashOutput",
        "KillShell",
    }


async def test_report_is_capped(authed: AsyncClient, llm: RoutedLLM):
    llm.scripts = [reply(calls=[agent("task-L")]), reply("ok")]
    llm.routes["task-L"] = [reply("x" * 9000)]
    out = results(await chat(authed, await session(authed)))[0]["output"]
    assert out.startswith("x" * 100)
    assert len(out) <= REPORT_MAX_CHARS + 40
    assert out.endswith("[report truncated]")


async def test_iteration_cap_and_empty_report(authed: AsyncClient, llm: RoutedLLM):
    llm.scripts = [reply(calls=[agent("task-I")]), reply("ok")]
    llm.routes["task-I"] = [
        reply(f"step {i}", [("Glob", {"pattern": "*.nothing"})]) for i in range(20)
    ]
    out = results(await chat(authed, await session(authed)))[0]["output"]
    assert out.endswith("[stopped at the iteration limit]")
    assert "step 14" in out
    assert "step 15" not in out
    assert len(llm.by_key["task-I"]) == 15


async def test_unknown_type_and_depth_limit(authed: AsyncClient, llm: RoutedLLM):
    gp = "general-purpose"
    llm.scripts = [
        reply(
            calls=[
                (
                    "Agent",
                    {"description": "d", "prompt": "p", "subagent_type": "Wizard"},
                )
            ]
        ),
        reply(calls=[agent("lvl1", gp)]),
        reply("ok"),
    ]
    llm.routes["lvl1"] = [reply(calls=[agent("lvl2", gp)]), reply("r1")]
    llm.routes["lvl2"] = [reply(calls=[agent("lvl3", gp)]), reply("r2")]
    ev = await chat(authed, await session(authed))
    first, second = results(ev)
    assert first["is_error"]
    assert "Unknown subagent_type 'Wizard'" in first["output"]
    assert second["output"] == "r1"
    deepest = [m for m in llm.by_key["lvl2"][1]["messages"] if m["role"] == "tool"]
    assert "depth limit (2)" in deepest[0]["content"]
    assert "lvl3" not in llm.by_key  # a third level never ran
    labels = {e["label"] for e in ev if e["type"] == "subagent"}
    assert labels == {"general-purpose 1", "general-purpose 2"}


async def test_subagent_stop_hook_fires_and_can_add_feedback(
    authed: AsyncClient, llm: RoutedLLM, ws: Path
):
    cmd = 'cat > /dev/null; echo fired >> hook.log; echo "also run lint" >&2; exit 2'
    write_settings(ws, hook("SubagentStop", cmd))
    llm.scripts = [reply(calls=[agent("task-H")]), reply("ok")]
    llm.routes["task-H"] = [reply("report body")]
    out = results(await chat(authed, await session(authed)))[0]["output"]
    assert out == "report body\n[SubagentStop hook] also run lint"
    assert (ws / "hook.log").read_text().strip() == "fired"
