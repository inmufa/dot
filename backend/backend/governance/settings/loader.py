"""Load and merge baseline < user < workspace settings; reload when files change."""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from backend.core.exceptions import DomainException
from backend.governance.settings.mcp_spec import McpServerSpec, Scope
from backend.governance.settings.schema import DotSettings

logger = logging.getLogger(__name__)
SETTINGS_INVALID = 3005
_Stamp = tuple[int, int] | None


def _stamp(path: Path | None) -> _Stamp:
    try:
        st = path.stat() if path else None
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size) if st else None


def read_file(path: Path | None, *, required: bool = False) -> DotSettings:
    """Parse one settings file; a missing file is empty, a broken one is an error.

    `required` is for the baseline: without it every deny rule would silently vanish.
    """
    if path is not None and required and not path.is_file():
        logger.error("baseline settings file missing: %s", path)
        raise DomainException(SETTINGS_INVALID)
    if path is None or not path.is_file():
        return DotSettings()
    try:
        return DotSettings.model_validate(json.loads(path.read_text("utf-8")))
    except (ValueError, OSError, ValidationError) as exc:
        # A silently dropped deny rule would be worse than a failed call.
        logger.exception("invalid settings file %s: %s", path, type(exc).__name__)
        raise DomainException(SETTINGS_INVALID) from exc


class SettingsProvider:
    """Merged settings, cached until any of the files changes on disk."""

    def __init__(
        self,
        workspace: Path,
        user_path: Path | None = None,
        default_path: Path | None = None,
    ) -> None:
        self._paths = (
            default_path,
            user_path,
            workspace / ".dot" / "settings.json",
        )
        self._stamps: tuple[_Stamp, ...] | None = None
        self._cached = DotSettings()
        self._mcp: dict[str, tuple[McpServerSpec, Scope]] = {}

    def get(self) -> DotSettings:
        stamps = tuple(_stamp(p) for p in self._paths)
        if stamps != self._stamps:
            base = read_file(self._paths[0], required=True)
            user, work = (read_file(p) for p in self._paths[1:])
            self._cached = work.merged_over(user.merged_over(base))
            self._mcp = {
                **{
                    n: (s, "user")
                    for n, s in {**base.mcp_servers, **user.mcp_servers}.items()
                },
                **{n: (s, "project") for n, s in work.mcp_servers.items()},
            }
            self._stamps = stamps
        return self._cached

    def mcp_servers(self) -> dict[str, tuple[McpServerSpec, Scope]]:
        """Merged MCP servers with their origin; the workspace wins on a name clash."""
        self.get()
        return dict(self._mcp)

    def rules(self) -> list:
        return self.get().rules()
