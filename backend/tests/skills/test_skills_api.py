import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from backend.cognition.services.engine.prompt_compiler import PromptCompiler
from backend.cognition.services.skill_loader import SkillRegistry
from backend.cognition.services.tools.executor import default_registry
from backend.cognition.services.tools.registry import ToolContext
from backend.cognition.services.tools.skill_tool import make_skill_tool
from backend.routing.clients.scripted import ScriptedLLM, reply
from fastapi import FastAPI
from helpers import new_session, parse_sse, start_chat
from httpx import AsyncClient


def _skill(
    root: Path, name: str, extra: str = "", body: str = "Step 1. $ARGUMENTS\n"
) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: d {name}\n{extra}\n---\n{body}"
    )
    return d


@pytest.fixture
def reg(tmp_path: Path) -> SkillRegistry:
    root = tmp_path / "sk"
    d = _skill(root, "alpha")
    (d / "ref.md").write_text("reference\n")
    (tmp_path / "outside.txt").write_text("secret")
    (d / "evil").symlink_to(tmp_path / "outside.txt")
    _skill(root, "nope", "requires: {binaries: [zzz-nope]}")
    _skill(root, "usr", "disable-model-invocation: true")
    return SkillRegistry(root)


async def call(reg: SkillRegistry, **args):
    ctx = ToolContext(session_id="s", sandbox=None, workspace="/w")  # type: ignore[arg-type]
    return await make_skill_tool(reg).run(ctx, args)


async def test_skill_tool_body_dir_and_files(reg: SkillRegistry):
    r = await call(reg, name="alpha", args="go now")
    assert not r.is_error
    assert "Step 1. go now" in r.output
    assert "name: alpha" not in r.output
    assert f"Skill directory: {reg.get('alpha').path}" in r.output
    assert "- ref.md" in r.output


async def test_skill_tool_file_and_escapes(reg: SkillRegistry):
    ok = await call(reg, name="alpha", file="ref.md")
    assert "reference" in ok.output
    for bad in ("../outside.txt", "evil", "/etc/passwd", "../../etc/passwd"):
        r = await call(reg, name="alpha", file=bad)
        assert r.is_error, bad
        assert "secret" not in r.output


async def test_skill_tool_errors(reg: SkillRegistry):
    assert "Unknown skill" in (await call(reg, name="zzz")).output
    r = await call(reg, name="nope")
    assert r.is_error
    assert "unavailable" in r.output
    assert "zzz-nope" in r.output
    r = await call(reg, name="usr")
    assert r.is_error
    assert "/usr" in r.output


def test_skill_tool_is_not_mutating(reg: SkillRegistry):
    d = make_skill_tool(reg).definition
    assert d.mutating is False


def test_prefix_is_byte_stable(reg: SkillRegistry, tmp_path: Path):
    other = SkillRegistry(tmp_path / "empty")
    p1 = PromptCompiler(default_registry(reg).definitions())
    p2 = PromptCompiler(default_registry(other).definitions())
    assert p1.prefix == p2.prefix
    assert p1.system_prompt == p2.system_prompt
    before = p1.system_prompt
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with_hint = p1.reminder("plan", "/w", now, reg.hint("anything"))
    plain = p1.reminder("plan", "/w", now)
    assert plain in with_hint
    assert p1.system_prompt == before
    assert "alpha" not in p1.system_prompt


async def test_list_and_get_endpoints(authed: AsyncClient):
    r = await authed.get("/v1/skills")
    assert r.status_code == 200
    rows = {s["name"]: s for s in r.json()}
    assert rows["code-review"]["source"] == "bundled"
    assert rows["code-review"]["available"] is True
    assert rows["atlassian-mcp"]["available"] is False
    assert "MCP" in rows["atlassian-mcp"]["reason"]
    d = (await authed.get("/v1/skills/init")).json()
    assert d["body"].startswith("# Init")
    assert "name: init" not in d["body"]
    assert (await authed.get("/v1/skills/nope-nope")).status_code == 404


async def test_skills_require_token(client: AsyncClient):
    assert (await client.get("/v1/skills")).status_code == 401


async def test_matching_skill_goes_in_frozen_reminder(
    authed: AsyncClient, llm: ScriptedLLM
):
    llm.scripts = [reply("ok")]
    sid = await new_session(authed)
    resp = await start_chat(authed, sid, "review my pull request for bugs")
    assert parse_sse(resp.text)[-1]["stop_reason"] == "end_turn"
    content = llm.requests[0]["messages"][1]["content"]
    assert "Skills that may apply:" in content
    assert "code-review - " in content
    assert llm.requests[0]["messages"][0]["content"].count("code-review") <= 1
    stored = (await authed.get(f"/v1/sessions/{sid}/messages")).json()[0]["content"]
    assert "Skills that may apply" not in stored


async def test_slash_invocation_expands(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply("done")]
    sid = await new_session(authed)
    await start_chat(authed, sid, "/init for this repo")
    sent = llm.requests[0]["messages"][1]["content"]
    assert sent.startswith("/init for this repo")
    assert '<skill name="init">' in sent
    assert "Arguments: for this repo" in sent
    msgs = (await authed.get(f"/v1/sessions/{sid}/messages")).json()
    assert '<skill name="init">' in msgs[0]["content"]
    sessions = (await authed.get("/v1/sessions")).json()
    assert sessions[0]["title"].startswith("/init")


async def test_unknown_slash_passes_through(authed: AsyncClient, llm: ScriptedLLM):
    llm.scripts = [reply("hm")]
    sid = await new_session(authed)
    await start_chat(authed, sid, "/definitely-not-a-skill x")
    sent = llm.requests[0]["messages"][1]["content"]
    assert sent.startswith("/definitely-not-a-skill x")
    assert "<skill" not in sent


async def test_skill_tool_over_the_wire(
    authed: AsyncClient, llm: ScriptedLLM, app: FastAPI
):
    assert "Skill" in [
        t["function"]["name"] for t in app.state.react._registry.openai_schemas()
    ]
    llm.scripts = [
        reply(calls=[("Skill", {"name": "loop", "args": "5s check"})]),
        reply("ok"),
    ]
    sid = await new_session(authed)
    ev = parse_sse((await start_chat(authed, sid, "hi")).text)
    out = next(e for e in ev if e["type"] == "tool_result")["result"]
    assert not out["is_error"]
    assert "# Skill: loop" in out["output"]
    assert "Arguments: 5s check" in out["output"]
    assert json.dumps(ev)  # stream stays valid
