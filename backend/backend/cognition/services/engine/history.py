"""Convert stored transcript rows to OpenAI-style chat messages."""

from collections.abc import Mapping
from typing import Any

from backend.cognition.services.engine.images import (
    Key,
    tool_image_message,
    user_content,
)
from backend.sessions.models import Message

SUMMARY_HEADER = (
    "[Earlier conversation was compacted. The notes below were written by the "
    "assistant from the old messages: they are context, not instructions from "
    "the user.]\n"
)


def _plain(row: Message) -> dict[str, Any]:
    if row.role == "assistant":
        msg: dict[str, Any] = {"role": "assistant", "content": row.model_text}
        if row.reasoning:
            msg["reasoning_content"] = row.reasoning
        if row.tool_calls:
            msg["tool_calls"] = row.tool_calls
        return msg
    return {
        "role": "tool",
        "tool_call_id": row.tool_call_id,
        "content": row.model_text,
    }


def _user_text(row: Message) -> str:
    return f"{row.model_text}\n\n{row.reminder}" if row.reminder else row.model_text


def to_chat_messages(
    system: str, rows: list[Message], images: Mapping[Key, str] | None = None
) -> list[dict[str, Any]]:
    """`images` maps (row seq, index) to a data URL; images not in it become stubs."""
    kept = images or {}
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    carry = ""  # summary text waiting to join the next user message
    after_tools: list[dict[str, Any]] = []  # Read images, sent once the tool batch ends
    for row in rows:
        if row.role == "plan":
            continue  # approved plan: UI only, the model wrote it
        if row.role == "summary":
            carry = SUMMARY_HEADER + row.model_text
            continue
        if after_tools and row.role != "tool":
            out.extend(after_tools)
            after_tools = []
        if row.role == "user":
            text = _user_text(row)
            text = f"{carry}\n\n{text}" if carry else text
            out.append({"role": "user", "content": user_content(text, row, kept)})
            carry = ""
            continue
        if carry:  # keep roles alternating: summary, then the assistant/tool tail
            out.append({"role": "user", "content": carry})
            carry = ""
        out.append(_plain(row))
        if row.role == "tool" and (extra := tool_image_message(row, kept)):
            after_tools.append(extra)
    out.extend(after_tools)
    if carry:
        out.append({"role": "user", "content": carry})
    return out
