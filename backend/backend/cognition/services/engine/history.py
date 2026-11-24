"""Convert stored transcript rows to OpenAI-style chat messages."""

from typing import Any

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


def to_chat_messages(system: str, rows: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    carry = ""  # summary text waiting to join the next user message
    for row in rows:
        if row.role == "plan":
            continue  # approved plan: UI only, the model wrote it
        if row.role == "summary":
            carry = SUMMARY_HEADER + row.model_text
            continue
        if row.role == "user":
            text = _user_text(row)
            out.append(
                {"role": "user", "content": f"{carry}\n\n{text}" if carry else text}
            )
            carry = ""
            continue
        if carry:  # keep roles alternating: summary, then the assistant/tool tail
            out.append({"role": "user", "content": carry})
            carry = ""
        out.append(_plain(row))
    if carry:
        out.append({"role": "user", "content": carry})
    return out
