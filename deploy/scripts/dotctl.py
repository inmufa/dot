# ruff: noqa: EM101, EM102, C901, PLR0912
"""Hardware profiles and model selection for the llama stack. Stdlib only.

  dotctl.py profile NAME [--set KEY=VALUE]   validate deploy/profiles/NAME.env, write it to .env
  dotctl.py model NAME     pick a model (file, stem or registry name), update .env

Everything profile-derived lives in a managed block of .env; the rest is untouched.
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BEGIN = "# >>> dot profile (managed by `make profile`, do not edit) >>>"
END = "# <<< dot profile <<<"
BACKENDS = ("vulkan", "cuda", "rocm", "cpu")
TAG_PREFIX = {
    "vulkan": "server-vulkan-",
    "cuda": "server-cuda",
    "rocm": "server-rocm-",
    "cpu": "server-",
}
KV_TYPES = {"f32", "f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"}
PROFILE_KEYS = {
    "DOT_GPU_BACKEND", "DOT_LLM_IMAGE_TAG", "DOT_LLM_NGL", "DOT_LLM_PARALLEL",
    "DOT_LLM_CTX_PER_SLOT", "DOT_LLM_KV_K", "DOT_LLM_KV_V", "DOT_LLM_FA",
    "DOT_LLM_MEM_LIMIT", "DOT_LLM_MEM_LIMIT_VISION", "DOT_VISION", "DOT_LLM_EXTRA_ARGS",
    "DOT_VOICE", "DOT_VOICE_THREADS", "DOT_CHAT_RATE_PER_MIN", "DOT_CHAT_RATE_BURST",
    "DOT_VRAM_SYSFS_DIR", "DOT_LLM_CONTEXT_CAP", "DOT_COMPACT_MAX_TOKENS",
}  # fmt: skip
DERIVED_KEYS = {
    "DOT_PROFILE", "DOT_LLM_CTX", "DOT_LLM_CONTEXT_LIMIT", "DOT_LLM_MMPROJ_ARGS",
}  # fmt: skip
MANAGED = PROFILE_KEYS | DERIVED_KEYS | {"DOT_MMPROJ_FILE"}


class ProfileError(Exception):
    pass


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("\"'")
    return out


def _int(values: dict[str, str], key: str, lo: int, hi: int) -> int:
    raw = values.get(key, "")
    if not re.fullmatch(r"\d+", raw) or not lo <= int(raw) <= hi:
        msg = f"{key} must be an integer in {lo}..{hi}, got {raw!r}"
        raise ProfileError(msg)
    return int(raw)


def validate(p: dict[str, str]) -> list[str]:
    """Raise ProfileError on a bad profile; return warnings."""
    warns: list[str] = []
    unknown = sorted(set(p) - PROFILE_KEYS)
    if unknown:
        raise ProfileError("unknown keys: " + ", ".join(unknown))
    backend = p.get("DOT_GPU_BACKEND", "")
    if backend not in BACKENDS:
        raise ProfileError(f"DOT_GPU_BACKEND must be one of {', '.join(BACKENDS)}")
    tag = p.get("DOT_LLM_IMAGE_TAG", "")
    if not tag.startswith(TAG_PREFIX[backend]) or not re.search(r"b\d+$", tag):
        raise ProfileError(
            f"DOT_LLM_IMAGE_TAG {tag!r} must be a pinned {backend} tag "
            f"like {TAG_PREFIX[backend].rstrip('-')}-b12464"
        )
    if backend != "cpu" and tag.startswith("server-b"):
        raise ProfileError("the CPU image tag does not match a GPU backend")
    ngl = _int(p, "DOT_LLM_NGL", 0, 999)
    if backend == "cpu" and ngl:
        raise ProfileError("DOT_LLM_NGL must be 0 on the cpu backend")
    _int(p, "DOT_LLM_PARALLEL", 1, 64)
    ctx = _int(p, "DOT_LLM_CTX_PER_SLOT", 512, 4_194_304)
    if ctx % 256:
        warns.append("DOT_LLM_CTX_PER_SLOT is not a multiple of 256")
    for key in ("DOT_LLM_KV_K", "DOT_LLM_KV_V"):
        if p.get(key) not in KV_TYPES:
            raise ProfileError(f"{key} must be one of {', '.join(sorted(KV_TYPES))}")
    fa = p.get("DOT_LLM_FA")
    if fa not in ("on", "off", "auto"):
        raise ProfileError("DOT_LLM_FA must be on, off or auto")
    if p["DOT_LLM_KV_V"] not in ("f32", "f16", "bf16") and fa != "on":
        raise ProfileError("a quantized V cache needs DOT_LLM_FA=on")
    for key in ("DOT_LLM_MEM_LIMIT", "DOT_LLM_MEM_LIMIT_VISION"):
        if not re.fullmatch(r"[1-9]\d*[bkmg]", p.get(key, "")):
            raise ProfileError(f"{key} must look like 1536m or 8g")
    vision = p.get("DOT_VISION")
    if vision not in ("off", "cpu", "gpu"):
        raise ProfileError("DOT_VISION must be off, cpu or gpu")
    if vision == "gpu" and backend == "cpu":
        raise ProfileError("DOT_VISION=gpu needs a GPU backend")
    if p.get("DOT_VOICE") not in ("on", "off"):
        raise ProfileError("DOT_VOICE must be on or off")
    _int(p, "DOT_VOICE_THREADS", 1, 128)
    _int(p, "DOT_CHAT_RATE_BURST", 1, 10_000)
    if not re.fullmatch(r"\d+(\.\d+)?", p.get("DOT_CHAT_RATE_PER_MIN", "")):
        raise ProfileError("DOT_CHAT_RATE_PER_MIN must be a positive number")
    for key in ("DOT_LLM_CONTEXT_CAP", "DOT_COMPACT_MAX_TOKENS"):
        if p.get(key) and not re.fullmatch(r"\d+", p[key]):
            raise ProfileError(f"{key} must be an integer or empty")
    if re.search(r"[;&|`$<>\n]", p.get("DOT_LLM_EXTRA_ARGS", "")):
        raise ProfileError("DOT_LLM_EXTRA_ARGS has shell metacharacters")
    return warns


def load_registry(models: Path) -> dict[str, dict]:
    try:
        data = tomllib.loads((models / "registry.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    items = data.get("model")
    return {m["file"]: m for m in items if isinstance(m, dict) and isinstance(m.get("file"), str)} if isinstance(items, list) else {}  # fmt: skip


def derive(
    profile: dict[str, str], name: str, model_file: str, models: Path
) -> tuple[dict[str, str], list[str]]:
    """Managed-block values for a profile and the current model (pure but for file checks)."""
    warns = validate(profile)
    out = dict(profile)
    per_slot = int(profile["DOT_LLM_CTX_PER_SLOT"])
    entry = load_registry(models).get(model_file, {})
    cmax = entry.get("context_max")
    if isinstance(cmax, int) and per_slot > cmax:
        warns.append(f"context per slot {per_slot} exceeds the model's {cmax}: clamped")
        per_slot = cmax
    parallel = int(profile["DOT_LLM_PARALLEL"])
    out["DOT_PROFILE"] = name
    out["DOT_LLM_CTX"] = str(per_slot * parallel)
    out["DOT_LLM_CONTEXT_LIMIT"] = str(per_slot)
    args, vision = "", profile["DOT_VISION"]
    mmproj = entry.get("mmproj")
    if vision != "off":
        if isinstance(mmproj, str) and (models / mmproj).is_file():
            args = f"--mmproj /models/{mmproj}" + (
                " -mmdev none" if vision == "cpu" else ""
            )
            out["DOT_MMPROJ_FILE"] = mmproj
            out["DOT_LLM_MEM_LIMIT"] = profile["DOT_LLM_MEM_LIMIT_VISION"]
        else:
            warns.append(
                f"no projector for {model_file or '(no model)'}: running text-only"
            )
    out["DOT_LLM_MMPROJ_ARGS"] = args
    return out, warns


def read_profile(name: str, root: Path = ROOT) -> dict[str, str]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name):
        raise ProfileError(f"bad profile name {name!r}")
    path = root / "deploy/profiles" / f"{name}.env"
    if not path.is_file():
        have = sorted(p.stem for p in (root / "deploy/profiles").glob("*.env"))
        raise ProfileError(f"no profile {name!r}; available: {', '.join(have)}")
    return parse_env(path.read_text())


def write_env(
    env_path: Path, managed: dict[str, str], set_keys: dict[str, str]
) -> None:
    """Rewrite .env: managed block replaced, duplicates of its keys dropped, set_keys in place."""
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    kept: list[str] = []
    inside = False
    for line in lines:
        if line == BEGIN:
            inside = True
        elif line == END:
            inside = False
        elif not inside:
            key = line.partition("=")[0].strip()
            if key in managed or key in MANAGED:
                continue
            kept.append(f"{key}={set_keys.pop(key)}" if key in set_keys else line)
    kept.extend(f"{k}={v}" for k, v in set_keys.items())
    block = [BEGIN, *(f"{k}={v}" for k, v in sorted(managed.items())), END]
    text = "\n".join([*kept, *([""] if kept and kept[-1] else []), *block]) + "\n"
    env_path.write_text(text)


def host_checks(env: dict[str, str], backend: str) -> list[str]:
    need = {"vulkan": ["DOT_GPU_RENDER_NODE", "DOT_VIDEO_GID", "DOT_RENDER_GID"],
            "rocm": ["DOT_VIDEO_GID", "DOT_RENDER_GID"]}.get(backend, [])  # fmt: skip
    missing = [k for k in need if not env.get(k)]
    if missing:
        raise ProfileError(f"set {', '.join(missing)} in .env first (see .env.example)")
    warns = []
    if backend == "vulkan" and not Path(env["DOT_GPU_RENDER_NODE"]).exists():
        warns.append(f"{env['DOT_GPU_RENDER_NODE']} does not exist on this host")
    if backend == "rocm" and not Path("/dev/kfd").exists():
        warns.append("/dev/kfd does not exist on this host")
    return warns


def cmd_profile(
    name: str, root: Path, env_path: Path, overrides: dict[str, str] | None = None
) -> list[str]:
    profile = {**read_profile(name, root), **(overrides or {})}
    env = parse_env(env_path.read_text()) if env_path.exists() else {}
    model = env.get("DOT_MODEL_FILE", "")
    managed, warns = derive(profile, name, model, root / "models")
    warns += host_checks(env, profile["DOT_GPU_BACKEND"])
    write_env(env_path, managed, {})
    return warns


def resolve_model(name: str, models: Path) -> str:
    if "/" in name or name.startswith("..") or not name:
        raise ProfileError("NAME must be a file name, stem or registry name")
    files = sorted(
        p.name for p in models.glob("*.gguf") if not p.name.startswith("mmproj")
    )
    reg = load_registry(models)
    low = name.lower()
    for f in files:
        if f == name or Path(f).stem == name:
            return f
    for f in files:
        if str(reg.get(f, {}).get("name", "")).lower() == low:
            return f
    raise ProfileError(
        f"no model {name!r} in ./models; have: {', '.join(files) or 'none'}"
    )


def cmd_model(name: str, root: Path, env_path: Path) -> tuple[str, list[str]]:
    if not env_path.exists():
        raise ProfileError("missing .env (copy .env.example)")
    model = resolve_model(name, root / "models")
    env = parse_env(env_path.read_text())
    warns: list[str] = []
    if prof := env.get("DOT_PROFILE"):
        managed, warns = derive(read_profile(prof, root), prof, model, root / "models")
        write_env(env_path, managed, {"DOT_MODEL_FILE": model})
    else:
        write_env(env_path, {}, {"DOT_MODEL_FILE": model})
        warns.append(
            "no profile applied (make profile NAME=...): vision and context unchanged"
        )
    return model, warns


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("profile", "model"))
    ap.add_argument("name")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--env", type=Path, default=None)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    a = ap.parse_args(argv)
    env_path = a.env or a.root / ".env"
    try:
        if a.cmd == "profile":
            over = dict(kv.split("=", 1) for kv in a.set if "=" in kv)
            warns = cmd_profile(a.name, a.root, env_path, over)
            print(f"profile {a.name} written to {env_path.name}")
        else:
            model, warns = cmd_model(a.name, a.root, env_path)
            print(f"DOT_MODEL_FILE={model}")
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for w in warns:
        print(f"warning: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
