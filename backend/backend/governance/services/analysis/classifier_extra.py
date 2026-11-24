"""Stage A checks for ways a command can run code the parser cannot see."""

from dot_contracts.permissions import Decision

from backend.governance.services.analysis.ast_bash_parser import Command, base_name
from backend.governance.services.analysis.classifier_patterns import Findings
from backend.governance.services.analysis.shell_views import INLINE, views

_GIT_CODE_KEYS = ("alias.", "core.sshcommand", "core.pager", "core.editor", "core.hookspath", "core.fsmonitor", "credential.helper")  # fmt: skip


def check_indirect(cmd: Command, f: Findings) -> list[Command]:
    """Flag inline interpreter code, `git -c`, `find -exec/-delete`.

    Returns the commands it runs indirectly so the caller can vet them too.
    """
    out = views(cmd)
    if any(v.argv and v.argv[0] == INLINE for v in out):
        f.add(Decision.ASK, "inline interpreter code (-c/-e) cannot be inspected")
    name = base_name(cmd.argv[0]) if cmd.argv else ""
    if name == "git":
        rest = cmd.argv[1:]
        if "-c" in rest[:6]:
            f.add(Decision.ASK, "git -c can run arbitrary commands")
        if rest[:1] == ["config"] and any(
            k in a.lower() for a in rest[1:] for k in _GIT_CODE_KEYS
        ):
            f.add(Decision.ASK, "git config sets a command-running option")
    if name == "find" and any(
        a in {"-delete", "-fprint", "-fprintf"} for a in cmd.argv
    ):
        f.add(Decision.ASK, "find writes or deletes files")
    return [v for v in out if v.argv and v.argv[0] != INLINE]
