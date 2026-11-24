"""Per-session set of activated deferred tools, in activation order.

In memory only: after a restart the model gets "not activated" for a deferred
tool and simply calls ToolSearch again (the prompt cache is cold then anyway).
"""

from backend.core.session_ids import root_of


class ActivationStore:
    def __init__(self) -> None:
        self._names: dict[str, list[str]] = {}

    def names(self, session_id: str) -> list[str]:
        return list(self._names.get(root_of(session_id), []))

    def activate(self, session_id: str, names: list[str]) -> list[str]:
        """Append names not yet active; returns the ones that were new."""
        have = self._names.setdefault(root_of(session_id), [])
        new = [n for n in dict.fromkeys(names) if n not in have]
        have.extend(new)
        return new

    def reset(self, session_id: str) -> None:
        self._names.pop(root_of(session_id), None)
