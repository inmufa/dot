from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = yaml.safe_load((ROOT / "deploy/compose/compose.base.yml").read_text())
SERVICES = COMPOSE["services"]


def names() -> list[str]:
    return sorted(SERVICES)


def test_expected_services_exist():
    assert set(SERVICES) == {
        "dot-llm",
        "dot-sandbox",
        "dot-backend",
        "dot-searxng",
        "dot-browser",
        "dot-voice",
        "dot-web",
    }


@pytest.mark.parametrize("name", names())
def test_published_ports_bind_loopback_only(name):
    for port in SERVICES[name].get("ports", []):
        assert str(port).startswith("127.0.0.1:"), (name, port)


@pytest.mark.parametrize("name", names())
def test_hardening_on_every_service(name):
    svc = SERVICES[name]
    assert "ALL" in svc["cap_drop"]
    assert "no-new-privileges:true" in svc["security_opt"]
    assert svc["mem_limit"]
    assert "privileged" not in svc
    assert svc.get("network_mode") != "host"


def test_searxng_is_not_published_and_pinned():
    svc = SERVICES["dot-searxng"]
    assert "ports" not in svc
    tag = svc["image"].split(":")[1]
    assert tag != "latest"
    assert tag[:4].isdigit()
    assert svc["cap_add"] == ["CHOWN", "SETGID", "SETUID"]


def test_browser_is_an_opt_in_profile_with_a_locked_down_container():
    svc = SERVICES["dot-browser"]
    assert svc["profiles"] == ["browser"]
    assert svc["user"] == "1000:1000"
    assert svc["read_only"] is True
    assert svc["mem_limit"] == "1536m"
    assert svc["shm_size"] == "512m"
    assert svc["pids_limit"] == 512
    assert svc["ports"] == ["127.0.0.1:8091:8091"]
    assert svc["build"]["dockerfile"] == "deploy/docker/browser/Dockerfile"
    assert any(t.startswith("/profiles") for t in svc["tmpfs"])
    assert "/tmp" in svc["tmpfs"]  # noqa: S108
    assert "healthcheck" in svc


def test_only_browser_and_voice_are_behind_a_profile():
    assert [n for n, s in SERVICES.items() if "profiles" in s] == [
        "dot-browser",
        "dot-voice",
    ]


def test_web_block():
    svc = SERVICES["dot-web"]
    assert svc["depends_on"]["dot-backend"]["condition"] == "service_healthy"
    assert svc["environment"]["DOT_URL"] == "http://dot-backend:8000"
    assert svc["environment"]["DOT_ALLOW_NON_LOOPBACK"] == "1"
    assert svc["ports"] == ["127.0.0.1:3000:3000"]
    assert svc["mem_limit"] == "256m"


def test_sandbox_never_mounts_memory_or_data_volumes():
    vols = " ".join(SERVICES["dot-sandbox"]["volumes"])
    assert "dot-memory" not in vols
    assert "dot-data" not in vols
    assert "/memory" not in vols
    assert ":ro" in next(
        v for v in SERVICES["dot-sandbox"]["volumes"] if "settings.json" in v
    )
    assert any(v.endswith(".dot/hooks:ro") for v in SERVICES["dot-sandbox"]["volumes"])


def test_backend_workspace_is_read_only_and_memory_is_backend_only():
    vols = SERVICES["dot-backend"]["volumes"]
    ws = [v for v in vols if ":/workspace" in v]
    assert len(ws) == 1
    assert ws[0].endswith(":/workspace:ro")
    others = {
        n
        for n, s in SERVICES.items()
        if "dot-memory:/memory" in " ".join(s.get("volumes", []))
    }
    assert others == {"dot-backend"}


def test_backend_env_points_at_searxng_and_the_browser():
    env = SERVICES["dot-backend"]["environment"]
    assert env["DOT_SEARXNG_URL"] == "http://dot-searxng:8080"
    assert env["DOT_BROWSER_URL"] == "http://dot-browser:8091"
    assert "DOT_BROWSER_TOKEN" in env
    assert "DOT_MCP_ENV_ALLOWLIST" in env


def test_secrets_are_required_or_defaulted_never_literal():
    for name, svc in SERVICES.items():
        for key, value in svc.get("environment", {}).items():
            if any(w in key for w in ("TOKEN", "SECRET")):
                assert str(value).startswith("${"), (name, key)


