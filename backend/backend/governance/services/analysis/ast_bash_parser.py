"""Bash command parsing on top of bashlex: simple commands, redirects, pipes."""

import re
from dataclasses import dataclass, field
from typing import Any

import bashlex
import bashlex.errors

SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh", "ash"})
INTERPRETERS = frozenset({"python", "python3", "perl", "ruby", "node", "php"})
_WRAPPERS = frozenset(
    {"sudo", "env", "nohup", "time", "command", "exec", "xargs", "nice", "doas"}
)
_SUBSTITUTIONS = ("commandsubstitution", "processsubstitution")
_PARSE_ERRORS = (
    bashlex.errors.ParsingError,
    NotImplementedError,
    ValueError,
    IndexError,
    AttributeError,
    TypeError,
    KeyError,
)


@dataclass(frozen=True)
class Redirect:
    op: str
    target: str | None


@dataclass
class Command:
    argv: list[str]
    text: str
    redirects: list[Redirect] = field(default_factory=list)
    dynamic: bool = False  # some word has a $var expansion
    substitution: bool = False  # some word has $(...), `...` or <(...)
    piped_in: bool = False  # fed by an earlier stage of a pipeline


@dataclass
class ParsedBash:
    commands: list[Command]
    ok: bool = True  # False: bashlex failed, `commands` is a crude fallback

    @property
    def substitution(self) -> bool:
        return any(c.substitution for c in self.commands)

    @property
    def pipe_to_shell(self) -> bool:
        return any(_runs_stdin_or_substitution(c) for c in self.commands)


def effective_argv(argv: list[str]) -> list[str]:
    """Strip wrappers like `sudo`, `env X=1`, `xargs -n1` from the front."""
    out = list(argv)
    while out and out[0].rsplit("/", 1)[-1] in _WRAPPERS:
        out.pop(0)
        while out and (out[0].startswith("-") or "=" in out[0]):
            out.pop(0)
    return out


def base_name(word: str) -> str:
    return word.rsplit("/", 1)[-1]


def _runs_stdin_or_substitution(cmd: Command) -> bool:
    argv = effective_argv(cmd.argv)
    if not argv:
        return False
    name = base_name(argv[0])
    if name in SHELLS or name in {"source", ".", "eval"}:
        # `sh`, `| bash -s`, `bash <(curl x)`, `eval "$(curl x)"`
        return cmd.piped_in or cmd.substitution
    if name in INTERPRETERS and cmd.piped_in:
        scripts = [a for a in argv[1:] if not a.startswith("-")]
        return not scripts or "-" in argv[1:]
    return False


def _children(node: Any) -> list[Any]:
    kids: list[Any] = []
    for value in vars(node).values():
        if hasattr(value, "kind"):
            kids.append(value)
        elif isinstance(value, list):
            kids.extend(v for v in value if hasattr(v, "kind"))
    return kids


def _word_flags(word: Any) -> tuple[bool, bool]:
    """(has $var expansion, has substitution) for a word node, recursively."""
    dynamic = substitution = False
    stack = list(getattr(word, "parts", []) or [])
    while stack:
        part = stack.pop()
        if part.kind == "parameter":
            dynamic = True
        elif part.kind in _SUBSTITUTIONS:
            substitution = True
        stack.extend(_children(part))
    return dynamic, substitution


def _build_command(node: Any, source: str, *, piped_in: bool) -> Command:
    argv: list[str] = []
    redirects: list[Redirect] = []
    dynamic = substitution = False
    for part in node.parts:
        if part.kind == "redirect":
            target = getattr(part.output, "word", None)
            redirects.append(Redirect(part.type, target))
            if hasattr(part.output, "parts"):
                d, s = _word_flags(part.output)
                dynamic, substitution = dynamic or d, substitution or s
        elif part.kind in ("word", "assignment"):
            if part.kind == "word":
                argv.append(part.word)
            d, s = _word_flags(part)
            dynamic, substitution = dynamic or d, substitution or s
    start, end = node.pos
    return Command(argv, source[start:end], redirects, dynamic, substitution, piped_in)


def _walk(node: Any, source: str, out: list[Command], *, piped_in: bool) -> None:
    if node.kind == "command":
        out.append(_build_command(node, source, piped_in=piped_in))
    if node.kind == "pipeline":
        stage = 0
        for part in node.parts:
            if part.kind == "pipe":
                continue
            _walk(part, source, out, piped_in=stage > 0)
            stage += 1
        return
    # Substitutions live inside words: descend into every node kind.
    for kid in _children(node):
        _walk(kid, source, out, piped_in=False)


def _crude_split(command: str) -> list[Command]:
    """Fallback when bashlex fails: split on control operators, no quoting."""
    pieces = [p.strip() for p in re.split(r"&&|\|\||;|\||\n|&", command)]
    return [
        Command(p.split(), p, substitution="$(" in p or "`" in p) for p in pieces if p
    ]


_QUOTED_HEREDOC = re.compile(r"<<(-?)\s*(['\"])(\w+)\2")


_UNQUOTED_HEREDOC = re.compile(r"<<-?\s*[A-Za-z_]")


def _flag_heredoc_expansion(original: str, commands: list[Command]) -> None:
    """An unquoted heredoc body expands $(...) and backticks like any shell word."""
    if not _UNQUOTED_HEREDOC.search(original):
        return
    if "$(" not in original and "`" not in original:
        return
    for cmd in commands:
        if any(r.op.startswith("<<") for r in cmd.redirects):
            cmd.substitution = True


def parse(command: str) -> ParsedBash:
    # bashlex rejects quoted heredoc delimiters (<<'EOF'); bodies stay opaque.
    original = command
    command = _QUOTED_HEREDOC.sub(r"<<\1\3", command)
    try:
        trees = bashlex.parse(command)
        out: list[Command] = []
        for tree in trees:
            _walk(tree, command, out, piped_in=False)
    except _PARSE_ERRORS:
        return ParsedBash(_crude_split(command), ok=False)
    _flag_heredoc_expansion(original, out)
    return ParsedBash(out)
