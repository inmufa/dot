"""Path jail: every path must resolve inside the workspace root."""

from pathlib import Path

from dot_sandbox.errors import SandboxError

_state = {"unrestricted": False}


def configure(*, unrestricted: bool) -> None:
    """Host mode switch, set once at app start."""
    _state["unrestricted"] = unrestricted


def resolve(root: Path, raw: str | None) -> Path:
    """Resolve symlinks and `..`, reject anything outside root with 403."""
    base = root.resolve()
    try:
        candidate = Path(raw) if raw else base
        if not candidate.is_absolute():
            candidate = base / candidate
        real = candidate.resolve()
    except (ValueError, OSError, RuntimeError) as exc:
        raise SandboxError(400, "invalid_path", str(exc)) from exc
    if _state["unrestricted"]:
        return real
    if real != base and not real.is_relative_to(base):
        raise SandboxError(
            403,
            "outside_workspace",
            f"{raw} is outside the workspace. It is probably a file on the owner's computer, which the sandbox cannot see: ask the owner to attach it or paste its text, do not search for it.",
        )
    return real


def inside(root: Path, path: Path) -> bool:
    """True when path (symlinks resolved) stays inside root."""
    if _state["unrestricted"]:
        return True
    try:
        real = path.resolve()
    except (OSError, RuntimeError):
        return False
    base = root.resolve()
    return real == base or real.is_relative_to(base)


def guard_write(root: Path, path: Path) -> None:
    """Refuse fs writes into the runner's own `.dot/` state (spill files etc.)."""
    if path.is_relative_to(root.resolve() / ".dot"):
        raise SandboxError(403, "protected_path", ".dot/ is managed by the sandbox")
