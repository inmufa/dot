"""Auto-mode classifier. Stage A: deterministic command analysis. Stage B: taint."""

import os
import re
from pathlib import Path
from typing import Any

from dot_contracts.permissions import ClassifierVerdict, Decision

from backend.governance.services.analysis.ast_bash_parser import (
    SHELLS,
    Command,
    ParsedBash,
    base_name,
    effective_argv,
    parse,
)
from backend.governance.services.analysis.classifier_extra import check_indirect
from backend.governance.services.analysis.classifier_patterns import (
    NETWORK_CMDS,
    SHELL_FILE_WRITERS,
    SYSTEM_DIRS,
    WRITE_OPS,
    Findings,
    check_network,
    is_cred,
)
from backend.governance.services.taint import TaintStore

MAX_NEST = 3


class AutoClassifier:
    def __init__(
        self, taint: TaintStore, workspace: str, home: str | None = None
    ) -> None:
        self.taint = taint
        self.workspace = os.path.realpath(workspace)
        self.home = home or str(Path.home())

    # ---- paths ----
    def _resolve(self, word: str, cwd: str) -> str | None:
        """Absolute path for a word, or None when it depends on an unknown variable."""
        w = word.replace("${HOME}", "~").replace("$HOME", "~")
        if w == "~" or w.startswith("~/"):
            w = self.home + w[1:]
        if "$" in w or "`" in w:
            return None
        cut = re.search(r"[*?\[]", w)
        if cut:  # judge a glob by its literal directory prefix
            w = (
                w[: cut.start()].rpartition("/")[0] + "/"
                if "/" in w[: cut.start()]
                else ""
            )
        base = w if w.startswith("/") else f"{cwd}/{w}"
        return os.path.normpath(base)

    def _outside(self, path: str) -> bool:
        return not (path == self.workspace or path.startswith(self.workspace + "/"))

    # ---- stage A, per command ----
    @staticmethod
    def _write_targets(cmd: Command, argv: list[str]) -> list[str]:
        name = base_name(argv[0]) if argv else ""
        targets = [r.target for r in cmd.redirects if r.op in WRITE_OPS and r.target]
        args = [a for a in argv[1:] if not a.startswith("-")]
        if name in SHELL_FILE_WRITERS:
            if name in {"cp", "ln", "install"}:
                args = args[-1:]
            targets += [a.split("=", 1)[1] if a.startswith("of=") else a for a in args]
        elif name == "sed" and any(
            a.startswith("-i") or a == "--in-place" for a in argv
        ):
            targets += args[1:]
        return targets

    def _check_paths(self, cmd: Command, cwd: str, f: Findings) -> str:
        argv = effective_argv(cmd.argv)
        targets = self._write_targets(cmd, argv)
        for t in targets:
            if t == "/dev/null":
                continue
            resolved = self._resolve(t, cwd)
            if resolved is None:
                f.add(Decision.ASK, "write target depends on a shell variable")
            elif self._outside(resolved):
                f.add(Decision.ASK, f"writes outside the workspace ({t})")
            elif ".dot" in resolved[len(self.workspace) :].split("/")[:2]:
                f.add(Decision.ASK, "writes to the protected .dot directory")
        name = base_name(argv[0]) if argv else ""
        if name == "cd" and len(argv) > 1:
            resolved = self._resolve(argv[1], cwd)
            if resolved is None or self._outside(resolved):
                f.add(Decision.ASK, "changes directory outside the workspace")
                return cwd
            return resolved
        return cwd

    def _check_rm(self, argv: list[str], cwd: str, f: Findings) -> None:
        flags = [a for a in argv[1:] if a.startswith("-")]
        recursive = any(
            a in {"--recursive", "--no-preserve-root"}
            or (not a.startswith("--") and ("r" in a or "R" in a))
            for a in flags
        )
        if not recursive:
            return
        for t in (a for a in argv[1:] if not a.startswith("-")):
            resolved = self._resolve(t, cwd)
            if resolved is None:
                f.add(Decision.ASK, "rm -r target depends on a shell variable")
            elif (
                resolved in SYSTEM_DIRS
                or resolved == self.home
                or self.home.startswith(resolved + "/")
            ):
                f.add(Decision.DENY, f"rm -r on a root-like or home path ({t})")
            elif resolved == self.workspace or resolved.endswith("/.git"):
                f.add(Decision.ASK, f"rm -r on the workspace root or .git ({t})")

    def _check_exec(self, cmd: Command, argv: list[str], f: Findings) -> None:
        name = base_name(argv[0])
        if name in {"eval", "sudo", "doas", "su"} or cmd.argv[0] in {"sudo", "doas"}:
            f.add(Decision.ASK, f"{base_name(cmd.argv[0])} runs with extra reach")
        if name in SHELLS and "-c" in argv[1:-1]:
            inner = self.analyse_bash(argv[argv.index("-c") + 1])
            if inner.decision != Decision.ALLOW:
                f.add(inner.decision, f"inside {name} -c: {inner.reason}")

    def _check_command(
        self, cmd: Command, cwd: str, f: Findings, depth: int = 0
    ) -> str:
        argv = effective_argv(cmd.argv)
        if not argv:
            if cmd.dynamic or cmd.substitution:
                f.add(Decision.ASK, "command name comes from an expansion")
            return cwd
        name = base_name(argv[0])
        if "$" in argv[0]:
            f.add(Decision.ASK, "command name comes from an expansion")
        if name == "rm":
            self._check_rm(argv, cwd, f)
        self._check_exec(cmd, argv, f)
        self._scan_words(cmd, argv, f)
        check_network(cmd, argv, f)
        if name == "ln":
            self._check_ln(argv, cwd, f)
        for inner in check_indirect(cmd, f):
            if depth < MAX_NEST:
                self._check_command(inner, cwd, f, depth + 1)
        return self._check_paths(cmd, cwd, f)

    @staticmethod
    def _scan_words(cmd: Command, argv: list[str], f: Findings) -> None:
        for word in [*argv[1:], *(r.target or "" for r in cmd.redirects)]:
            if "/dev/tcp/" in word or "/dev/udp/" in word:
                f.add(Decision.DENY, "raw socket via /dev/tcp")
            if word and not word.startswith("-") and is_cred(word):
                f.add(Decision.ASK, f"touches a credential path ({word})")

    def _check_ln(self, argv: list[str], cwd: str, f: Findings) -> None:
        """A link made inside the workspace must not point out of it."""
        for t in (a for a in argv[1:] if not a.startswith("-")):
            resolved = self._resolve(t, cwd)
            if resolved is None or self._outside(resolved):
                f.add(Decision.ASK, f"ln involves a path outside the workspace ({t})")

    def analyse_bash(self, command: str) -> ClassifierVerdict:
        parsed: ParsedBash = parse(command)
        f = Findings()
        if not parsed.ok:
            f.add(Decision.ASK, "command could not be parsed")
        if parsed.substitution:
            f.add(Decision.ASK, "command substitution")
        if parsed.pipe_to_shell:
            f.add(Decision.DENY, "pipes or substitutes remote content into a shell")
        cwd = self.workspace
        for cmd in parsed.commands:
            cwd = self._check_command(cmd, cwd, f)
        names = {
            base_name(a[0]) for c in parsed.commands if (a := effective_argv(c.argv))
        }
        if names & NETWORK_CMDS and any(
            "credential path" in reason for _, reason in f.items
        ):
            f.add(Decision.DENY, "credential path combined with a network tool")
        return f.verdict()

    def analyse_tool(self, name: str, args: dict[str, Any]) -> ClassifierVerdict:
        """Stage A for any mutating tool."""
        f = Findings()
        if name == "Bash":
            return self.analyse_bash(str(args.get("command", "")))
        if name in {"Write", "Edit"}:
            path = self._resolve(str(args.get("file_path", "")), self.workspace)
            if path is None or self._outside(path):
                f.add(Decision.ASK, "writes outside the workspace")
            elif is_cred(path):
                f.add(Decision.ASK, "writes a credential file")
            elif path.startswith(self.workspace + "/.dot"):
                f.add(Decision.ASK, "writes to the protected .dot directory")
        elif name != "KillShell":
            f.add(Decision.ASK, f"{name} is not covered by the classifier")
        return f.verdict()

    def classify(
        self, session: str, name: str, args: dict[str, Any]
    ) -> ClassifierVerdict:
        """Stage A allow + Stage B clean -> allow; anything else is not allow."""
        verdict = self.analyse_tool(name, args)
        if verdict.decision != Decision.ALLOW:
            return verdict
        taint = self.taint.check(session, args)
        if taint:
            return ClassifierVerdict(decision=Decision.ASK, stage="B", reason=taint)
        return ClassifierVerdict(
            decision=Decision.ALLOW, stage="B", reason="stage A clean, no taint"
        )
