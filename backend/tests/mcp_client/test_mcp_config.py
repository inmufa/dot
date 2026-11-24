import json

import httpx
import pytest
from backend.core import ssrf
from backend.core.exceptions import DomainException
from backend.core.ssrf import Blocked
from backend.governance.settings.loader import SettingsProvider
from backend.governance.settings.mcp_spec import McpServerSpec
from backend.mcp.services import config, transports
from backend.mcp.services.transports import GuardedTransport, check_url
from pydantic import ValidationError


def test_spec_shapes():
    assert McpServerSpec(command="x").transport == "stdio"
    assert McpServerSpec(url="http://h/mcp").transport == "http"
    assert McpServerSpec(type="sse", url="http://h/s").transport == "sse"


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"command": "x", "url": "http://h"},
        {"command": "x", "type": "http"},
        {"url": "http://h", "type": "stdio"},
        {"command": "x", "args": ["a"] * 65},
    ],
)
def test_spec_rejects_bad_shapes(bad):
    with pytest.raises(ValidationError):
        McpServerSpec(**bad)


def test_fingerprint_changes_with_config():
    a = McpServerSpec(command="x", args=["1"])
    assert a.fingerprint() == McpServerSpec(command="x", args=["1"]).fingerprint()
    assert a.fingerprint() != McpServerSpec(command="x", args=["2"]).fingerprint()
    assert a.fingerprint() != McpServerSpec(command="y", args=["1"]).fingerprint()


ENV = {"GITHUB_TOKEN": "ghp_x", "OTHER": "o", "AWS_SECRET_ACCESS_KEY": "s"}
ALLOWED = config.allowlist("GITHUB_TOKEN, OTHER")


def test_expand_reads_only_the_allowlist():
    assert config.expand("Bearer ${GITHUB_TOKEN}", ALLOWED, ENV) == "Bearer ghp_x"
    assert config.expand("plain", ALLOWED, ENV) == "plain"
    with pytest.raises(config.McpConfigError, match="ALLOWLIST"):
        config.expand("${AWS_SECRET_ACCESS_KEY}", ALLOWED, ENV)
    with pytest.raises(config.McpConfigError, match="not set"):
        config.expand("${OTHER}", ALLOWED, {})


def test_expand_does_not_recurse_or_run_shell():
    env = {"A": "${B}", "B": "secret"}
    assert config.expand("${A}", frozenset({"A"}), env) == "${B}"
    assert config.expand("$(id) `id` $A", frozenset({"A"}), env) == "$(id) `id` $A"


def test_resolve_maps_expands_env_and_headers():
    spec = McpServerSpec(
        url="https://h/mcp",
        headers={"Authorization": "Bearer ${GITHUB_TOKEN}"},
        env={"X": "${OTHER}"},
    )
    env, headers = config.resolve_maps(spec, ALLOWED, ENV)
    assert env == {"X": "o"}
    assert headers == {"Authorization": "Bearer ghp_x"}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_scopes_and_workspace_wins_on_clash(tmp_path):
    ws, user = tmp_path / "ws", tmp_path / "u" / "settings.json"
    write(user, {"mcpServers": {"a": {"command": "ua"}, "b": {"command": "ub"}}})
    write(ws / ".dot" / "settings.json", {"mcpServers": {"b": {"command": "wb"}}})
    got = SettingsProvider(ws, user, None).mcp_servers()
    assert got["a"][1] == "user"
    assert got["b"][1] == "project"
    assert got["b"][0].command == "wb"


def test_invalid_server_fails_closed(tmp_path):
    ws = tmp_path / "ws"
    write(
        ws / ".dot" / "settings.json", {"mcpServers": {"bad name!": {"command": "x"}}}
    )
    with pytest.raises(DomainException) as exc:
        SettingsProvider(ws, None, None).get()
    assert exc.value.code == 3005


async def test_ssrf_blocks_private_hosts_unless_allowed():
    for url in (
        "http://127.0.0.1:9/mcp",
        "http://169.254.169.254/latest",
        "http://10.0.0.5/mcp",
        "http://localhost/mcp",
        "http://[::1]/mcp",
        "http://2130706433/mcp",
    ):
        with pytest.raises(config.McpConfigError):
            await check_url(McpServerSpec(url=url))
    ok = await check_url(
        McpServerSpec(url="http://127.0.0.1:9/mcp", allowHosts=["127.0.0.1"])
    )
    assert "127.0.0.1" in ok


async def test_guarded_transport_blocks_at_request_time():
    transport = GuardedTransport(frozenset())
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.ConnectError, match="blocked"):
            await client.get("http://10.1.2.3/x")
    assert Blocked


async def test_guarded_transport_pins_vetted_ip(monkeypatch):
    seen: list[httpx.Request] = []

    async def fake_vet(url):
        return ssrf.Target(url, "https", "mcp.example.com", 443, "93.184.216.34", "/")

    class Inner(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            seen.append(request)
            return httpx.Response(200, request=request)

    monkeypatch.setattr(transports, "vet", fake_vet)
    transport = GuardedTransport(frozenset())
    transport._inner = Inner()
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        await client.get("https://mcp.example.com/x")
    assert seen[0].url.host == "93.184.216.34"
    assert seen[0].headers["host"] == "mcp.example.com"
    assert seen[0].extensions["sni_hostname"] == "mcp.example.com"
