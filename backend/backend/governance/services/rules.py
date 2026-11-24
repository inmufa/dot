"""Settings rules: `Tool(specifier)` parsing and matching (deny > allow > ask)."""

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import urlparse

from dot_contracts.permissions import Decision, RuleSpec

from backend.governance.services.analysis.ast_bash_parser import Command, parse
from backend.governance.services.analysis.file_rules import file_rule_hits
from backend.governance.services.analysis.path_globs import RuleContext, path_matches
from backend.governance.services.analysis.shell_views import views

__all__ = ["RuleContext", "RuleHit", "decide_rules", "parse_rule", "path_matches"]

PRECEDENCE = (Decision.DENY, Decision.ALLOW, Decision.ASK)
_RULE = re.compile(r"^\s*([A-Za-z_][\w.\-*]*)\s*(?:\((.*)\))?\s*$", re.DOTALL)
_PATH_KEY = {"Read": "file_path", "Write": "file_path", "Edit": "file_path"}
_FAMILY = {"Write": "Edit", "Grep": "Read", "Glob": "Read"}
_GENERIC_KEYS = ("command", "file_path", "path", "url", "pattern", "name")
_WRITE_OPS = frozenset({">", ">>", ">|", "&>", "&>>"})


@dataclass(frozen=True)
class RuleHit:
    decision: Decision
    rule: str


def parse_rule(decision: Decision, text: str) -> RuleSpec:
    m = _RULE.match(text)
    if m is None:
        msg = f"invalid permission rule: {text!r}"
        raise ValueError(msg)
    spec = m.group(2)
    return RuleSpec(
        decision=decision, tool=m.group(1), specifier=spec.strip() if spec else None
    )


def rule_text(rule: RuleSpec) -> str:
    return rule.tool if rule.specifier is None else f"{rule.tool}({rule.specifier})"


def _applies(rule_tool: str, name: str) -> bool:
    if "*" in rule_tool:
        return fnmatchcase(name, rule_tool)
    return rule_tool == name or _FAMILY.get(name) == rule_tool


# ---- bash --------------------------------------------------------------------


def _norm(text: str) -> str:
    return " ".join(text.split())


def _spec_matches_text(spec: str, text: str) -> bool:
    if spec.endswith(":*"):
        prefix = _norm(spec[:-2])
        return text == prefix or text.startswith(prefix + " ")
    if "*" in spec or "?" in spec:
        return fnmatchcase(text, _norm(spec))
    return text == _norm(spec)


def _allow_safe(cmd: Command) -> bool:
    if cmd.dynamic or cmd.substitution or not cmd.argv:
        return False
    if cmd.text.split()[0] != cmd.argv[0]:  # env-var prefix such as FOO=1 git ...
        return False
    return all(r.op not in _WRITE_OPS or r.target == "/dev/null" for r in cmd.redirects)


def _segment_hits(rule: RuleSpec, cmd: Command, *, parsed_ok: bool) -> bool:
    if rule.specifier is None:
        return True
    forms = {_norm(cmd.text), _norm(" ".join(cmd.argv))}
    if rule.decision == Decision.ALLOW:
        if not (parsed_ok and _allow_safe(cmd)):
            return False
        forms = {_norm(" ".join(cmd.argv))}
    return any(_spec_matches_text(rule.specifier, f) for f in forms)


def _crude_hits(rules: list[RuleSpec], command: str) -> list[RuleSpec]:
    """Unparseable input: a deny/ask prefix anywhere as whole words still counts."""
    text = f" {_norm(command)} "
    out = []
    for r in rules:
        if r.tool == "Bash" and r.specifier and r.decision != Decision.ALLOW:
            prefix = _norm(r.specifier.removesuffix(":*"))
            if f" {prefix} " in text:
                out.append(r)
    return out


def _segment_decisions(
    rules: list[RuleSpec], cmd: Command, ctx: RuleContext, *, ok: bool
) -> tuple[set[Decision], dict[Decision, str]]:
    decisions: set[Decision] = set()
    why: dict[Decision, str] = {}

    def add(decision: Decision, rule: RuleSpec) -> None:
        decisions.add(decision)
        why.setdefault(decision, rule_text(rule))

    bash = [r for r in rules if r.tool == "Bash"]
    for r in bash:
        if _segment_hits(r, cmd, parsed_ok=ok):
            add(r.decision, r)
    for view in [cmd, *views(cmd)]:
        for r in bash:  # indirect runs can only tighten: never allow
            if view is not cmd and r.decision != Decision.ALLOW:
                if _segment_hits(r, view, parsed_ok=ok):
                    add(r.decision, r)
        for decision, r in file_rule_hits(rules, view, ctx):
            add(decision, r)
    return decisions, why


def _bash_decision(
    rules: list[RuleSpec], command: str, ctx: RuleContext
) -> RuleHit | None:
    parsed = parse(command)
    bash_rules = [r for r in rules if r.tool == "Bash"]
    seg: list[Decision | None] = []
    hit_rule: dict[Decision, str] = {}
    for cmd in parsed.commands:
        decisions, why = _segment_decisions(rules, cmd, ctx, ok=parsed.ok)
        for d, text in why.items():
            hit_rule.setdefault(d, text)
        seg.append(next((d for d in PRECEDENCE if d in decisions), None))
    if not parsed.ok:
        for r in _crude_hits(rules, command):
            seg.append(r.decision)
            hit_rule.setdefault(r.decision, rule_text(r))
    if not seg:
        return _whole(bash_rules)
    for decision in (Decision.DENY, Decision.ASK):
        if decision in seg:
            return RuleHit(decision, hit_rule[decision])
    if all(d == Decision.ALLOW for d in seg):
        return RuleHit(Decision.ALLOW, hit_rule[Decision.ALLOW])
    return None


def _whole(bash_rules: list[RuleSpec]) -> RuleHit | None:
    for r in bash_rules:
        if r.specifier is None:
            return RuleHit(r.decision, rule_text(r))
    return None


# ---- other tools -------------------------------------------------------------


def _path_arg(name: str, args: dict[str, Any]) -> str:
    key = _PATH_KEY.get(name, "path")
    return str(args.get(key) or ".")


def _generic_matches(spec: str, args: dict[str, Any]) -> bool:
    if spec.startswith("domain:"):
        host = (urlparse(str(args.get("url", "")).strip()).hostname or "").lower()
        host = host.rstrip(".")  # `example.com.` is the same host
        want = spec[7:].strip().lower().lstrip(".")
        return host == want or host.endswith("." + want)
    pattern = spec.replace(":*", "*")
    return any(fnmatchcase(str(args[k]), pattern) for k in _GENERIC_KEYS if k in args)


def _matches(rule: RuleSpec, name: str, args: dict[str, Any], ctx: RuleContext) -> bool:
    if rule.specifier is None:
        return True
    if rule.tool in ("Read", "Edit", "Write"):
        return path_matches(rule.specifier, _path_arg(name, args), ctx)
    return _generic_matches(rule.specifier, args)


def decide_rules(
    rules: list[RuleSpec], name: str, args: dict[str, Any], ctx: RuleContext
) -> RuleHit | None:
    """Highest-precedence matching rule (deny > allow > ask), or None."""
    if name == "Bash":
        return _bash_decision(rules, str(args.get("command", "")), ctx)
    hits: dict[Decision, str] = {}
    for rule in rules:
        if _applies(rule.tool, name) and _matches(rule, name, args, ctx):
            hits.setdefault(rule.decision, rule_text(rule))
    for decision in PRECEDENCE:
        if decision in hits:
            return RuleHit(decision, hits[decision])
    return None
