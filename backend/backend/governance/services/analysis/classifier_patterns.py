"""Stage A building blocks: pattern tables, findings and network/exfil checks."""

import fnmatch
import os
import re
from dataclasses import dataclass, field

from dot_contracts.permissions import ClassifierVerdict, Decision

from backend.governance.services.analysis.ast_bash_parser import Command, base_name

RANK = {Decision.ALLOW: 0, Decision.ASK: 1, Decision.DENY: 2}
SYSTEM_DIRS = frozenset(
    [
        "/",
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/lib64",
        "/opt",
        "/proc",
        "/root",
        "/sbin",
        "/srv",
        "/sys",
        "/usr",
        "/var",
        "/usr/bin",
        "/usr/lib",
        "/usr/local",
    ]
)
CRED_PATTERNS = (
    "*/.ssh/*", "*/.ssh", "*/.aws/*", "*/.gnupg/*", "*/.netrc", "*/.npmrc",
    "*/.pypirc", "*/.git-credentials", "*/.kube/config", "*/.docker/config.json",
    "*/.config/gh/hosts.yml", "*/.env", "*/.env.*", "*/id_rsa*", "*/id_ed25519*",
    "*/id_ecdsa*", "*.pem", "*.p12", "*.pfx", "/etc/shadow", "/etc/sudoers*",
    "*/credentials.json", "*/service-account*.json", "*/.vault-token",
)  # fmt: skip
NET_UPLOAD_CMDS = frozenset({"curl", "wget"})
RAW_NET = frozenset({"nc", "ncat", "netcat", "socat", "telnet"})
REMOTE_COPY = frozenset({"scp", "rsync", "sftp"})
NETWORK_CMDS = NET_UPLOAD_CMDS | RAW_NET | REMOTE_COPY
_PUBLISH = (
    ("git", "push"),
    ("npm", "publish"),
    ("docker", "push"),
    ("twine", "upload"),
)
_REMOTE_SPEC = re.compile(r"^[\w.\-]+@[\w.\-]+:|^[\w.\-]+:|^\w+://")
SHELL_FILE_WRITERS = frozenset(
    [
        "rm",
        "touch",
        "mkdir",
        "tee",
        "chmod",
        "chown",
        "truncate",
        "rmdir",
        "shred",
        "mv",
        "ln",
        "dd",
        "install",
        "cp",
    ]
)
WRITE_OPS = frozenset({">", ">>", ">|", "&>", "&>>"})
_DATA_FLAGS = ("-d", "--data", "--data-binary", "--data-raw", "--data-urlencode",
               "-F", "--form", "-T", "--upload-file", "--post-data", "--post-file",
               "--body-data", "--body-file")  # fmt: skip


@dataclass
class Findings:
    items: list[tuple[Decision, str]] = field(default_factory=list)

    def add(self, decision: Decision, reason: str) -> None:
        self.items.append((decision, reason))

    def verdict(self, stage: str = "A") -> ClassifierVerdict:
        if not self.items:
            return ClassifierVerdict(
                decision=Decision.ALLOW, stage=stage, reason="no risky pattern found"
            )
        worst = max(self.items, key=lambda i: RANK[i[0]])[0]
        reasons = dict.fromkeys(r for _, r in self.items)
        return ClassifierVerdict(decision=worst, stage=stage, reason="; ".join(reasons))


def is_cred(path: str) -> bool:
    norm = path if path.startswith(("/", "~")) else "/" + os.path.normpath(path)
    return any(fnmatch.fnmatchcase(norm, p) for p in CRED_PATTERNS)


def check_network(cmd: Command, argv: list[str], f: Findings) -> None:
    name = base_name(argv[0])
    rest = argv[1:]
    if name in NET_UPLOAD_CMDS:
        _check_upload(name, rest, f)
    elif name in RAW_NET:
        sends = cmd.piped_in or any(r.op in {"<", "<<", "<<<"} for r in cmd.redirects)
        f.add(
            Decision.DENY if sends else Decision.ASK,
            f"raw network tool {name}" + (" fed with local data" if sends else ""),
        )
    elif name in REMOTE_COPY:
        remote = [a for a in rest if _REMOTE_SPEC.match(a)]
        if remote and _REMOTE_SPEC.match(rest[-1]):
            f.add(Decision.DENY, f"{name} sends data to a remote host")
        elif remote:
            f.add(Decision.ASK, f"{name} touches a remote host")
    for words in _PUBLISH:
        if argv[: len(words)] == list(words):
            f.add(Decision.ASK, f"{' '.join(words)} publishes data")


def _check_upload(name: str, rest: list[str], f: Findings) -> None:
    posts = False
    for i, a in enumerate(rest):
        flag, _, inline = a.partition("=")
        is_data = flag in _DATA_FLAGS or (
            a.startswith(("-d", "-F", "-T")) and not a.startswith("--")
        )
        if flag in {"-X", "--request", "--method"}:
            nxt = inline or (rest[i + 1] if i + 1 < len(rest) else "")
            posts = posts or nxt.upper() in {"POST", "PUT", "PATCH"}
        if is_data:
            posts = True
            value = inline or a[2:] or (rest[i + 1] if i + 1 < len(rest) else "")
            if (
                value.startswith("@")
                or flag in {"-T", "--upload-file", "--post-file", "--body-file"}
                or "=@" in value
            ):
                f.add(Decision.DENY, f"{name} uploads a local file")
    if posts:
        f.add(Decision.ASK, f"{name} sends data (POST/upload)")
