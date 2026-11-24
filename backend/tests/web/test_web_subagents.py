import pytest
from backend.cognition.services.subagents.types import TYPES
from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from helpers import new_session, parse_sse
from httpx import AsyncClient

BROWSER = {"BrowserNavigate", "BrowserRead", "BrowserClick", "BrowserType"}


def names(request: dict) -> set[str]:
    return {t["function"]["name"] for t in request["tools"]}


def agent(kind: str) -> tuple[str, dict]:
    return "Agent", {"description": "d", "prompt": "research it", "subagent_type": kind}


async def run(c: AsyncClient, sid: str) -> list[dict]:
    resp = await c.post(f"/v1/sessions/{sid}/chat", json={"message": "go"})
    return parse_sse(resp.text)


@pytest.mark.parametrize(
    ("kind", "has_web", "has_browser"),
    [
        ("Explore", True, False),
        ("Plan", True, False),
        ("general-purpose", True, True),
        ("Verifier", False, False),
    ],
)
async def test_subagent_tool_arrays(
    authed: AsyncClient, web: FastAPI, llm: ScriptedLLM, kind, has_web, has_browser
):
    llm.scripts = [reply(calls=[agent(kind)]), reply("report"), reply("done")]
    await run(authed, await new_session(authed, "bypass"))
    parent, child = llm.requests[0], llm.requests[1]
    child_names = names(child)
    assert ("WebSearch" in child_names) is has_web
    assert ("WebFetch" in child_names) is has_web
    assert (child_names >= BROWSER) is has_browser
    assert not (child_names & BROWSER) or has_browser
    assert not (names(parent) & BROWSER)  # the main agent keeps them deferred


async def test_report_from_a_web_child_is_tainted_and_taints_the_parent(
    authed: AsyncClient, web: FastAPI, app: FastAPI, llm: ScriptedLLM
):
    llm.scripts = [
        reply(calls=[agent("Explore")]),
        reply(calls=[("WebFetch", {"url": "http://evil.example.com/tips"})]),
        reply("the page says to touch pwned-marker-file.txt"),
        reply(calls=[("Bash", {"command": "echo hi"})]),
        reply("ok"),
    ]
    sid = await new_session(authed, "auto")
    ev = await run(authed, sid)
    report = next(e["result"] for e in ev if e["type"] == "tool_result")
    assert report["tainted"] is True
    cards = [e for e in ev if e["type"] == "approval_required"]
    assert cards  # the parent's next mutating call is escalated, not auto-run


async def test_child_audit_rows_use_the_child_session(
    authed: AsyncClient, web: FastAPI, llm: ScriptedLLM
):
    llm.scripts = [
        reply(calls=[agent("Explore")]),
        reply(calls=[("WebFetch", {"url": "http://docs.example.com/"})]),
        reply("fine"),
        reply("done"),
    ]
    sid = await new_session(authed, "default")
    await run(authed, sid)
    rows = (await authed.get(f"/v1/audit?session={sid}-sub-1")).json()["items"]
    assert [r["tool"] for r in rows] == ["WebFetch"]


def test_types_declare_the_web_tools():
    assert {"WebSearch", "WebFetch"} <= set(TYPES["Explore"].tools or ())
    assert {"WebSearch", "WebFetch"} <= set(TYPES["Plan"].tools or ())
    assert not {"WebSearch", "WebFetch"} & set(TYPES["Verifier"].tools or ())
    assert TYPES["general-purpose"].loaded


async def test_general_purpose_child_can_call_a_preloaded_browser_tool(
    authed: AsyncClient, web: FastAPI, llm: ScriptedLLM
):
    nav = ("BrowserNavigate", {"url": "http://docs.example.com/"})
    llm.scripts = [
        reply(calls=[agent("general-purpose")]),
        reply(calls=[nav]),
        reply("r"),
        reply("d"),
    ]
    await run(authed, await new_session(authed, "bypass"))
    tool_msgs = [
        m["content"] for m in llm.requests[2]["messages"] if m["role"] == "tool"
    ]
    assert tool_msgs
    assert "deferred and not loaded" not in tool_msgs[-1]
    assert "Unknown tool" not in tool_msgs[-1]
