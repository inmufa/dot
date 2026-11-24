"""Subagent session ids: `<parent>-sub-<n>`.

The sandbox only accepts `[A-Za-z0-9_-]` ids, so the separator is `-sub-`
(a colon would be refused). Taint, audit rows, read-tracking and
"always allow" are keyed by the child id; tasks and checkpoints by the root.
"""

SUB_SEP = "-sub-"


def child_id(parent: str, n: int) -> str:
    return f"{parent}{SUB_SEP}{n}"


def root_of(session_id: str) -> str:
    return session_id.split(SUB_SEP, 1)[0]
