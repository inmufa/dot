"""Decide whether a skill can run here; the reason is shown, never hidden."""

from collections.abc import Callable
from dataclasses import dataclass, field

from backend.cognition.services.skills.model import Requires


@dataclass
class Environment:
    tools: set[str] = field(default_factory=set)
    mcp: set[str] = field(default_factory=set)
    binaries: set[str] | None = None  # found in the sandbox; None = not checked yet
    which: Callable[[str], str | None] | None = None  # override (tests)

    def has_binary(self, name: str) -> bool:
        if self.which is not None:
            return bool(self.which(name))
        return self.binaries is not None and name in self.binaries


def unavailable_reason(req: Requires, env: Environment) -> str | None:
    missing = []
    if tools := [t for t in req.tools if t not in env.tools]:
        missing.append(f"missing tools: {', '.join(tools)}")
    if mcp := [m for m in req.mcp if m not in env.mcp]:
        missing.append(f"missing MCP servers: {', '.join(mcp)}")
    if bins := [b for b in req.binaries if not env.has_binary(b)]:
        unchecked = env.which is None and env.binaries is None
        note = " (sandbox not reachable, could not check)" if unchecked else ""
        missing.append(f"missing binaries: {', '.join(bins)}{note}")
    return "; ".join(missing) or None
