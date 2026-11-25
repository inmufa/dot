"""Hardware profiles, dotctl and compose.sh: pure file logic, no docker."""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "dotctl", ROOT / "deploy/scripts/dotctl.py"
)
dotctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dotctl)
PROFILES = sorted((ROOT / "deploy/profiles").glob("*.env"))
COMPOSE = ROOT / "deploy/compose"


def good() -> dict[str, str]:
    return dotctl.parse_env((ROOT / "deploy/profiles/rx580-8gb.env").read_text())


def models_dir(tmp_path: Path, registry: str = "") -> Path:
    d = tmp_path / "models"
    d.mkdir()
    (d / "m.gguf").write_bytes(b"0")
    (d / "mmproj-m.gguf").write_bytes(b"0")
    if registry:
        (d / "registry.toml").write_text(registry)
    return d


def test_expected_profiles_exist():
    names = {p.stem for p in PROFILES}
    assert {
        "rx580-8gb",
        "cpu-only",
        "nvidia-24gb",
        "nvidia-48gb-multi",
        "amd-rocm-16gb",
    } <= names


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_every_profile_validates_and_has_an_overlay(path):
    p = dotctl.parse_env(path.read_text())
    dotctl.validate(p)
    backend = p["DOT_GPU_BACKEND"]
    assert backend == "cpu" or (COMPOSE / f"compose.gpu-{backend}.yml").is_file()
    assert "latest" not in p["DOT_LLM_IMAGE_TAG"]


def test_default_profile_matches_the_tuned_rx580_flags():
    p = good()
    assert (p["DOT_LLM_NGL"], p["DOT_LLM_PARALLEL"], p["DOT_LLM_CTX_PER_SLOT"]) == (
        "99",
        "2",
        "32768",
    )
    assert (p["DOT_LLM_KV_K"], p["DOT_LLM_KV_V"], p["DOT_LLM_FA"]) == (
        "q8_0",
        "q8_0",
        "on",
    )
    assert p["DOT_LLM_MEM_LIMIT"] == "1536m"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DOT_GPU_BACKEND", "metal"),
        ("DOT_LLM_IMAGE_TAG", "server-vulkan"),
        ("DOT_LLM_IMAGE_TAG", "server-cuda-b12464"),
        ("DOT_LLM_PARALLEL", "0"),
        ("DOT_LLM_CTX_PER_SLOT", "100"),
        ("DOT_LLM_KV_V", "q9"),
        ("DOT_LLM_FA", "off"),  # q8_0 V cache needs flash attention
        ("DOT_LLM_MEM_LIMIT", "lots"),
        ("DOT_VISION", "igpu"),
        ("DOT_LLM_EXTRA_ARGS", "--x; rm -rf /"),
        ("DOT_TYPO", "1"),
    ],
)
def test_bad_profiles_are_rejected(key, value):
    p = good()
    p[key] = value
    with pytest.raises(dotctl.ProfileError):
        dotctl.validate(p)


def test_cpu_backend_rejects_gpu_layers_and_gpu_projector():
    p = dotctl.parse_env((ROOT / "deploy/profiles/cpu-only.env").read_text())
    with pytest.raises(dotctl.ProfileError):
        dotctl.validate({**p, "DOT_LLM_NGL": "10"})
    with pytest.raises(dotctl.ProfileError):
        dotctl.validate({**p, "DOT_VISION": "gpu"})


def test_derive_total_context_and_projector_placement(tmp_path):
    reg = '[[model]]\nfile = "m.gguf"\nmmproj = "mmproj-m.gguf"\n'
    m = models_dir(tmp_path, reg)
    out, warns = dotctl.derive({**good(), "DOT_VISION": "cpu"}, "x", "m.gguf", m)
    assert out["DOT_LLM_CTX"] == "65536"
    assert out["DOT_LLM_CONTEXT_LIMIT"] == "32768"
    assert out["DOT_LLM_MMPROJ_ARGS"] == "--mmproj /models/mmproj-m.gguf -mmdev none"
    assert out["DOT_LLM_MEM_LIMIT"] == "4g"
    assert not warns
    gpu = {**good(), "DOT_VISION": "gpu"}
    assert (
        dotctl.derive(gpu, "x", "m.gguf", m)[0]["DOT_LLM_MMPROJ_ARGS"]
        == "--mmproj /models/mmproj-m.gguf"
    )


def test_unknown_model_degrades_to_text_only(tmp_path):
    out, warns = dotctl.derive(
        {**good(), "DOT_VISION": "cpu"}, "x", "m.gguf", models_dir(tmp_path)
    )
    assert out["DOT_LLM_MMPROJ_ARGS"] == ""
    assert out["DOT_LLM_MEM_LIMIT"] == "1536m"
    assert any("text-only" in w for w in warns)


def test_context_is_clamped_to_the_model_maximum(tmp_path):
    m = models_dir(tmp_path, '[[model]]\nfile = "m.gguf"\ncontext_max = 8192\n')
    out, warns = dotctl.derive(good(), "x", "m.gguf", m)
    assert (out["DOT_LLM_CONTEXT_LIMIT"], out["DOT_LLM_CTX"]) == ("8192", "16384")
    assert any("clamped" in w for w in warns)


