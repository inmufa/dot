"""Scrolling conversation log."""

from typing import Any

from rich.text import Text
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Static

from dot_cli.widgets.status_bar import ACCENT

_ARG_LIMIT = 60
_PREVIEW_LINES = 5
_PREVIEW_CHARS = 400


def short(value: object, limit: int = _ARG_LIMIT) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_call(name: str, arguments: dict[str, Any]) -> str:
    args = ", ".join(f"{k}={short(v)}" for k, v in arguments.items())
    return f"{name}({short(args, 100)})"


class ChatLog(VerticalScroll):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._block: Static | None = None
        self._kind: str | None = None  # "assistant" | "thinking"
        self._text = ""
        self._fold: Collapsible | None = None

    def _add(self, widget: Static | Collapsible) -> None:
        self.mount(widget)
        self.scroll_end(animate=False)

    def close_block(self) -> None:
        if self._fold is not None:
            self._fold.collapsed = True
        self._block = self._fold = self._kind = None
        self._text = ""

    def add_user(self, text: str) -> None:
        self.close_block()
        self._add(Static(Text("> " + text, style="bold"), classes="user"))

    def add_notice(self, text: str, *, error: bool = False) -> None:
        self.close_block()
        style = "bold red" if error else "dim italic"
        self._add(Static(Text(text, style=style), classes="notice"))

    def add_token(self, text: str, *, thinking: bool) -> None:
        kind = "thinking" if thinking else "assistant"
        if kind != self._kind or self._block is None:
            self.close_block()
            self._kind = kind
            self._block = Static(classes=kind)
            if thinking:
                self._fold = Collapsible(self._block, title="thinking", collapsed=False)
                self._add(self._fold)
            else:
                self._add(self._block)
        self._text += text
        self._block.update(Text(self._text, style="dim italic" if thinking else ""))
        self.scroll_end(animate=False)

    def add_tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        self.close_block()
        line = Text("▸ ", style=f"bold {ACCENT}")
        line.append(format_call(name, arguments), style="bold")
        self._add(Static(line, classes="tool-call"))

    def add_tool_result(self, output: str, *, is_error: bool = False) -> None:
        self.close_block()
        style = "red" if is_error else "dim"
        lines = output.splitlines() or [""]
        preview = "\n".join(lines[:_PREVIEW_LINES])[:_PREVIEW_CHARS]
        truncated = len(lines) > _PREVIEW_LINES or len(output) > len(preview)
        self._add(Static(Text("  ⎿ " + preview, style=style), classes="tool-result"))
        if truncated:
            body = Static(Text(output, style=style))
            self._add(Collapsible(body, title="full output", collapsed=True))
