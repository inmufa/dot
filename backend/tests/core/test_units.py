from datetime import UTC, datetime

from backend.cognition.services.engine.prompt_compiler import (
    CACHE_BOUNDARY,
    PromptCompiler,
)
from backend.cognition.services.tools.executor import (
    default_registry,
    summarize,
    validate,
)
from backend.governance.services.approvals import ApprovalRegistry
from backend.governance.services.permission_engine import PermissionEngine
from dot_contracts.permissions import Decision, RuleSpec


def test_prefix_is_byte_stable_across_turns_and_modes():
    defs = default_registry().definitions()
    a, b = PromptCompiler(defs), PromptCompiler(defs)
    assert a.prefix.encode() == b.prefix.encode()
    assert a.system_prompt.endswith(f"{CACHE_BOUNDARY}\n")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    r1 = a.reminder("plan", "/ws", now)
    r2 = a.reminder("acceptEdits", "/other", now)
    assert r1 != r2
    for word in ("bypass", "acceptEdits", "/ws", "/other", "2026-01-01"):
        assert word not in a.prefix
    assert a.system_prompt == b.system_prompt  # unchanged after reminders built


def test_summarize_head_tail():
    text = "H" * 2000 + "M" * 5000 + "T" * 2000
    out = summarize(text, 3000)
    assert len(out) < 3200
    assert out.startswith("H")
    assert out.endswith("T")
    assert "omitted" in out
    assert summarize("short", 3000) == "short"


def test_validate_required_and_types():
    tool = default_registry().get("Read")
    assert tool
    assert validate(tool, {}) == "missing required argument 'file_path'"
    assert validate(tool, {"file_path": 3})
    assert validate(tool, {"file_path": "/a", "limit": 5}) is None


def _tool(name):
    tool = default_registry().get(name)
    assert tool
    return tool.definition


def test_permission_modes():
    eng = PermissionEngine()
    read, write, bash = _tool("Read"), _tool("Write"), _tool("Bash")
    assert eng.decide("plan", read, {}).decision == Decision.ALLOW
    assert eng.decide("plan", write, {}).decision == Decision.DENY
    assert eng.decide("default", read, {}).decision == Decision.ALLOW
    assert eng.decide("default", write, {}).decision == Decision.ASK
    assert eng.decide("auto", write, {}).decision == Decision.ASK
    assert eng.decide("acceptEdits", write, {}).decision == Decision.ALLOW
    assert eng.decide("acceptEdits", bash, {}).decision == Decision.ASK
    assert eng.decide("bypass", bash, {}).decision == Decision.ALLOW
    assert eng.decide("default", bash, {"command": "ls"}, {"Bash:ls"}).decision == (
        Decision.ALLOW
    )


def test_rule_precedence_deny_over_allow_over_ask():
    bash = _tool("Bash")
    rules = [
        RuleSpec(decision=Decision.ALLOW, tool="Bash", specifier="git:*"),
        RuleSpec(decision=Decision.ASK, tool="Bash"),
        RuleSpec(decision=Decision.DENY, tool="Bash", specifier="git push*"),
    ]
    eng = PermissionEngine(rules)
    assert eng.decide("bypass", bash, {"command": "git push"}).decision == Decision.DENY
    assert eng.decide("default", bash, {"command": "git status"}).decision == (
        Decision.ALLOW
    )
    assert eng.decide("default", bash, {"command": "ls"}).decision == Decision.ASK
    # bypass skips ask rules (deny still wins)
    assert eng.decide("bypass", bash, {"command": "ls"}).decision == Decision.ALLOW


async def test_approval_registry_roundtrip():
    reg = ApprovalRegistry()
    aid = reg.create("S1")
    reg.resolve(aid, "allow")
    assert await reg.wait(aid, 1) == "allow"
