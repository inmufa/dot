"""In-memory read tracking: session -> {resolved path: (mtime_ns, size)}."""

from pathlib import Path

from dot_sandbox.errors import SandboxError


class ReadTracker:
    def __init__(self) -> None:
        self._seen: dict[str, dict[str, tuple[int, int]]] = {}

    def mark(self, session: str, path: Path) -> None:
        st = path.stat()
        self._seen.setdefault(session, {})[str(path)] = (st.st_mtime_ns, st.st_size)

    def require(self, session: str, path: Path) -> None:
        """Raise 409 read_required unless path was read and is unchanged since."""
        seen = self._seen.get(session, {}).get(str(path))
        if seen is None:
            raise SandboxError(409, "read_required", f"read {path} first")
        st = path.stat()
        if (st.st_mtime_ns, st.st_size) != seen:
            raise SandboxError(
                409, "read_required", f"{path} changed on disk since read"
            )
