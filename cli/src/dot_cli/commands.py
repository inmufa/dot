"""Slash command parsing."""

from dot_contracts.permissions import PermissionMode

HELP_TEXT = (
    "/mode <name>  switch permission mode ("
    + ", ".join(m.value for m in PermissionMode)
    + ")\n/stop  cancel the running turn\n/new  start a new session\n"
    "/help  this text\n/quit  exit\n"
    "approval keys: a allow, s always this session, r reject"
)


def parse_command(text: str) -> tuple[str, str] | None:
    """Return (name, argument) for `/name arg`, else None."""
    if not text.startswith("/"):
        return None
    name, _, arg = text[1:].partition(" ")
    return name.lower(), arg.strip()
