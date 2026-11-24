import json

from agent_helpers import (
    RoutedLLM,
    assert_paired,
    chat,
    deferred_tool,
    results,
    session,
    tool_names,
)
from backend.cognition.services.engine.prompt_compiler import PromptCompiler
from backend.cognition.services.tools.agent.tool_search import rank
from backend.routing.clients.scripted import reply
from fastapi import FastAPI
from httpx import AsyncClient

DEFS = {
    "NotebookEdit": "Edit cells of a Jupyter notebook",
    "CronCreate": "Schedule a recurring job with a cron expression",
    "mcp__github__create_issue": "Create an issue in a GitHub repository",
    "BrowserScreenshot": "Take a screenshot of the current browser page",
}


def _register(app: FastAPI, seen: list | None = None) -> None:
    for name, desc in DEFS.items():
        app.state.agent.registry.add(deferred_tool(name, desc, seen))


def test_bm25_ranking_prefers_name_and_description_matches():
    tools = [deferred_tool(n, d).definition for n, d in DEFS.items()]
    assert rank(tools, "jupyter notebook cells", 3)[0] == "NotebookEdit"
    assert rank(tools, "github issue", 3)[0] == "mcp__github__create_issue"
    assert rank(tools, "schedule cron", 3)[0] == "CronCreate"
    assert rank(tools, "screenshot", 5) == ["BrowserScreenshot"]
    assert rank(tools, "kubernetes", 5) == []
    assert len(rank(tools, "create edit page", 2)) <= 2


async def test_prefix_excludes_deferred_and_reminder_lists_them(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    before = app.state.react._compiler.prefix
    _register(app)
    assert PromptCompiler(app.state.agent.registry.core_definitions()).prefix == before
    assert "NotebookEdit" not in before
    assert "ToolSearch" in before
    llm.scripts = [reply("ok")]
    sid = await session(authed)
    await chat(authed, sid)
    req = llm.requests[0]
    assert not set(DEFS) & set(tool_names(req["tools"]))
    user = req["messages"][1]["content"]
    assert "Deferred tools available via ToolSearch: " in user
    assert all(n in user for n in DEFS)


async def test_select_activates_and_appends_to_tools_array_end(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    seen: list = []
    _register(app, seen)
    llm.scripts = [
        reply(calls=[("ToolSearch", {"query": "select:NotebookEdit,Nope"})]),
        reply(calls=[("NotebookEdit", {"x": "cell1"})]),
        reply("done"),
    ]
    sid = await session(authed)
    ev = await chat(authed, sid)
    assert_paired(ev)
    r = results(ev)
    assert "Activated 1 tool(s)" in r[0]["output"]
    assert '"name": "NotebookEdit"' in r[0]["output"]
    assert "Not found: Nope" in r[0]["output"]
    assert r[1]["output"].startswith("NotebookEdit ran")
    assert not r[1]["is_error"]
    assert seen == [{"x": "cell1"}]
    t1, t2, t3 = (tool_names(q["tools"]) for q in llm.requests)
    assert "NotebookEdit" not in t1
    assert t2 == [*t1, "NotebookEdit"]  # append only, at the very end
    assert t3 == t2


async def test_cache_prefix_stays_identical_across_activation(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    _register(app)
    llm.scripts = [
        reply("looking", [("ToolSearch", {"query": "cron schedule recurring"})]),
        reply("done"),
    ]
    sid = await session(authed)
    await chat(authed, sid)
    a, b = llm.requests
    assert a["messages"][0] == b["messages"][0]  # system prompt byte-identical
    assert b["tools"][: len(a["tools"])] == a["tools"]  # every old schema unchanged
    assert b["messages"][: len(a["messages"])] == a["messages"]  # history only grows
    assert len(b["tools"]) == len(a["tools"]) + 1
    # What a llama chat template renders first: system text, then the tools block.
    # Everything up to the appended schema is the same bytes before and after.
    head_a = json.dumps([a["messages"][0], a["tools"]])[:-1]
    head_b = json.dumps([b["messages"][0], b["tools"][: len(a["tools"])]])[:-1]
    assert head_a == head_b


async def test_deferred_tool_not_callable_before_activation(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    seen: list = []
    _register(app, seen)
    llm.scripts = [reply(calls=[("CronCreate", {"x": "1"})]), reply("ok")]
    sid = await session(authed)
    ev = await chat(authed, sid)
    out = results(ev)[0]
    assert out["is_error"]
    assert "select:CronCreate" in out["output"]
    assert seen == []


async def test_keyword_search_activates_top_matches_and_unknown_select_errors(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    _register(app)
    llm.scripts = [
        reply(calls=[("ToolSearch", {"query": "github issue", "max_results": 1})]),
        reply(calls=[("ToolSearch", {"query": "select:Missing"})]),
        reply("ok"),
    ]
    sid = await session(authed)
    ev = await chat(authed, sid)
    first, second = results(ev)
    assert "mcp__github__create_issue" in first["output"]
    assert "NotebookEdit" not in first["output"]
    assert second["is_error"]
    assert "Not found: Missing" in second["output"]
    assert tool_names(llm.requests[-1]["tools"])[-1] == "mcp__github__create_issue"


def _lcp(x: str, y: str) -> int:
    n = 0
    for p, q in zip(x, y, strict=False):
        if p != q:
            break
        n += 1
    return n


async def test_activation_invalidates_only_the_history_part_of_the_cache(
    authed: AsyncClient, app: FastAPI, llm: RoutedLLM
):
    """llama renders `tools` before the messages, so growing the array re-prefills
    the history once. The system prompt and the old schemas stay cached."""
    _register(app)
    llm.scripts = [
        reply(calls=[("ToolSearch", {"query": "select:CronCreate"})]),
        reply("x"),
    ]
    await chat(authed, await session(authed))
    a, b = llm.requests

    def wire(r: dict) -> str:
        return json.dumps(
            {"s": r["messages"][0], "t": r["tools"], "m": r["messages"][1:]}
        )

    shared = _lcp(wire(a), wire(b))
    static = len(json.dumps({"s": a["messages"][0], "t": a["tools"]})) - 2
    assert static - 2 <= shared < len(wire(a))
