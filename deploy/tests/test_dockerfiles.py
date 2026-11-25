"""Static checks for every deploy/docker/*/Dockerfile (no docker needed)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCKER_DIR = ROOT / "deploy" / "docker"
# Build context per image (compose: backend/sandbox/browser use the repo root).
CONTEXTS = {"web": ROOT / "services" / "web-ui"}
# The web image is owned by the web UI; its base is a major tag, not a digest.
DIGEST_EXEMPT = {"web"}
SECRET_WORDS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "PRIVATE_KEY")

DOCKERFILES = sorted(DOCKER_DIR.glob("*/Dockerfile"))


def _logical_lines(text: str) -> list[str]:
    out: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        out.append((buf + line).strip())
        buf = ""
    return out


def _instructions(path: Path) -> list[tuple[str, str]]:
    result = []
    for line in _logical_lines(path.read_text()):
        word, _, rest = line.partition(" ")
        result.append((word.upper(), rest.strip()))
    return result


def _images(path: Path) -> list[str]:
    images = []
    for word, rest in _instructions(path):
        if word == "FROM":
            images.append(re.sub(r"^--\S+\s+", "", rest).split()[0])
        elif word == "COPY":
            match = re.search(r"--from=(\S+)", rest)
            if match:
                images.append(match.group(1))
    return images


def _stage_names(path: Path) -> set[str]:
    return {
        m.group(1)
        for word, rest in _instructions(path)
        if word == "FROM" and (m := re.search(r"\sAS\s+(\S+)$", rest, re.I))
    }


def _ids() -> list[str]:
    return [p.parent.name for p in DOCKERFILES]


def test_dockerfiles_found():
    assert {p.parent.name for p in DOCKERFILES} >= {
        "backend",
        "sandbox",
        "browser",
        "web",
    }


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_final_stage_runs_non_root(path):
    instr = _instructions(path)
    last_from = max(i for i, (w, _) in enumerate(instr) if w == "FROM")
    users = [r for w, r in instr[last_from:] if w == "USER"]
    assert users, f"{path}: final stage has no USER"
    user = users[-1].split(":")[0]
    assert user not in {"root", "0"}, f"{path}: final USER is root"


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_images_have_explicit_non_latest_tags(path):
    stages = _stage_names(path)
    for image in _images(path):
        if image in stages or image == "scratch":
            continue
        ref = image.split("@")[0]
        tag = ref.rsplit(":", 1)[1] if ":" in ref.rsplit("/", 1)[-1] else ""
        assert tag, f"{path}: {image} has no tag"
        assert tag != "latest", f"{path}: {image} uses latest"


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_images_pinned_by_digest(path):
    if path.parent.name in DIGEST_EXEMPT:
        pytest.skip("web image base is pinned by major tag only")
    stages = _stage_names(path)
    for image in _images(path):
        if image not in stages:
            assert re.search(r"@sha256:[0-9a-f]{64}$", image), (
                f"{path}: {image} has no digest"
            )


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_uv_is_pinned(path):
    for image in _images(path):
        if "astral-sh/uv" in image:
            assert re.search(r"/uv:\d+\.\d+\.\d+", image), f"{path}: uv not pinned"


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_copy_sources_exist(path):
    context = CONTEXTS.get(path.parent.name, ROOT)
    for word, rest in _instructions(path):
        if word != "COPY" or "--from=" in rest:
            continue
        args = [a for a in rest.split() if not a.startswith("--")]
        for src in args[:-1]:
            if src == ".":
                continue
            assert (context / src).exists(), f"{path}: COPY source {src} missing"


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_no_secrets_in_env_or_arg(path):
    for word, rest in _instructions(path):
        if word not in {"ENV", "ARG"}:
            continue
        for key, _ in re.findall(r"(\w+)=(\S+)", rest):
            if any(s in key.upper() for s in SECRET_WORDS):
                pytest.fail(f"{path}: {word} {key} carries a value")
        if word == "ARG" and "=" not in rest:
            assert not any(s in rest.upper() for s in SECRET_WORDS)


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_has_healthcheck(path):
    assert any(w == "HEALTHCHECK" for w, _ in _instructions(path))


@pytest.mark.parametrize("path", DOCKERFILES, ids=_ids())
def test_no_pip_install_from_source_or_unlocked_sync(path):
    for word, rest in _instructions(path):
        if word == "RUN" and "uv " in rest:
            if "uv pip install" in rest:
                assert "--require-hashes" in rest, (
                    f"{path}: pip install needs --require-hashes"
                )
            if "uv sync" in rest:
                assert "--frozen" in rest, f"{path}: uv sync without --frozen"


def test_dockerignore_covers_basics():
    lines = (ROOT / ".dockerignore").read_text().split()
    for entry in (".git", ".env", "node_modules", "models", "workspace"):
        assert entry in lines


def test_sandbox_has_hash_pinned_analysis_venv():
    path = ROOT / "deploy/docker/sandbox/Dockerfile"
    text = path.read_text()
    assert "--require-hashes" in text
    assert "/opt/analysis" in text
    env = " ".join(r for w, r in _instructions(path) if w == "ENV")
    assert re.search(r"PATH=/opt/analysis/bin:", env)
    assert "MPLBACKEND=Agg" in env
    pins = (ROOT / "deploy/docker/sandbox/analysis.txt").read_text()
    for pkg in ("pandas==", "numpy==", "matplotlib==", "openpyxl=="):
        assert pkg in pins
    assert "--hash=sha256:" in pins
