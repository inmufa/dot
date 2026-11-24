import itertools

import pytest
from backend.cognition.services.tools.executor import default_registry
from backend.governance.services.permission_engine import PermissionEngine, always_key
from backend.governance.services.rules import RuleContext, parse_rule
from dot_contracts.permissions import Decision, PermissionMode
from dot_contracts.tools import ToolDefinition

A, ASK, D = Decision.ALLOW, Decision.ASK, Decision.DENY
MODES = [m.value for m in PermissionMode]
REG = default_registry()
TOOLS = {
    "Read": ({"file_path": "a.txt"}, False),
    "Glob": ({"pattern": "*"}, False),
    "Write": ({"file_path": "a.txt", "content": "x"}, True),
    "Edit": ({"file_path": "a.txt", "old_string": "a", "new_string": "b"}, True),
    "Bash": ({"command": "make build"}, True),
    "Shiny": ({}, True),  # unknown tool: fails closed
}
RULESETS = [
    (),
    ("allow",),
    ("ask",),
    ("deny",),
    ("allow", "ask"),
    ("allow", "deny"),
    ("ask", "deny"),
    ("allow", "ask", "deny"),
]


def tool_def(name: str) -> ToolDefinition:
    t = REG.get(name)
    if t:
        return t.definition
    return ToolDefinition(name=name, description="d", input_schema={})


def expected(mode: str, name: str, ruleset: tuple[str, ...]) -> Decision:
    mutating = TOOLS[name][1]
    if mutating and mode == "plan":
        return D  # plan wins over every rule
    for key, decision in (("deny", D), ("allow", A), ("ask", ASK)):
        if key in ruleset:
            return decision
    if not mutating:
        return A
    if mode == "bypass" or (mode == "acceptEdits" and name in {"Write", "Edit"}):
        return A
    return ASK


@pytest.mark.parametrize(
    ("mode", "name", "ruleset"),
    list(itertools.product(MODES, TOOLS, RULESETS)),
)
def test_full_matrix(mode, name, ruleset):
    rules = [
        parse_rule(Decision(k), name) for k in ruleset
    ]  # bare Tool rule: matches every call
    args = TOOLS[name][0]
    got = PermissionEngine(rules, RuleContext(workspace="/w")).decide(
        mode, tool_def(name), args
    )
    assert got.decision == expected(mode, name, ruleset), (mode, name, ruleset)


def test_rule_sources_are_reported():
    eng = PermissionEngine([parse_rule(D, "Bash(rm:*)")], RuleContext("/w"))
    bash = tool_def("Bash")
    assert eng.decide("default", bash, {"command": "rm x"}).source == "rule"
    assert eng.decide("default", bash, {"command": "ls"}).source == "mode"
    assert eng.decide("plan", bash, {"command": "ls"}).source == "mode"


def test_auto_mode_defers_to_classifier_only_for_unruled_mutating_calls():
    eng = PermissionEngine([parse_rule(A, "Bash(make:*)")], RuleContext("/w"))
    bash = tool_def("Bash")
    assert eng.decide("auto", bash, {"command": "make x"}).decision == A
    other = eng.decide("auto", bash, {"command": "ls"})
    assert (other.decision, other.classify) == (ASK, True)
    assert eng.decide("default", bash, {"command": "ls"}).classify is False
    assert eng.decide("auto", tool_def("Read"), {}).decision == A


def test_session_always_does_not_beat_deny_or_plan_but_beats_ask():
    bash = tool_def("Bash")
    args = {"command": "make"}
    allowed = {always_key("Bash", args)}
    ask = PermissionEngine([parse_rule(ASK, "Bash")], RuleContext("/w"))
    assert ask.decide("default", bash, args, allowed).decision == A
    deny = PermissionEngine([parse_rule(D, "Bash")], RuleContext("/w"))
    assert deny.decide("default", bash, args, allowed).decision == D
    assert PermissionEngine().decide("plan", bash, args, allowed).decision == D


def test_rules_can_be_a_live_callable():
    box: list = []
    eng = PermissionEngine(lambda: box, RuleContext("/w"))
    bash = tool_def("Bash")
    assert eng.decide("bypass", bash, {"command": "x"}).decision == A
    box.append(parse_rule(D, "Bash"))
    assert eng.decide("bypass", bash, {"command": "x"}).decision == D
