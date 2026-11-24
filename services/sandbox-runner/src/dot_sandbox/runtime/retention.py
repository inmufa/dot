"""Retention for sandbox-owned state: checkpoints (age + size per session), spill files.

Pruned checkpoint ids are never reused: the highest pruned id is kept in a `.max`
marker, so an old backend row can never restore a newer, unrelated snapshot.
"""

import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path

DAY_S = 86_400
MARKER = ".max"
LOCK = threading.Lock()  # prune and restore never overlap


@dataclass
class Report:
    checkpoints_removed: int = 0
    outputs_removed: int = 0
    bytes_freed: int = 0


def _size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _stamp(path: Path) -> float:
    meta = path / "meta.json"
    return (meta if meta.exists() else path).stat().st_mtime


def read_marker(sdir: Path) -> int:
    try:
        return int((sdir / MARKER).read_text().strip())
    except (OSError, ValueError):
        return 0


def _drop(sdir: Path, entry: Path, report: Report) -> None:
    n = int(entry.name)
    if n > read_marker(sdir):
        (sdir / MARKER).write_text(str(n))
    report.bytes_freed += _size(entry)
    shutil.rmtree(entry, ignore_errors=True)
    report.checkpoints_removed += 1


def _prune_session(
    sdir: Path, cutoff: float, max_bytes: int, report: Report, protect: int
) -> None:
    entries = sorted(
        (
            p
            for p in sdir.iterdir()
            if p.is_dir() and not p.is_symlink() and p.name.isdigit()
        ),
        key=lambda p: int(p.name),
    )
    shielded = {e.name for e in entries[len(entries) - protect :]} if protect else set()
    keep: list[tuple[Path, int]] = []
    for entry in entries:
        if entry.name not in shielded and _stamp(entry) < cutoff:
            _drop(sdir, entry, report)
        else:
            keep.append((entry, _size(entry)))
    total = sum(size for _, size in keep)
    for entry, size in keep:  # oldest first
        if total <= max_bytes:
            break
        if entry.name in shielded:
            continue
        total -= size
        _drop(sdir, entry, report)


def _prune_outputs(root: Path, cutoff: float, report: Report) -> None:
    out = root / ".dot" / "tool_outputs"
    if out.is_symlink() or not out.is_dir():
        return
    for f in out.iterdir():
        if f.is_file() and not f.is_symlink() and f.stat().st_mtime < cutoff:
            report.bytes_freed += f.stat().st_size
            f.unlink(missing_ok=True)
            report.outputs_removed += 1


def prune(  # noqa: PLR0913
    root: Path,
    *,
    checkpoint_days: float,
    checkpoint_max_bytes: int,
    outputs_days: float,
    protect_sessions: frozenset[str] = frozenset(),
    protect_last: int = 0,
    now: float | None = None,
) -> Report:
    """Delete old state. The newest `protect_last` checkpoints of live sessions stay."""
    now = time.time() if now is None else now
    report = Report()
    with LOCK:
        base = root.resolve() / ".dot" / "checkpoints"
        # A symlinked base or session dir could point anywhere: never follow it.
        if base.is_dir() and not base.is_symlink():
            cutoff = now - checkpoint_days * DAY_S
            for sdir in (
                p for p in base.iterdir() if p.is_dir() and not p.is_symlink()
            ):
                keep = protect_last if sdir.name in protect_sessions else 0
                _prune_session(sdir, cutoff, checkpoint_max_bytes, report, keep)
                if not any(sdir.iterdir()):
                    sdir.rmdir()
        _prune_outputs(root.resolve(), now - outputs_days * DAY_S, report)
    return report
