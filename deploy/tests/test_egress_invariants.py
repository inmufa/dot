"""Static egress and privacy invariants of the compose file (no docker needed)."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "deploy/compose/compose.base.yml").read_text())
SERVICES = COMPOSE["services"]
NETS = COMPOSE["networks"]
# Services allowed a route to the public internet, and why (docs/privacy.md).
EGRESS_BY_DESIGN = {
    "dot-searxng": {"dot-search"},
    "dot-browser": {"dot-browsing"},
    "dot-backend": {"dot-fetch"},  # WebFetch, behind the SSRF guard
}


def _nets(name: str) -> set[str]:
    return set(SERVICES[name].get("networks", []))


def _routable(net: str) -> bool:
    return not (NETS[net] or {}).get("internal")


def test_core_and_links_are_internal():
    for net in (
        "dot-core",
        "dot-sandbox-link",
        "dot-search-link",
        "dot-browser-link",
        "dot-voice-link",
    ):
        assert NETS[net]["internal"] is True


def test_publish_network_has_no_nat():
    opts = NETS["dot-publish"]["driver_opts"]
    assert opts["com.docker.network.bridge.enable_ip_masquerade"] == "false"


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_only_designed_services_have_a_routable_network(name):
    routable = {n for n in _nets(name) if _routable(n)}
    allowed = EGRESS_BY_DESIGN.get(name, set()) | {"dot-publish"}
    assert routable <= allowed, (name, routable)


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_services_on_publish_net_cannot_resolve_outside_names(name):
    if "dot-publish" in _nets(name) and name != "dot-backend":
        assert SERVICES[name]["dns"] == ["192.0.2.53"]


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_no_default_network_and_no_host_tricks(name):
    svc = SERVICES[name]
    assert svc.get("networks"), "service must name its networks"
    assert "network_mode" not in svc
    assert "extra_hosts" not in svc
    assert "privileged" not in svc
    for vol in svc.get("volumes", []):
        assert "docker.sock" not in str(vol)


def test_ports_are_loopback_and_only_expected_services_publish():
    published = {n for n, s in SERVICES.items() if s.get("ports")}
    assert published == {"dot-llm", "dot-backend", "dot-web", "dot-browser"}
    for name in published:
        for port in SERVICES[name]["ports"]:
            assert str(port).startswith("127.0.0.1:"), (name, port)


def test_sandbox_has_no_published_port_and_no_route_out():
    assert "ports" not in SERVICES["dot-sandbox"]
    assert _nets("dot-sandbox") == {"dot-sandbox-link"}


def test_only_backend_shares_a_network_with_the_sandbox_and_searxng():
    for link, server in (
        ("dot-sandbox-link", "dot-sandbox"),
        ("dot-search-link", "dot-searxng"),
    ):
        members = {n for n in SERVICES if link in _nets(n)}
        assert members == {"dot-backend", server}


def test_llm_is_local_models_only():
    svc = SERVICES["dot-llm"]
    cmd = svc["command"].split()
    assert "-hf" not in cmd
    assert "--hf-repo" not in cmd
    assert svc["environment"]["HF_HUB_OFFLINE"] == "1"
    assert any(v.endswith(":ro") for v in svc["volumes"])


def test_telemetry_flags_set():
    assert SERVICES["dot-web"]["environment"]["NEXT_TELEMETRY_DISABLED"] == "1"
    backend = SERVICES["dot-backend"]["environment"]
    assert backend["DO_NOT_TRACK"] == "1"
    assert "DOT_WEB_SEARCH" in backend


def test_env_example_has_no_personal_data():
    text = (ROOT / ".env.example").read_text().lower()
    assert "@gmail" not in text
    assert "/home/" not in text


def test_privacy_check_is_wired_into_make_and_docs():
    make = (ROOT / "Makefile").read_text()
    assert "privacy-check:\n\tbash deploy/scripts/privacy_check.sh" in make
    assert (ROOT / "deploy/scripts/privacy_check.sh").exists()
    ops = (ROOT / "docs/operations.md").read_text()
    assert "make privacy-check" in ops
    assert (ROOT / "docs/privacy.md").exists()


def test_gitignore_covers_secrets_and_data():
    ignore = (ROOT / ".gitignore").read_text().splitlines()
    for entry in (
        ".env",
        "data/",
        "models/*",
        "*.db",
        "workspace/*",
        "workspace/uploads/",
    ):
        assert entry in ignore, entry
    assert any(line.startswith("llm_debug") for line in ignore)
    assert any("shots" in line for line in ignore)


def test_web_csp_has_no_remote_origin_and_no_prod_eval():
    cfg = (ROOT / "services/web-ui/next.config.ts").read_text()
    for want in (
        "connect-src 'self'",
        "img-src 'self' data: blob:",
        "frame-src 'self'",
        "form-action 'self'",
        "base-uri 'none'",
        "object-src 'none'",
    ):
        assert want in cfg, want
    assert "http://" not in cfg.split("const CSP")[1].split("].join")[0]
    assert "dev ? \" 'unsafe-eval'\"" in cfg


def test_firewall_script_covers_every_egress_network():
    text = (ROOT / "deploy/scripts/firewall_dot.sh").read_text()
    for net in ("browsing", "fetch", "search", "publish"):
        assert net in text
