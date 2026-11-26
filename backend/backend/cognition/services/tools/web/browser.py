"""Deferred browser tools. Page content is untrusted: every result is tainted."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from dot_contracts.tools import ToolDefinition, ToolResult

from backend.cognition.services.tools.registry import Tool, ToolContext
from backend.cognition.services.tools.web.browser_client import BrowserClient
from backend.cognition.services.tools.web.errors import one_line, web_error
from backend.core.exceptions import DomainException
from backend.core.text import strip_control_tags

if TYPE_CHECKING:
    from backend.cognition.services.tools.web.browser_login import VaultHandle

MAX_CHARS = 14_000
_VIEWS = (
    "snapshot",
    "extract",
    "screenshot",
    "scroll_down",
    "scroll_up",
    "scroll_top",
    "scroll_bottom",
)
_Body = Callable[[ToolContext, BrowserClient, dict[str, Any]], Awaitable[str]]


def _head(d: dict[str, Any]) -> str:
    title = one_line(str(d.get("title", "")), 200)
    return f"Page: {one_line(str(d.get('url', '')), 500)}\nTitle: {title}"


def _element(e: dict[str, Any]) -> str:
    bits = [f"[{e.get('id')}] {e.get('role', '')}"]
    if e.get("name"):
        bits.append(f'"{one_line(str(e["name"]), 120)}"')
    if e.get("value"):
        bits.append(f"value={one_line(str(e['value']), 80)!r}")
    if e.get("href"):
        bits.append(f"-> {one_line(str(e['href']), 200)}")
    if e.get("state"):
        bits.append(f"({one_line(str(e['state']), 60)})")
    return " ".join(bits)


def _snapshot_text(d: dict[str, Any]) -> str:
    lines = [_head(d), "Elements (use the number as element_id):"]
    lines += [_element(e) for e in d.get("elements", [])]
    if d.get("elements_truncated"):
        lines.append("[more elements exist: scroll and take a new snapshot]")
    lines.append(f"Scroll: {d.get('scroll_y', 0)} of {d.get('page_height', '?')} px")
    lines.append("Text:\n" + strip_control_tags(str(d.get("text", ""))))
    return "\n".join(lines)


async def _navigate(ctx: ToolContext, b: BrowserClient, a: dict[str, Any]) -> str:
    # The snapshot is folded in here rather than left as a second step: a model
    # that skips calling BrowserRead would otherwise be flying blind forever.
    if a.get("back"):
        d = await b.post(ctx.session_id, "/back", {})
        head = f"Went back.\n{_head(d)}"
    else:
        if not a.get("url"):
            msg = "give a url, or back=true"
            raise ValueError(msg)
        d = await b.post(ctx.session_id, "/nav", {"url": str(a["url"])})
        head = f"Opened (HTTP {d.get('status')}).\n{_head(d)}"
    snap = _snapshot_text(await b.post(ctx.session_id, "/snapshot", {}))
    return f"{head}\n{snap}"


async def _read(ctx: ToolContext, b: BrowserClient, a: dict[str, Any]) -> str:
    view = a.get("view", "snapshot")
    sid = ctx.session_id
    if view == "snapshot":
        return _snapshot_text(await b.post(sid, "/snapshot", {}))
    if view == "extract":
        body = {"goal": str(a["selector"])} if a.get("selector") else {}
        d = await b.post(sid, "/extract", body)
        cut = "\n[truncated]" if d.get("truncated") else ""
        return f"{_head(d)}\n---\n{strip_control_tags(str(d.get('markdown', '')))}{cut}"
    if view == "screenshot":
        d = await b.post(sid, "/screenshot", {"full_page": bool(a.get("full_page"))})
        # No file endpoint accepts binary yet, so the image is not kept.
        return (
            f"{_head(d)}\nScreenshot taken ({d.get('mime')}, {d.get('bytes')} bytes). "
            "Images cannot be shown to this model and are not saved; "
            "use snapshot or extract to read the page."
        )
    direction = view.removeprefix("scroll_")
    await b.post(sid, "/scroll", {"direction": direction})
    return _snapshot_text(await b.post(sid, "/snapshot", {}))


async def _click(ctx: ToolContext, b: BrowserClient, a: dict[str, Any]) -> str:
    target = {"element_id": int(a["element_id"])}
    if a.get("select_value"):
        d = await b.post(
            ctx.session_id, "/select", {**target, "value": str(a["select_value"])}
        )
        return f"Selected the option.\n{_head(d)}"
    d = await b.post(ctx.session_id, "/click", target)
    return f"Clicked.\n{_head(d)}\nTake a new snapshot: element ids may have changed."


async def _type(ctx: ToolContext, b: BrowserClient, a: dict[str, Any]) -> str:
    body = {
        "element_id": int(a["element_id"]),
        "text": str(a["text"]),
        "submit": bool(a.get("submit")),
    }
    d = await b.post(ctx.session_id, "/type", body)
    return f"Typed.\n{_head(d)}"


def _navigate_with(vault: "VaultHandle | None") -> _Body:
    """Navigate; restore consented saved sessions first and name saved logins after."""

    async def body(ctx: ToolContext, b: BrowserClient, a: dict[str, Any]) -> str:
        url = str(a.get("url") or "")
        if vault and url and not a.get("back"):
            await vault.on_navigate(ctx.session_id, url)
        text = await _navigate(ctx, b, a)
        if vault and url and not a.get("back"):
            text += await vault.hint(ctx.session_id, url)
        return text

    return body


def _runner(name: str, browser: BrowserClient, body: _Body):
    async def run(ctx: ToolContext, a: dict[str, Any]) -> ToolResult:
        try:
            text = await body(ctx, browser, a)
        except DomainException as exc:
            # The worker's detail can quote the page, so the error stays tainted too.
            err = web_error(name, exc)
            return err.model_copy(update={"tainted": exc.code == 4016})  # noqa: PLR2004
        except (ValueError, TypeError) as exc:
            return ToolResult(call_id="", output=f"{name}: {exc}", is_error=True)
        return ToolResult(call_id="", output=text, tainted=True)

    return run


def _tool(  # noqa: PLR0913
    name: str,
    desc: str,
    props: dict[str, Any],
    required: list[str],
    *,
    mutating: bool,
    browser: BrowserClient,
    body: _Body,
) -> Tool:
    definition = ToolDefinition(
        name=name,
        description=desc,
        deferred=True,
        mutating=mutating,
        input_schema={"type": "object", "properties": props, "required": required},
    )
    return Tool(definition, _runner(name, browser, body), max_chars=MAX_CHARS)


def make_browser_tools(
    browser: BrowserClient, vault: "VaultHandle | None" = None
) -> list[Tool]:
    kw: dict[str, Any] = {"browser": browser}
    return [
        _tool(
            "BrowserNavigate",
            "Open a URL in the headless browser (or go back with back=true). "
            "Returns a snapshot of the resulting page already, with numbered "
            "clickable elements - no separate read needed. Only for pages that need "
            "JavaScript, login or clicking, or when browser control was explicitly "
            "asked for; WebFetch is the default for plain reading and is cheaper.",
            {"url": {"type": "string"}, "back": {"type": "boolean"}},
            [],
            mutating=False,
            body=_navigate_with(vault),
            **kw,
        ),
        _tool(
            "BrowserRead",
            "Re-read the current page without navigating - use after a click/type, "
            "or for extract/screenshot/scroll views. BrowserNavigate already "
            "includes a snapshot, so you don't need this right after navigating. "
            "view: snapshot (numbered clickable elements + text, default) | "
            "extract (article markdown; selector optional) | screenshot (metadata "
            "only) | scroll_down | scroll_up | scroll_top | scroll_bottom (scrolls, "
            "then returns a snapshot).",
            {
                "view": {"type": "string", "enum": list(_VIEWS)},
                "selector": {"type": "string"},
                "full_page": {"type": "boolean"},
            },
            [],
            mutating=False,
            body=_read,
            **kw,
        ),
        _tool(
            "BrowserClick",
            "Click an element by its snapshot number. With select_value, choose "
            "that option in a dropdown instead of clicking.",
            {"element_id": {"type": "integer"}, "select_value": {"type": "string"}},
            ["element_id"],
            mutating=True,
            body=_click,
            **kw,
        ),
        _tool(
            "BrowserType",
            "Type text into an input by its snapshot number; submit=true presses Enter.",
            {
                "element_id": {"type": "integer"},
                "text": {"type": "string"},
                "submit": {"type": "boolean"},
            },
            ["element_id", "text"],
            mutating=True,
            body=_type,
            **kw,
        ),
    ]
