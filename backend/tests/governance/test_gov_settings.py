import json
from pathlib import Path

import pytest
from backend.cognition.services.tools.executor import default_registry
from backend.core.exceptions import DomainException
from backend.governance.services.permission_engine import PermissionEngine
from backend.governance.services.rules import RuleContext
from backend.governance.settings.loader import SETTINGS_INVALID, SettingsProvider
from backend.governance.settings.schema import DotSettings, HookEvent
from dot_contracts.permissions import Decision

BASELINE = (
    Path(__file__).resolve().parents[3] / "deploy/config/dot/default_permissions.json"
)


def put(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def test_schema_defaults_and_unknown_keys_are_ignored():
    s = DotSettings.model_validate({"model": "x"})
    assert s.rules() == []
    assert s.hooks == {}


def test_rules_are_flattened_with_decisions():
    s = DotSettings.model_validate(
        {
            "permissions": {
                "allow": ["Bash(ls:*)"],
                "ask": ["Write"],
                "deny": ["Read(./s/**)"],
            }
        }
    )
    got = {(r.decision, r.tool, r.specifier) for r in s.rules()}
    assert got == {
        (Decision.ALLOW, "Bash", "ls:*"),
        (Decision.ASK, "Write", None),
        (Decision.DENY, "Read", "./s/**"),
    }


def test_hook_schema_rejects_unknown_events_and_bad_timeouts():
    for bad in (
        {"hooks": {"Nope": [{"command": "x"}]}},
        {"hooks": {"Stop": [{"command": ""}]}},
        {"hooks": {"Stop": [{"command": "x", "timeout": 0}]}},
        {"permissions": {"allow": ["not a rule"]}},
    ):
        with pytest.raises(ValueError, match=r"validation error|rule"):
            DotSettings.model_validate(bad)
    ok = DotSettings.model_validate({"hooks": {"PreCompact": [{"command": "x"}]}})
    assert ok.hooks[HookEvent.PRE_COMPACT][0].timeout == 30


def test_merge_workspace_first_user_second_baseline_last(tmp_path: Path):
    base = put(
        tmp_path / "base.json",
        {"permissions": {"deny": ["Bash(base:*)"], "allow": ["A"]}},
    )
    user = put(
        tmp_path / "home/settings.json", {"permissions": {"allow": ["U"], "ask": ["Q"]}}
    )
    ws = tmp_path / "ws"
    put(ws / ".dot/settings.json", {"permissions": {"allow": ["W", "U"]}})
    cfg = SettingsProvider(ws, user, base).get()
    assert cfg.permissions.allow == ["W", "U", "A"]  # workspace first, deduped
    assert cfg.permissions.deny == ["Bash(base:*)"]
    assert cfg.permissions.ask == ["Q"]


def test_workspace_cannot_drop_a_user_deny(tmp_path: Path):
    user = put(tmp_path / "u.json", {"permissions": {"deny": ["Bash(rm:*)"]}})
    ws = tmp_path / "ws"
    put(ws / ".dot/settings.json", {"permissions": {"allow": ["Bash(rm:*)"]}})
    prov = SettingsProvider(ws, user)
    eng = PermissionEngine(prov.rules, RuleContext(str(ws)))
    bash = default_registry().get("Bash").definition  # type: ignore[union-attr]
    assert eng.decide("bypass", bash, {"command": "rm x"}).decision == Decision.DENY


def test_hooks_from_all_layers_are_kept(tmp_path: Path):
    user = put(tmp_path / "u.json", {"hooks": {"Stop": [{"command": "user-stop"}]}})
    ws = tmp_path / "ws"
    put(
        ws / ".dot/settings.json",
        {
            "hooks": {
                "Stop": [{"command": "ws-stop"}],
                "PreToolUse": [{"command": "pre"}],
            }
        },
    )
    hooks = SettingsProvider(ws, user).get().hooks
    assert [h.command for h in hooks[HookEvent.STOP]] == ["ws-stop", "user-stop"]
    assert [h.command for h in hooks[HookEvent.PRE_TOOL_USE]] == ["pre"]


def test_missing_files_are_fine_and_changes_are_picked_up(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    base = tmp_path / "base.json"
    put(base, {})
    prov = SettingsProvider(ws, tmp_path / "nope.json", base)
    assert prov.rules() == []
    first = prov.get()
    assert prov.get() is first  # cached while files are unchanged
    put(ws / ".dot/settings.json", {"permissions": {"deny": ["Bash"]}})
    assert len(prov.rules()) == 1
    put(ws / ".dot/settings.json", {"permissions": {"deny": ["Bash", "Write"]}})
    assert len(prov.rules()) == 2
    (ws / ".dot/settings.json").unlink()
    assert prov.rules() == []


@pytest.mark.parametrize(
    "content", ["{not json", "[]", '{"permissions": {"deny": ["Bash("]}}']
)
def test_invalid_files_fail_closed(tmp_path: Path, content: str):
    ws = tmp_path / "ws"
    put(ws / ".dot/settings.json", content)
    with pytest.raises(DomainException) as exc:
        SettingsProvider(ws).get()
    assert exc.value.code == SETTINGS_INVALID


def test_shipped_baseline_denies_secrets_and_allows_read_only_commands(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    prov = SettingsProvider(ws, tmp_path / "none.json", BASELINE)
    eng = PermissionEngine(prov.rules, RuleContext(str(ws), home="/home/u"))
    reg = default_registry()

    def go(tool: str, args: dict, mode: str = "default") -> Decision:
        return eng.decide(mode, reg.get(tool).definition, args).decision  # type: ignore[union-attr]

    for path in (
        ".env",
        "app/.env",
        "~/.ssh/id_rsa",
        "/home/u/.aws/credentials",
        "k/server.pem",
    ):
        assert go("Read", {"file_path": path}) == Decision.DENY, path
    assert go("Read", {"file_path": ".env.example"}) == Decision.ALLOW
    assert go("Read", {"file_path": "src/app.py"}) == Decision.ALLOW
    for cmd in ("cat .env", "cat ~/.ssh/id_rsa", "head -1 app/.env.local"):
        assert go("Bash", {"command": cmd}, "bypass") == Decision.DENY, cmd
    assert go("Bash", {"command": "git status"}) == Decision.ALLOW
    assert go("Bash", {"command": "ls -la && git diff"}) == Decision.ALLOW
    assert go("Bash", {"command": "cat README.md | head -5"}) == Decision.ALLOW
    assert go("Bash", {"command": "git status && rm -rf /"}) == Decision.ASK
    assert go("Bash", {"command": "ls $(rm x)"}) == Decision.ASK
    assert (
        go("Write", {"file_path": ".git/hooks/pre-commit", "content": ""}, "bypass")
        == Decision.DENY
    )


def test_missing_baseline_fails_closed(tmp_path: Path):
    prov = SettingsProvider(tmp_path, None, tmp_path / "gone.json")
    with pytest.raises(DomainException) as exc:
        prov.get()
    assert exc.value.code == SETTINGS_INVALID
