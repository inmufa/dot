"""Headless `dot --once` mode: stream one turn, write the final answer to stdout."""

import sys

import httpx
from dot_contracts.events import (
    ApprovalRequiredEvent,
    DoneEvent,
    ErrorEvent,
    QuestionEvent,
    TokenEvent,
    ToolCallEvent,
)

from dot_cli.api import ApiError, DotClient
from dot_cli.config import Config


async def run_once(config: Config, client: DotClient | None = None) -> int:
    client = client or DotClient(config.url, config.token)
    answer: list[str] = []
    code = 0
    try:
        session_id = config.session or (await client.create_session(config.mode)).id
        async for event in client.chat(session_id, config.once or ""):
            match event:
                case TokenEvent(thinking=False, text=text):
                    answer.append(text)
                case ToolCallEvent():
                    answer.clear()  # keep only text after the last tool use
                case ApprovalRequiredEvent(approval_id=approval_id):
                    sys.stderr.write("approval required, rejecting (headless)\n")
                    await client.resolve(approval_id, "reject")
                case QuestionEvent(question_id=question_id):
                    sys.stderr.write("question asked, answering 'no user' (headless)\n")
                    await client.answer(
                        question_id, [], "No user is available: decide yourself."
                    )
                case ErrorEvent(message=message):
                    sys.stderr.write(f"error: {message}\n")
                    code = 1
                case DoneEvent():
                    break
    except (ApiError, httpx.HTTPError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        code = 1
    finally:
        await client.aclose()
    sys.stdout.write("".join(answer).strip() + "\n")
    return code
