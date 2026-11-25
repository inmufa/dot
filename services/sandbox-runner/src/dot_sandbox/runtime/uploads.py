# ruff: noqa: TRY301, ASYNC240
"""Binary uploads into `<workspace>/uploads/<session>/` (backend-only)."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

from dot_sandbox.errors import SandboxError


def upload_target(root: Path, real: Path) -> Path:
    base = (root.resolve() / "uploads").resolve()
    if not real.is_relative_to(base) or real == base:
        raise SandboxError(403, "protected_path", "uploads go under uploads/")
    return base


async def write_stream(real: Path, chunks: AsyncIterator[bytes], max_bytes: int) -> int:
    """Create `real` exclusively (never overwrite, never follow a final symlink)."""
    real.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    try:
        fd = os.open(real, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError as exc:
        raise SandboxError(409, "exists", "file already exists") from exc
    size = 0
    try:
        with os.fdopen(fd, "wb") as fh:
            async for chunk in chunks:
                size += len(chunk)
                if size > max_bytes:
                    raise SandboxError(413, "too_large", f"over {max_bytes} bytes")
                fh.write(chunk)
    except BaseException:
        real.unlink(missing_ok=True)
        raise
    return size