def test_write_env_keeps_foreign_lines_and_replaces_managed(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nDOT_LLM_CONTEXT_LIMIT=111\nDOT_MODEL_FILE=old.gguf\nB=2\n")
    dotctl.write_env(
        env, {"DOT_LLM_CONTEXT_LIMIT": "5"}, {"DOT_MODEL_FILE": "new.gguf"}
    )
    dotctl.write_env(env, {"DOT_LLM_CONTEXT_LIMIT": "6"}, {})
    text = env.read_text()
    assert text.count("DOT_LLM_CONTEXT_LIMIT") == 1
    assert "DOT_LLM_CONTEXT_LIMIT=6" in text
    assert "A=1" in text
    assert "B=2" in text
    assert "DOT_MODEL_FILE=new.gguf" in text


def test_profile_and_model_commands_end_to_end(tmp_path):
    root = tmp_path
    (root / "deploy").mkdir()
    (root / "deploy/profiles").symlink_to(ROOT / "deploy/profiles")
    m = models_dir(
        root, '[[model]]\nfile = "m.gguf"\nname = "My M"\nmmproj = "mmproj-m.gguf"\n'
    )
    (m / "other.gguf").write_bytes(b"0")
    env = root / ".env"
    env.write_text(
        "DOT_GPU_RENDER_NODE=/dev/null\nDOT_VIDEO_GID=1\nDOT_RENDER_GID=2\nDOT_MODEL_FILE=m.gguf\n"
    )
    dotctl.cmd_profile("rx580-8gb", root, env, {"DOT_VISION": "cpu"})
    assert (
        "DOT_LLM_MMPROJ_ARGS=--mmproj /models/mmproj-m.gguf -mmdev none"
        in env.read_text()
    )
    model, _ = dotctl.cmd_model("other", root, env)
    assert model == "other.gguf"
    text = env.read_text()
    assert "DOT_MODEL_FILE=other.gguf" in text
    assert "DOT_LLM_MMPROJ_ARGS=\n" in text
    assert dotctl.cmd_model("my m", root, env)[0] == "m.gguf"
    for bad in ("../x", "mmproj-m", "nope", ""):
        with pytest.raises(dotctl.ProfileError):
            dotctl.cmd_model(bad, root, env)


def test_vulkan_profile_needs_host_ids(tmp_path):
    root = tmp_path
    (root / "deploy").mkdir()
    (root / "deploy/profiles").symlink_to(ROOT / "deploy/profiles")
    (root / "models").mkdir()
    env = root / ".env"
    env.write_text("DOT_MODEL_FILE=m.gguf\n")
    with pytest.raises(dotctl.ProfileError, match="DOT_GPU_RENDER_NODE"):
        dotctl.cmd_profile("rx580-8gb", root, env)
    dotctl.cmd_profile("cpu-only", root, env)  # no host ids needed


@pytest.mark.parametrize(
    ("backend", "overlay"),
    [
        ("vulkan", "gpu-vulkan"),
        ("cuda", "gpu-cuda"),
        ("rocm", "gpu-rocm"),
        ("cpu", None),
    ],
)
def test_compose_sh_picks_the_overlay(backend, overlay, tmp_path):
    (tmp_path / "deploy/scripts").mkdir(parents=True)
    script = tmp_path / "deploy/scripts/compose.sh"
    script.write_text((ROOT / "deploy/scripts/compose.sh").read_text())
    (tmp_path / ".env").write_text(f"DOT_GPU_BACKEND={backend}\n")
    out = subprocess.run(  # noqa: S603
        ["bash", str(script), "up", "-d"],  # noqa: S607
        capture_output=True,
        text=True,
        env={**os.environ, "DOT_COMPOSE_DRY": "1"},
        check=True,
    ).stdout
    assert "compose.base.yml" in out
    assert (f"compose.{overlay}.yml" in out) if overlay else ("compose.gpu-" not in out)


def test_compose_sh_rejects_a_bad_backend(tmp_path):
    (tmp_path / "deploy/scripts").mkdir(parents=True)
    (tmp_path / "deploy/scripts/compose.sh").write_text(
        (ROOT / "deploy/scripts/compose.sh").read_text()
    )
    (tmp_path / ".env").write_text("DOT_GPU_BACKEND=metal\n")
    r = subprocess.run(  # noqa: S603
        ["bash", str(tmp_path / "deploy/scripts/compose.sh"), "ps"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2


@pytest.mark.parametrize(
    "overlay", sorted(COMPOSE.glob("compose.gpu-*.yml")), ids=lambda p: p.stem
)
def test_overlays_only_touch_the_llm(overlay):
    data = yaml.safe_load(overlay.read_text())
    assert set(data["services"]) == {"dot-llm"}
    assert "privileged" not in data["services"]["dot-llm"]
