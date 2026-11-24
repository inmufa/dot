import pytest
from backend.governance.services.rules import (
    RuleContext,
    decide_rules,
    parse_rule,
    path_matches,
)
from dot_contracts.permissions import Decision

CTX = RuleContext(workspace="/w", home="/home/u")
A, ASK, D = Decision.ALLOW, Decision.ASK, Decision.DENY


def rules(**kw: list[str]):
    out = []
    for key, decision in (("deny", D), ("allow", A), ("ask", ASK)):
        out += [parse_rule(decision, t) for t in kw.get(key, [])]
    return out


def hit(rs, command: str):
    r = decide_rules(rs, "Bash", {"command": command}, CTX)
    return r.decision if r else None


def test_parse_rule_shapes():
    r = parse_rule(A, "Bash(git status:*)")
    assert (r.tool, r.specifier, r.decision) == ("Bash", "git status:*", A)
    assert parse_rule(D, "Write").specifier is None
    assert parse_rule(D, " Read( ./secrets/** ) ").specifier == "./secrets/**"
    assert parse_rule(A, "mcp__srv__tool").tool == "mcp__srv__tool"
    for bad in ("", "(x)", "Bash(", "two words"):
        with pytest.raises(ValueError, match="invalid permission rule"):
            parse_rule(A, bad)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git status", A),
        ("git status -sb", A),
        ("git   status   -s", A),  # whitespace is normalised
        ("git statusx", None),
        ("git stash", None),
        ("git", None),
        ("git status && rm -rf /", None),
        ("git status; rm -rf /", None),
        ("git status || rm -rf /", None),
        ("git status | sh", None),
        ("git status & rm -rf /", None),
        ("git status\nrm -rf /", None),
        ("git status $(rm -rf /)", None),
        ("git status `rm -rf /`", None),
        ("git status <(curl x)", None),
        ("git status > /tmp/x", None),
        ("git status >> notes.txt", None),
        ("git status > /dev/null", A),
        ("git status 2>&1", A),
        ("FOO=1 git status", None),
        ("git status $EXTRA", None),
        ("git status && git status -s", A),
        ("echo 'git status && x'", None),
        ("git commit -m 'a && b'", None),
    ],
)
def test_prefix_allow_never_matches_compound_commands(command, expected):
    assert hit(rules(allow=["Bash(git status:*)"]), command) == expected


def test_every_segment_needs_an_allow_rule():
    rs = rules(allow=["Bash(git status:*)", "Bash(ls:*)", "Bash(wc:*)"])
    assert hit(rs, "git status && ls -la | wc -l") == A
    assert hit(rs, "git status && ls -la | sh") is None
    assert hit(rs, "if true; then ls; fi") is None  # `true` is unmatched


def test_deny_matches_any_segment_even_nested():
    rs = rules(deny=["Bash(rm:*)"], allow=["Bash(echo:*)"])
    assert hit(rs, "echo hi && rm -rf x") == D
    assert hit(rs, "echo $(rm x)") == D
    assert hit(rs, "echo hi | tee x; rm y") == D
    assert hit(rs, "FOO=1 rm x") == D
    assert hit(rs, "echo hi") == A


def test_ask_applies_when_any_segment_asks_and_none_deny():
    rs = rules(ask=["Bash(git push:*)"], allow=["Bash(git status:*)"])
    assert hit(rs, "git status && git push origin") == ASK
    assert hit(rs, "git status") == A


def test_exact_and_glob_specifiers():
    exact = rules(allow=["Bash(npm run build)"])
    assert hit(exact, "npm run build") == A
    assert hit(exact, "npm run build --prod") is None
    glob = rules(allow=["Bash(git * --help)"])
    assert hit(glob, "git commit --help") == A
    assert hit(glob, "git commit") is None


def test_bare_tool_rule_matches_everything_incl_substitution():
    assert hit(rules(allow=["Bash"]), "anything $(x) && y") == A
    assert hit(rules(deny=["Bash"], allow=["Bash(ls:*)"]), "ls") == D
    assert hit(rules(allow=["Bash"]), "") is not None


