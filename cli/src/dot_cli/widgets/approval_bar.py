"""Approval prompt: tool, syntax-colored diff, key hints."""

from dot_contracts.events import ApprovalRequiredEvent
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from dot_cli.widgets.chat_log import format_call
from dot_cli.widgets.status_bar import ACCENT


class ApprovalBar(Vertical):
    def compose(self) -> ComposeResult:
        yield Static(id="approval-head")
        with VerticalScroll(id="approval-diff-box"):
            yield Static(id="approval-diff")

    def on_mount(self) -> None:
        self.display = False

    def show_approval(self, event: ApprovalRequiredEvent) -> None:
        head = Text()
        head.append("approval needed  ", style=f"bold {ACCENT}")
        head.append(format_call(event.invocation.name, event.invocation.arguments))
        if event.verdict:
            head.append(f"\n{event.verdict.stage}: {event.verdict.reason}", style="dim")
        head.append("\n[a] allow   [s] always this session   [r] reject", style=ACCENT)
        self.query_one("#approval-head", Static).update(head)
        body = self.query_one("#approval-diff-box")
        body.display = bool(event.diff)
        if event.diff:
            syntax = Syntax(event.diff, "diff", theme="ansi_dark", word_wrap=True)
            self.query_one("#approval-diff", Static).update(syntax)
        self.display = True

    def hide_approval(self) -> None:
        self.display = False
