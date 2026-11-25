"""Voice worker deploy invariants: compose service, Dockerfile, DOT_VOICE wiring."""

import os
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "deploy/compose/compose.base.yml").read_text())
DOCKERFILE = (ROOT / "deploy/docker/voice/Dockerfile").read_text()


def test_voice_service_is_isolated():
    svc = COMPOSE["services"]["dot-voice"]
    assert svc["profiles"] == ["voice"]
    assert svc["networks"] == ["dot-voice-link"]
    assert COMPOSE["networks"]["dot-voice-link"]["internal"] is True
    assert "ports" not in svc
    assert svc["cap_drop"] == ["ALL"]
    assert svc["read_only"] is True
    assert "no-new-privileges:true" in svc["security_opt"]
    assert svc["mem_limit"] == "3g"
    assert "healthcheck" in svc


def test_models_mounted_read_only():
    vols = COMPOSE["services"]["dot-voice"]["volumes"]
    assert vols == ["../../models/voice:/models/voice:ro"]


def test_backend_reaches_voice_only_over_the_link():
    backend = COMPOSE["services"]["dot-backend"]
    assert "dot-voice-link" in backend["networks"]
    assert backend["environment"]["DOT_VOICE_URL"] == "http://dot-voice:8092"
    assert "DOT_VOICE_TOKEN" in backend["environment"]
    for name, svc in COMPOSE["services"].items():
        if name not in {"dot-backend", "dot-voice"}:
            assert "dot-voice-link" not in svc.get("networks", [])


def test_dockerfile_locked_and_no_secrets():
    assert "uv sync --frozen --no-dev" in DOCKERFILE
    assert "services/voice-worker/uv.lock" in DOCKERFILE
    assert "TOKEN" not in DOCKERFILE
    assert "COPY models" not in DOCKERFILE


def test_voice_lock_pins_sherpa():
    lock = (ROOT / "services/voice-worker/uv.lock").read_text()
    assert 'name = "sherpa-onnx"\nversion = "2.0.3"' in lock


def _compose_cmd(env_text: str) -> str:
    # A scratch repo copy of compose.sh and an .env decide the profile.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "deploy/scripts").mkdir(parents=True)
        (root / "deploy/compose").mkdir(parents=True)
        (root / "deploy/compose/compose.base.yml").write_text("services: {}\n")
        src = (ROOT / "deploy/scripts/compose.sh").read_text()
        (root / "deploy/scripts/compose.sh").write_text(src)
        (root / ".env").write_text(env_text)
        done = subprocess.run(  # noqa: S603
            ["bash", str(root / "deploy/scripts/compose.sh"), "up"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "DOT_COMPOSE_DRY": "1"},
        )
        return done.stdout + done.stderr


def test_dot_voice_on_enables_profile_when_token_set():
    assert "--profile voice" in _compose_cmd("DOT_VOICE=on\nDOT_VOICE_TOKEN=abc\n")


def test_dot_voice_off_or_tokenless_stays_off():
    assert "--profile voice" not in _compose_cmd("DOT_VOICE=off\nDOT_VOICE_TOKEN=abc\n")
    out = _compose_cmd("DOT_VOICE=on\nDOT_VOICE_TOKEN=\n")
    assert "--profile voice" not in out
    assert "voice stays off" in out
