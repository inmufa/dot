"""AI chat titles: once the first exchange is done, replace the first-message placeholder."""

import logging

from backend.core.exceptions import DomainException
from backend.routing.clients.llm_types import LLMClient
from backend.sessions.services.session_service import TITLE_MAX, SessionService

logger = logging.getLogger(__name__)
AFTER_USER_MESSAGES = 1
_SNIPPET = 400
_SYSTEM = (
    "Write a short title for this chat: 2 to 5 words, in the language the user writes in. "
    "Reply with the title only, no quotes, no trailing period."
)


def placeholder(first_user_text: str) -> str | None:
    """What title_from stores; a title that still equals it was never renamed."""
    return " ".join(first_user_text.split())[:TITLE_MAX] or None


def clean(raw: str) -> str | None:
    line = next((x for x in raw.strip().splitlines() if x.strip()), "")
    title = " ".join(line.split()).strip("\"'`*# ").rstrip(".")
    return title[:TITLE_MAX] or None


async def retitle(sessions: SessionService, llm: LLMClient, public_id: str) -> None:
    """Name the chat once, after its first exchange, if the title was never renamed."""
    try:
        rows = await sessions.messages(public_id)
        users = [m for m in rows if m.role == "user"]
        if len(users) != AFTER_USER_MESSAGES:
            return
        row = await sessions.get(public_id)
        if row.title != placeholder(users[0].content):
            return
        convo = "\n".join(
            f"{m.role}: {' '.join(m.content.split())[:_SNIPPET]}"
            for m in rows
            if m.role in {"user", "assistant"} and m.content.strip()
        )[:2000]
        raw = await llm.complete(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": convo},
            ],
            max_tokens=32,
            thinking=False,
        )
        title = clean(raw)
        if title:
            await sessions.set_title_if(row.id, placeholder(users[0].content), title)
    except DomainException:
        logger.info("auto title skipped: model unavailable")
    except Exception:
        logger.exception("auto title failed")
