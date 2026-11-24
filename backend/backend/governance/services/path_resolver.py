"""Resolve symlinks (in the sandbox) so Read/Edit rules judge the real file."""

from typing import Any

from backend.core.exceptions import DomainException
from backend.routing.clients.sandbox_client import SandboxClient

_PATH_KEY = {"Read": "file_path", "Write": "file_path", "Edit": "file_path"}
_PATH_KEY_OPT = {"Grep": "path", "Glob": "path"}


class PathResolver:
    def __init__(self, sandbox: SandboxClient) -> None:
        self._sandbox = sandbox

    async def real_args(
        self, session: str, tool: str, args: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Args with the path replaced by its realpath, or None if unchanged."""
        key = _PATH_KEY.get(tool) or _PATH_KEY_OPT.get(tool)
        raw = args.get(key) if key else None
        if not isinstance(raw, str) or not raw:
            return None
        try:
            r = await self._sandbox.post(session, "/internal/realpath", {"path": raw})
        except DomainException:
            return None  # the tool call itself will report the sandbox problem
        real = r.data.get("path")
        if not r.ok or not isinstance(real, str) or real == raw:
            return None
        return {**args, key: real}
