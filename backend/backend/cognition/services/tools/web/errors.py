"""Turn web DomainExceptions into model-readable error results."""

from dot_contracts.tools import ToolResult

from backend.core.error_messages import CATALOG
from backend.core.exceptions import DomainException
from backend.core.text import strip_control_tags


def one_line(text: str, limit: int) -> str:
    """Collapse whitespace, neutralise control tags, cap the length."""
    text = " ".join(strip_control_tags(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def web_error(tool: str, exc: DomainException) -> ToolResult:
    base = CATALOG.get(exc.code, {}).get("messages", {}).get("en", "Tool failed")
    detail = exc.ctx.get("detail")
    extra = f": {one_line(str(detail), 200)}" if detail else ""
    return ToolResult(
        call_id="",
        output=f"{tool} failed (error {exc.code}): {base}{extra}",
        is_error=True,
    )
