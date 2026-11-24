"""Read/Edit deny rules applied to shell commands.

Any argument of a non-trivial command may be read (`cut`, `sort`, `git add`,
`python script.py .env`), so Read rules check every path-like argument except
for commands that only name files (`ls`, `rm`, `echo`). Glob and brace words are
compared against concrete samples of the denied patterns. Lexical only: the
sandbox, not these rules, is the real boundary.
"""

import re
from fnmatch import fnmatchcase

from dot_contracts.permissions import Decision, RuleSpec

from backend.governance.services.analysis.ast_bash_parser import Command, base_name
from backend.governance.services.analysis.path_globs import (
    RuleContext,
    normalise,
    path_matches,
)
from backend.governance.services.analysis.shell_views import INLINE

_NAMES_ONLY = frozenset(
    [
        "echo",
        "printf",
        "ls",
        "rm",
        "rmdir",
        "mkdir",
        "touch",
        "chmod",
        "chown",
        "test",
        "[",
        "true",
        "false",
        "cd",
        "pwd",
        "which",
        "type",
        "stat",
        "unlink",
        "sleep",
        "export",
        "set",
        "unset",
        "kill",
        "exit",
    ]
)
_READERS = frozenset(
    [
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "grep",
        "rg",
        "sed",
        "awk",
        "xxd",
        "strings",
        "base64",
        "od",
        "nl",
        "tac",
        "cut",
        "sort",
        "uniq",
        "diff",
        "cmp",
        "paste",
        "column",
        "fold",
        "hexdump",
        "rev",
        "jq",
        "tar",
        "zip",
        "gzip",
        "zcat",
        "file",
    ]
)
_WRITERS = frozenset(
    [
        "rm",
        "tee",
        "touch",
        "mv",
        "cp",
        "mkdir",
        "chmod",
        "truncate",
        "ln",
        "rmdir",
        "shred",
        "install",
        "dd",
        "rsync",
        "patch",
        "unzip",
        "tar",
        "chown",
    ]
) | {INLINE}
_WRITE_OPS = frozenset({">", ">>", ">|", "&>", "&>>"})
_GLOB = re.compile(r"[*?\[]")
_MAX_BRACE = 64
_BRACE = re.compile(r"\{([^{}]*)\}")


def _braces(word: str) -> list[str]:
    out, queue = [], [word]
    while queue and len(out) < _MAX_BRACE:
        w = queue.pop()
        m = _BRACE.search(w)
        if not m or ("," not in m[1] and ".." not in m[1]):
            out.append(w)
            continue
        parts = m[1].split(",") if "," in m[1] else m[1].split("..")
        queue += [w[: m.start()] + p + w[m.end() :] for p in parts]
    return out


def _candidates(arg: str) -> list[str]:
    """Path-like readings of one argument (`--f=x`, `dd if=x`, `rev:path`)."""
    out = [] if arg.startswith("-") and "=" not in arg else [arg]
    if "=" in arg:
        out.append(arg.split("=", 1)[1])
    if ":" in arg and not arg.startswith("-"):
        out.append(arg.rsplit(":", 1)[1])
    out = [
        c.removeprefix("file://").replace("${HOME}", "~").replace("$HOME", "~")
        for c in out
    ]
    return [b for c in out if c for b in _braces(c)]


def _samples(spec: str, ctx: RuleContext) -> list[str]:
    """Concrete paths a deny pattern would match, for glob-vs-glob comparison."""
    s = spec.strip().removeprefix("./")
    if s.startswith("~"):
        s = ctx.home + s[1:]
    s = s.replace("**/", "").replace("/**", "/x").replace("**", "x").replace("*", "x")
    ws = ctx.workspace.rstrip("/")
    return [s] if s.startswith("/") else [f"{ws}/{s}", f"{ws}/x/{s}"]


def _comp_match(arg: str, sample: str) -> bool:
    a, b = arg.split("/"), sample.split("/")
    if len(a) != len(b):
        return False
    for x, y in zip(a, b, strict=True):
        if x and set(x) <= {"*"}:
            return False  # a bare `*` is too broad to read as "the denied file"
        if y.startswith(".") and not x.startswith("."):
            return False  # a leading wildcard never expands to a dotfile
        if not fnmatchcase(y, x):
            return False
    return True


def _hit(rule: RuleSpec, cand: str, ctx: RuleContext) -> bool:
    spec = rule.specifier or ""
    if not _GLOB.search(cand):
        return path_matches(spec, cand, ctx)
    arg = normalise(cand, ctx)
    return any(_comp_match(arg, s) for s in _samples(spec, ctx))


def _args(cmd: Command, *, write: bool) -> list[str]:
    name = base_name(cmd.argv[0]) if cmd.argv else ""
    ok = name in _WRITERS if write else name not in _NAMES_ONLY
    if name == "sed" and write:
        ok = any(a.startswith("-i") or a == "--in-place" for a in cmd.argv)
    args = [c for a in cmd.argv[1:] if ok for c in _candidates(a)] if ok else []
    if write:
        for r in cmd.redirects:
            if r.op in _WRITE_OPS and r.target:
                args += [*_candidates(r.target), r.target]
    else:
        args += [r.target for r in cmd.redirects if r.op == "<" and r.target]
    return args


def file_rule_hits(
    rules: list[RuleSpec], cmd: Command, ctx: RuleContext
) -> list[tuple[Decision, RuleSpec]]:
    """Deny hits (and ASK for dynamic reader arguments) of Read/Edit rules."""
    reads = [r for r in rules if r.decision == Decision.DENY and r.tool in {"Read"}]
    edits = [
        r for r in rules if r.decision == Decision.DENY and r.tool in {"Edit", "Write"}
    ]
    out: list[tuple[Decision, RuleSpec]] = []
    for group, write in ((reads, False), (edits, True)):
        args = _args(cmd, write=write) if group else []
        out += [
            (Decision.DENY, r)
            for r in group
            if r.specifier and any(_hit(r, a, ctx) for a in args)
        ]
    name = base_name(cmd.argv[0]) if cmd.argv else ""
    if reads and name in _READERS and (cmd.dynamic or cmd.substitution):
        out.append((Decision.ASK, reads[0]))  # the path is unknown until run time
    return out