def test_network_isolation():
    nets = COMPOSE["networks"]
    assert nets["dot-browser-link"]["internal"] is True
    of = {n: set(s.get("networks", [])) for n, s in SERVICES.items()}
    assert of["dot-browser"] == {"dot-browsing", "dot-browser-link"}
    assert of["dot-backend"] == {
        "dot-core",
        "dot-sandbox-link",
        "dot-search-link",
        "dot-publish",
        "dot-fetch",
        "dot-browser-link",
        "dot-voice-link",
    }
    assert nets["dot-voice-link"]["internal"] is True
    assert of["dot-voice"] == {"dot-voice-link"}
    assert of["dot-llm"] == {"dot-core", "dot-publish"}
    assert of["dot-web"] == {"dot-core", "dot-publish"}
    assert of["dot-sandbox"] == {"dot-sandbox-link"}
    assert of["dot-searxng"] == {"dot-search-link", "dot-search"}
    assert "dot-core" not in of["dot-browser"]


def test_images_are_pinned():
    for name, svc in SERVICES.items():
        if "image" in svc:
            assert not svc["image"].endswith(":latest"), name
            assert ":" in svc["image"], name


def test_env_example_has_the_new_entries():
    env = (ROOT / ".env.example").read_text()
    for key in (
        "DOT_BROWSER_TOKEN",
        "SEARXNG_SECRET",
        "DOT_SANDBOX_TOKEN",
        "DOT_API_TOKEN",
    ):
        assert f"{key}=" in env


def test_makefile_has_up_and_up_browser_with_the_profile():
    make = (ROOT / "Makefile").read_text()
    assert "up-browser:" in make
    assert "--profile browser up" in make
    assert "--profile browser --profile voice down" in make


def test_firewall_script_is_dry_run_by_default():
    text = (ROOT / "deploy/scripts/firewall_dot.sh").read_text()
    assert "--apply)" in text
    assert 'echo "iptables -I' in text


def test_llm_flags_come_from_the_profile_not_constants():
    cmd = " ".join(str(SERVICES["dot-llm"]["command"]).split())
    for flag in (
        "--parallel ${DOT_LLM_PARALLEL",
        "-ngl ${DOT_LLM_NGL",
        "-c ${DOT_LLM_CTX",
    ):
        assert flag in cmd
    for var in (
        "DOT_LLM_FA",
        "DOT_LLM_KV_K",
        "DOT_LLM_KV_V",
        "DOT_LLM_MMPROJ_ARGS",
        "DOT_LLM_EXTRA_ARGS",
    ):
        assert "${" + var in cmd
    assert SERVICES["dot-llm"]["mem_limit"].startswith("${DOT_LLM_MEM_LIMIT")
    assert SERVICES["dot-llm"]["image"].startswith(
        "ghcr.io/ggml-org/llama.cpp:${DOT_LLM_IMAGE_TAG:-"
    )


def test_gpu_access_lives_in_the_overlays_only():
    assert "devices" not in SERVICES["dot-llm"]
    assert "group_add" not in SERVICES["dot-llm"]
    gpu = ROOT / "deploy/compose"
    vulkan = yaml.safe_load((gpu / "compose.gpu-vulkan.yml").read_text())["services"][
        "dot-llm"
    ]
    assert len(vulkan["devices"]) == 1  # the dGPU render node, never all of /dev/dri
    assert "privileged" not in vulkan
    rocm = yaml.safe_load((gpu / "compose.gpu-rocm.yml").read_text())["services"][
        "dot-llm"
    ]
    assert "/dev/kfd:/dev/kfd" in rocm["devices"]
    cuda = yaml.safe_load((gpu / "compose.gpu-cuda.yml").read_text())["services"][
        "dot-llm"
    ]
    assert (
        cuda["deploy"]["resources"]["reservations"]["devices"][0]["driver"] == "nvidia"
    )


def test_backend_gets_context_seed_and_slots_from_the_same_profile():
    env = SERVICES["dot-backend"]["environment"]
    assert env["DOT_LLM_CONTEXT_LIMIT"].startswith("${DOT_LLM_CONTEXT_LIMIT")
    assert env["DOT_LLM_PARALLEL_SLOTS"].startswith("${DOT_LLM_PARALLEL")
