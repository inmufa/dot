"""Server config -> concrete env, headers and URL checks. `${VAR}` reads an allowlist only."""

import os
import re
from collections.abc import Mapping

from backend.governance.settings.mcp_spec import McpServerSpec

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class McpConfigError(Exception):
    """The server config cannot be used (bad reference, blocked URL)."""


def allowlist(raw: str) -> frozenset[str]:
    return frozenset(n.strip() for n in raw.split(",") if n.strip())


def expand(
    value: str, allowed: frozenset[str], environ: Mapping[str, str] | None = None
) -> str:
    """Replace `${NAME}`; a name outside the allowlist (or unset) is an error."""
    env = os.environ if environ is None else environ

    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in allowed:
            msg = f"variable {name} is not in DOT_MCP_ENV_ALLOWLIST"
            raise McpConfigError(msg)
        if name not in env:
            msg = f"variable {name} is not set"
            raise McpConfigError(msg)
        return env[name]

    return _VAR.sub(sub, value)


def resolve_maps(
    spec: McpServerSpec,
    allowed: frozenset[str],
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """(env, headers) with references expanded."""
    env = {k: expand(v, allowed, environ) for k, v in spec.env.items()}
    headers = {k: expand(v, allowed, environ) for k, v in spec.headers.items()}
    return env, headers
