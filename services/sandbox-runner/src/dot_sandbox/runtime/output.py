"""Output clipping (head+tail) and spill files."""

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

LIMIT = 30_000
HALF = LIMIT // 2
WHOLE_READ_MAX = 1_000_000


@dataclass
class Clipped:
    text: str
    truncated: bool


def clip_text(text: str) -> Clipped:
    if len(text) <= LIMIT:
        return Clipped(text, truncated=False)
    cut = len(text) - LIMIT
    return Clipped(
        f"{text[:HALF]}\n... [{cut} chars truncated] ...\n{text[-HALF:]}",
        truncated=True,
    )


def clip_file(path: Path) -> Clipped:
    """Read a captured stream file without loading huge outputs into memory."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size <= WHOLE_READ_MAX:
            return clip_text(fh.read().decode("utf-8", "replace"))
        head = fh.read(HALF)
        fh.seek(size - HALF)
        tail = fh.read(HALF)
    cut = size - 2 * HALF
    body = f"{head.decode('utf-8', 'replace')}\n... [{cut} bytes truncated] ...\n"
    return Clipped(body + tail.decode("utf-8", "replace"), truncated=True)


def spill(root: Path, out: Path, err: Path) -> Path:
    """Copy full stdout/stderr into <workspace>/.dot/tool_outputs/<id>.log."""
    target_dir = root / ".dot" / "tool_outputs"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex[:12]}.log"
    with target.open("wb") as dst:
        for label, src in (("stdout", out), ("stderr", err)):
            dst.write(f"--- {label} ---\n".encode())
            with src.open("rb") as fh:
                shutil.copyfileobj(fh, dst)
            dst.write(b"\n")
    return target
