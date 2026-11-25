"""BrowserLogin: the model names a saved login; the worker fills it. No secret reaches the model."""

from typing import Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.cognition.services.tools.web.errors import web_error
from backend.core.exceptions import DomainException

NAME = "BrowserLogin"
BROWSER_FAILED = 4016
KEY_MISSING = 4140


class VaultHandle:
    """Late-bound vault agent (the vault is built after the tool registry)."""

    def __init__(self) -> None:
        self.agent: Any = None

    async def hint(self, sid: str, url: str) -> str:
        return await self.agent.hint(sid, url) if self.agent else ""

    async def on_navigate(self, sid: str, url: str) -> None:
        if self.agent:
            await self.agent.restore_on_navigate(sid, url, owner=False)


def make_login_tool(handle: VaultHandle) -> Tool:
    async def run(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        agent = handle.agent
        if agent is None or not agent.svc.enabled:
            return web_error(NAME, DomainException(KEY_MISSING))
        label = str(a.get("credential", "")).strip()
        if not label:
            return ToolResult(
                call_id="", output=f"{NAME}: give a credential label", is_error=True
            )
        try:
            text = await agent.login(ctx.session_id, label, a.get("url") or None)
        except DomainException as exc:
            err = web_error(NAME, exc)
            return err.model_copy(update={"tainted": exc.code == BROWSER_FAILED})
        # Title and URL come from the page: untrusted.
        return ToolResult(call_id="", output=text, tainted=True)

    definition = ToolDefinition(
        name=NAME,
        description=(
            "Sign in to a website with a login the owner saved. Give the saved login's "
            "label (BrowserNavigate lists matching labels for a site) and optionally the "
            "login page url. The owner approves each use; the browser fills the username, "
            "password and 2FA code itself and you never see them. Returns only "
            "'logged in' or 'failed: reason'. Then use BrowserRead on the page."
        ),
        deferred=True,
        mutating=True,
        needs_approval=True,
        input_schema={
            "type": "object",
            "properties": {"credential": {"type": "string"}, "url": {"type": "string"}},
            "required": ["credential"],
        },
    )
    return Tool(definition, run, max_chars=4_000)
