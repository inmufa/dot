"""Post-edit lint: never fails an edit, returns text or None."""

import asyncio
import shutil
from pathlib import Path

from dot_sandbox.runtime.env import scrubbed_env

TIMEOUT_S = 20
TOOLS: dict[str, list[str]] = {
    ".py": ["ruff", "check", "--output-format", "concise"],
    ".sh": ["bash", "-n"],
    ".js": ["node", "--check"],
}


async def lint_file(path: Path) -> str | None:
    cmd = TOOLS.get(path.suffix)
    if cmd is None or shutil.which(cmd[0]) is None:
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            env=scrubbed_env(),
            cwd=path.parent,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), TIMEOUT_S)
    except (OSError, TimeoutError):
        return None
    if proc.returncode == 0:
        return None
    return out.decode("utf-8", "replace").strip()[:5000] or None
