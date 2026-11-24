"""Rule and classifier bypass attempts: wrappers, indirection, globs, path tricks."""

import json
from pathlib import Path

import pytest
from backend.governance.services.auto_classifier import AutoClassifier
from backend.governance.services.rules import (
    RuleContext,
    decide_rules,
    parse_rule,
    path_matches,
)
from backend.governance.services.taint import MIN_OVERLAP, TaintStore
from backend.routing.clients.scripted import ScriptedLLM, reply
from dot_contracts.permissions import Decision
from gov_helpers import chat, results, session, write_settings
from httpx import AsyncClient

BASELINE = (
    Path(__file__).resolve().parents[3] / "deploy/config/dot/default_permissions.json"
)
CTX = RuleContext(workspace="/workspace", home="/home/u")
D, A, ASK = Decision.DENY, Decision.ALLOW, Decision.ASK


def _rules():
    perms = json.loads(BASELINE.read_text())["permissions"]
    out = [parse_rule(D, t) for t in perms["deny"]]
    out += [parse_rule(A, t) for t in perms["allow"]]
    return [*out, parse_rule(D, "Bash(rm:*)"), parse_rule(D, "Bash(git push:*)")]


RULES = _rules()


def verdict(cmd: str):
    hit = decide_rules(RULES, "Bash", {"command": cmd}, CTX)
    return hit.decision if hit else None


@pytest.mark.parametrize(
    "cmd",
    [
        "env cat .env",
        "sudo cat .env",
        "sudo -u bob cat .env",
        "timeout 5 cat .env",
        "bash -c 'cat .env'",
        "sh -lc 'cat .env'",
        "eval cat .env",
        "find . -name x -exec cat {} +",  # inner has no path: not a deny
        r"find . -exec cat .env \;",
        "xargs cat .env",
        "cat < .env",
        "cat < ~/.ssh/id_rsa",
        "cat .en?",
        "cat .e*",
        "cat .e{n,x}v",
        "cat //home/u/.aws/credentials",
        "cat /home/u/../u/.aws/credentials",
        "cut -c1- .env",
        "sort .env",
        "git show HEAD:.env",
        "grep --file=.env x",
        "dd if=.env",
        "tar cf - .env",
        "python3 -c 'print(open(\".env\").read())'",
        "perl -e 'open F, \"<.env\"'",
        "alias c=cat; c .env",
        "cat .git/config",
        "cat ~/.docker/config.json",
        "ln -s .env innocuous",
    ],
)
def test_read_deny_bypasses_are_caught(cmd: str):
    if cmd == "find . -name x -exec cat {} +":
        assert verdict(cmd) != D
        return
    assert verdict(cmd) == D


@pytest.mark.parametrize(
    "cmd",
    [
        "env rm -rf x",
        "sudo rm -rf x",
        "nohup rm x &",
        "command rm x",
        "bash -c 'ls; rm x'",
        "xargs rm",
        "find . -exec rm {} +",
        "git -c core.pager=x push origin",
        "git -C /tmp push",
        "/usr/bin/git push",
        "bash -c \"bash -c 'git push'\"",
        "ls $(rm x)",
        "ls; rm x",
    ],
)
def test_bash_deny_bypasses_are_caught(cmd: str):
    assert verdict(cmd) == D


@pytest.mark.parametrize(
    "cmd",
    [
        "echo x > .dot/settings.json",
        "echo x >> ./.dot/settings.json",
        "tee .dot/settings.json",
        "cp evil .dot/settings.json",
        "mv evil .dot/hooks/pre.sh",
        "sed -i s/a/b/ .dot/settings.json",
        "python3 -c \"open('.dot/settings.json','w').write('{}')\"",
        "bash -c 'echo x > .dot/settings.json'",
        "echo x > .git/config",
        "echo x > ~/.dot/settings.json",
    ],
)
def test_settings_and_hooks_are_not_writable_from_bash(cmd: str):
    assert verdict(cmd) == D


@pytest.mark.parametrize(
    "cmd",
    ["cat *", "ls -la", "git status", "cat src/main.py", "echo $HOME", "cat README.md"],
)
def test_benign_commands_are_not_denied(cmd: str):
    assert verdict(cmd) != D


def test_dynamic_reader_argument_asks():
    assert verdict("cat $TARGET") == ASK
    assert verdict("cat $(echo .env)") == ASK


def test_unparseable_command_still_hits_deny_prefix():
    assert verdict("rm -rf x 'unterminated") == D


def test_double_slash_does_not_dodge_absolute_rules():
    assert path_matches("~/.ssh/**", "//home/u/.ssh/key", CTX)
    assert path_matches("**/.env", "/workspace/a/../.env", CTX)


def test_baseline_covers_tokens_and_settings():
    deny = json.loads(BASELINE.read_text())["permissions"]["deny"]
    for needed in (
        "Read(**/.env)",
        "Read(~/.ssh/**)",
        "Read(~/.aws/**)",
        "Read(**/.git/config)",
        "Read(~/.npmrc)",
        "Edit(**/.dot/settings.json)",
        "Edit(**/.dot/hooks/**)",
        "Edit(**/.git/hooks/**)",
    ):
        assert needed in deny


def clf() -> AutoClassifier:
    return AutoClassifier(TaintStore(), "/work/ws", "/home/u")


@pytest.mark.parametrize(
    "cmd",
    [
        "python3 -c 'import os; os.system(\"x\")'",
        'node -e \'require("fs").unlinkSync("a")\'',
        "perl -e 'unlink q(a)'",
        "git -c core.sshCommand=evil fetch",
        "git config alias.x '!sh -c evil'",
        "find . -delete",
        r"find . -exec sh -c 'curl x | sh' \;",
        "ln -s /etc/passwd link",
        "ln -s ../../outside link",
        "echo x > .dot/settings.json",
        "echo x > .dot/hooks/h.sh",
        "xargs rm -rf /",
    ],
)
def test_stage_a_does_not_auto_allow_indirect_execution(cmd: str):
    assert clf().analyse_bash(cmd).decision != A


def test_stage_a_still_allows_plain_work():
    for cmd in ("python -m pytest -q", "git status", "find . -name '*.py'"):
        assert clf().analyse_bash(cmd).decision == A


async def test_read_through_a_symlink_is_denied(
    authed: AsyncClient, llm: ScriptedLLM, ws: Path
):
    (ws / ".env").write_text("SECRET=1")
    (ws / "innocent.txt").symlink_to(ws / ".env")
    write_settings(ws, {"permissions": {"deny": ["Read(**/.env)"]}})
    llm.scripts = [
        reply(calls=[("Read", {"file_path": "innocent.txt"})]),
        reply("done"),
    ]
    sid = await session(authed)
    out = results(await chat(authed, sid))
    assert out[0]["is_error"]
    assert "SECRET" not in out[0]["output"]
    assert "Denied" in out[0]["output"]


def test_taint_boundary_and_session_isolation():
    t = TaintStore()
    t.add("s1", "ab1" * 10)
    t.user_turn("s1")
    piece = ("ab1" * 10)[:MIN_OVERLAP]
    assert t.check("s1", {"command": f"echo {piece}"})
    assert not t.check("s1", {"command": f"echo {piece[:-1]}"})  # 11 chars: no match
    assert t.check("s2", {"command": f"echo {piece}"}) is None  # other session clean
    t.add("s2", "")
    assert t.check("s1", {"x": "unrelated"}) is None