def test_empty_command_and_unparseable_fall_back_safely():
    rs = rules(allow=["Bash(echo:*)"], deny=["Bash(rm:*)"])
    assert hit(rs, "") is None
    assert hit(rs, "echo 'unterminated") is None  # allow never matches unparsed
    assert hit(rs, "echo 'x && rm -rf /") == D  # deny still sees the segments


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("./secrets/**", "secrets/a.txt", True),
        ("./secrets/**", "/w/secrets/deep/a.txt", True),
        ("./secrets/**", "secrets", True),
        ("./secrets/**", "src/secrets/a.txt", False),
        ("./secrets/**", "secretsX/a.txt", False),
        ("secrets/**", "secrets/a", True),
        ("**/.env", ".env", True),
        ("**/.env", "a/b/.env", True),
        ("**/.env", "a/.env.example", False),
        (".env", "a/b/.env", True),  # no slash: any depth, gitignore style
        ("*.pem", "x/y/cert.pem", True),
        ("*.pem", "cert.pem.txt", False),
        ("src/*.py", "src/a.py", True),
        ("src/*.py", "src/sub/a.py", False),
        ("src/**/*.py", "src/sub/deep/a.py", True),
        ("src/**/*.py", "src/a.py", True),
        ("~/.ssh/**", "~/.ssh/id_rsa", True),
        ("~/.ssh/**", "/home/u/.ssh/id_rsa", True),
        ("~/.ssh/**", "/home/other/.ssh/id_rsa", False),
        ("/etc/**", "/etc/passwd", True),
        ("/etc/**", "/w/etc/passwd", False),
        ("config?.yml", "config1.yml", True),
        ("config?.yml", "config12.yml", False),
        ("./a/../secrets/**", "secrets/x", False),  # patterns are literal
        ("secrets/**", "a/../secrets/x", True),  # paths are normalised
        ("secrets/**", "/w/a/../../etc/x", False),
        ("**/id_rsa*", "/home/u/.ssh/id_rsa.pub", True),
    ],
)
def test_path_globs(pattern, path, expected):
    assert path_matches(pattern, path, CTX) is expected


def test_read_rule_covers_grep_glob_and_shell_readers():
    rs = rules(deny=["Read(./secrets/**)"])
    for tool, args in (
        ("Read", {"file_path": "secrets/k"}),
        ("Grep", {"pattern": "x", "path": "secrets"}),
        ("Glob", {"pattern": "*", "path": "/w/secrets"}),
    ):
        assert decide_rules(rs, tool, args, CTX).decision == D
    assert decide_rules(rs, "Read", {"file_path": "src/a"}, CTX) is None
    assert decide_rules(rs, "Write", {"file_path": "secrets/k"}, CTX) is None
    assert hit(rs, "cat secrets/k") == D
    assert hit(rs, "grep -r x secrets") == D
    assert hit(rs, "ls secrets") is None


def test_edit_rule_covers_write_and_redirects():
    rs = rules(deny=["Edit(**/.git/hooks/**)"])
    args = {"file_path": ".git/hooks/pre-commit", "content": "x"}
    assert decide_rules(rs, "Write", args, CTX).decision == D
    assert decide_rules(rs, "Edit", args, CTX).decision == D
    assert hit(rs, "echo x > .git/hooks/pre-commit") == D
    assert hit(rs, "rm .git/hooks/pre-commit") == D
    assert hit(rs, "echo x > notes.txt") is None


def test_precedence_on_non_bash_tools():
    rs = rules(allow=["Write"], deny=["Write(**/*.lock)"], ask=["Write(docs/**)"])
    assert decide_rules(rs, "Write", {"file_path": "a.lock"}, CTX).decision == D
    assert decide_rules(rs, "Write", {"file_path": "docs/a.md"}, CTX).decision == A
    assert decide_rules(rs, "Edit", {"file_path": "docs/a.md"}, CTX) is None


def test_webfetch_domain_and_generic_rules():
    rs = rules(allow=["WebFetch(domain:example.com)"], deny=["mcp__x__*"])
    ok = {"url": "https://docs.example.com/a"}
    assert decide_rules(rs, "WebFetch", ok, CTX).decision == A
    assert decide_rules(rs, "WebFetch", {"url": "https://evilexample.com"}, CTX) is None
    assert decide_rules(rs, "mcp__x__y", {}, CTX).decision == D
    assert decide_rules(rs, "mcp__z__y", {}, CTX) is None
    assert decide_rules(rules(deny=["Skill(rm*)"]), "Skill", {"name": "rmx"}, CTX)
