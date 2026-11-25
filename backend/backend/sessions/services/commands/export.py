"""Session export as markdown or JSON."""

import json
from typing import Any

from backend.sessions.models import Message, Session

_FENCE = "```"


def _calls(row: Message, results: dict[str, Message]) -> list[str]:
    out = []
    for call in row.tool_calls or []:
        fn = call.get("function") or {}
        res = results.get(str(call.get("id")))
        args = str(fn.get("arguments") or "{}")
        body = f"{_FENCE}json\n{args}\n{_FENCE}"
        if res is not None:
            body += f"\n\n{_FENCE}\n{res.content}\n{_FENCE}"
        out.append(
            f"<details><summary>Tool: {fn.get('name', '?')}</summary>\n\n"
            f"{body}\n\n</details>"
        )
    return out


def to_markdown(
    session: Session, rows: list[Message], *, include_thinking: bool = False
) -> str:
    results = {r.tool_call_id: r for r in rows if r.role == "tool" and r.tool_call_id}
    parts = [f"# {session.title or 'Untitled session'}", f"Session {session.public_id}"]
    for row in rows:
        if row.role == "user":
            parts.append(f"## User\n\n{row.content}")
        elif row.role == "plan":
            parts.append(f"## Plan\n\n{row.content}")
        elif row.role == "assistant":
            block = ["## Assistant"]
            if include_thinking and row.reasoning:
                block.append(
                    f"<details><summary>Thinking</summary>\n\n{row.reasoning}"
                    "\n\n</details>"
                )
            if row.content:
                block.append(row.content)
            block += _calls(row, results)
            parts.append("\n\n".join(block))
    return "\n\n".join(parts) + "\n"


def to_json(
    session: Session, rows: list[Message], *, include_thinking: bool = False
) -> dict[str, Any]:
    messages = []
    for r in rows:
        if r.role == "summary":
            continue
        item: dict[str, Any] = {
            "seq": r.seq,
            "role": r.role,
            "content": r.content,
            "tool_calls": r.tool_calls,
            "tool_call_id": r.tool_call_id,
            "created_at": r.created_at.isoformat(),
            "meta": r.meta,
        }
        if include_thinking and r.reasoning:
            item["thinking"] = r.reasoning
        messages.append(item)
    return json.loads(
        json.dumps(
            {
                "id": session.public_id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
                "project": session.project,
                "parent_id": session.parent_id,
                "parent_seq": session.parent_seq,
                "messages": messages,
            }
        )
    )
