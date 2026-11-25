"""Pre-write file snapshots under <workspace>/.dot/checkpoints/<session>/<n>/."""

import json
import re
import shutil
from pathlib import Path

from dot_sandbox.errors import SandboxError
from dot_sandbox.files import _atomic_write
from dot_sandbox.jail import guard_write, resolve
from dot_sandbox.runtime.retention import LOCK, read_marker

_SESSION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_META = "meta.json"
_CONTENT = "content"


def _session_dir(root: Path, session: str) -> Path:
    if not _SESSION.match(session):
        raise SandboxError(400, "invalid_session", "bad session id")
    return root.resolve() / ".dot" / "checkpoints" / session


def _allocate(sdir: Path) -> tuple[int, Path]:
    sdir.mkdir(parents=True, exist_ok=True)
    n = max((int(p.name) for p in sdir.iterdir() if p.name.isdigit()), default=0)
    n = max(n, read_marker(sdir))  # ids pruned by retention are never reused
    while True:
        n += 1
        target = sdir / str(n)
        try:
            target.mkdir()
        except FileExistsError:
            continue
        return n, target


def save(root: Path, session: str, raw_path: str, max_bytes: int) -> tuple[str, bool]:
    """Store the current content of a path (or a 'did not exist' marker)."""
    path = resolve(root, raw_path)
    guard_write(root, path)
    existed = path.exists()
    if existed:
        if not path.is_file():
            raise SandboxError(400, "not_regular", f"{path} is not a regular file")
        if path.stat().st_size > max_bytes:
            raise SandboxError(413, "file_too_large", f"{path} is too large")
    n, target = _allocate(_session_dir(root, session))
    if existed:
        shutil.copyfile(path, target / _CONTENT)
        (target / _CONTENT).chmod(
            0o444
        )  # shells cannot overwrite a snapshot by accident
    (target / _META).write_text(json.dumps({"path": str(path), "existed": existed}))
    return str(n), existed


def restore(
    root: Path, session: str, checkpoint_id: str, *, dry_run: bool = False
) -> tuple[str, str]:
    """Put a snapshot back; returns (path, 'restored' | 'deleted').

    `dry_run` only proves the snapshot is intact, so a caller can check every
    checkpoint of a rewind before changing any file.
    """
    if not checkpoint_id.isdigit():
        raise SandboxError(400, "invalid_checkpoint", "bad checkpoint id")
    target = _session_dir(root, session) / checkpoint_id
    with LOCK:
        try:
            meta = json.loads((target / _META).read_text())
            data = (target / _CONTENT).read_bytes() if meta["existed"] else b""
        except (OSError, ValueError, KeyError) as exc:
            raise SandboxError(404, "no_checkpoint", "checkpoint not found") from exc
        path = resolve(root, meta["path"])
        guard_write(root, path)
        action = "restored" if meta["existed"] else "deleted"
        if dry_run:
            return str(path), action
        if meta["existed"]:
            _atomic_write(path, data)
        else:
            path.unlink(missing_ok=True)
        return str(path), action


def peek(path: Path, max_bytes: int) -> tuple[bool, str | None]:
    """(exists, text) without marking the file as read; text None if unusable."""
    if not path.is_file():
        return path.exists(), None
    if path.stat().st_size > max_bytes:
        return True, None
    try:
        return True, path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return True, None
