"""Extra views of a shell command (`sudo rm x`, `bash -c ...`, `xargs rm`, ...).

Deny and ask rules match all views; an allow rule only matches the outer command.
"""

import re

from backend.governance.services.analysis.ast_bash_parser import (
    INTERPRETERS,
    SHELLS,
    Command,
    base_name,
    parse,
)

INLINE = "<inline-code>"  # argv[0] of the view made from interpreter code
_WRAPPERS = frozenset(
    [
        "sudo",
        "doas",
        "env",
        "nohup",
        "time",
        "command",
        "exec",
        "xargs",
        "nice",
        "timeout",
        "stdbuf",
        "setsid",
        "ionice",
        "builtin",
        "busybox",
        "unbuffer",
        "watch",
        "strace",
        "flock",
        "chroot",
    ]
)
_GIT_ARG_FLAGS = frozenset({"-c", "-C", "--git-dir", "--work-tree", "--namespace"})
_FIND_EXEC = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
_CODE_FLAGS = frozenset({"-c", "-e", "-E", "-r", "-x", "--eval", "--command"})
_LITERAL = re.compile(r"""["']([^"'\n]{1,300})["']""")
MAX_DEPTH = 4
MAX_VIEWS = 64


def _view(argv: list[str], src: Command) -> Command:
    return Command(argv, " ".join(argv), [], src.dynamic, src.substitution)


def _shell_script(argv: list[str]) -> str | None:
    for i, a in enumerate(argv[1:], start=1):
        if a.startswith("-") and not a.startswith("--") and "c" in a:
            return argv[i + 1] if i + 1 < len(argv) else None
    return None


def _git_rest(argv: list[str]) -> list[str]:
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in _GIT_ARG_FLAGS else 1
    return argv[i:]


def _find_inner(argv: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    i = 0
    while i < len(argv):
        if argv[i] in _FIND_EXEC:
            j = i + 1
            while j < len(argv) and argv[j] not in {";", "+", r"\;"}:
                j += 1
            out.append(argv[i + 1 : j])
            i = j
        i += 1
    return out


def _code_literals(argv: list[str]) -> list[str] | None:
    """String literals inside interpreter `-c`/`-e` code (None: not inline code)."""
    for i, a in enumerate(argv[1:], start=1):
        if a in _CODE_FLAGS and i + 1 < len(argv):
            code = argv[i + 1]
            lits = [*_LITERAL.findall(code), *code.split()]
            return [*lits, *(x.lstrip("<>+ ") for x in lits)]
    return None


def _indirect(cmd: Command, name: str) -> tuple[list[list[str]], list[Command]]:
    """(argv lists to wrap as views, ready-made views) for one command."""
    argv = cmd.argv
    inner: list[list[str]] = [[name, *argv[1:]]] if "/" in argv[0] else []
    ready: list[Command] = []
    if name in _WRAPPERS:
        inner += [
            argv[j:]
            for j in range(1, len(argv))
            if not argv[j].startswith("-") and "=" not in argv[j]
        ]
    elif name == "git":
        inner.append(["git", *_git_rest(argv)])
    elif name == "find":
        inner += _find_inner(argv)
    elif name in SHELLS or name == "eval":
        script = " ".join(argv[1:]) if name == "eval" else _shell_script(argv)
        ready += parse(script).commands if script else []
    elif name.rstrip("0123456789.") in INTERPRETERS | {"lua", "awk", "gawk"}:
        if (lits := _code_literals(argv)) is not None:
            ready.append(_view([INLINE, *lits], cmd))
    return inner, ready


def views(cmd: Command, depth: int = 0) -> list[Command]:
    """Commands that `cmd` runs indirectly (not including `cmd` itself)."""
    if not cmd.argv or depth > MAX_DEPTH:
        return []
    inner, out = _indirect(cmd, base_name(cmd.argv[0]))
    out += [_view(v, cmd) for v in inner if v]
    for v in list(out):
        out.extend(views(v, depth + 1))
    return out[:MAX_VIEWS]
