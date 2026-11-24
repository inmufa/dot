"""Footer: state dot, mode, context usage."""

from typing import Literal

from rich.text import Text
from textual.widgets import Static

ACCENT = "#ffb000"
State = Literal["idle", "thinking", "approval"]
_LABEL = {"idle": "idle", "thinking": "thinking", "approval": "awaiting approval"}


class StatusBar(Static):
    def __init__(self) -> None:
        super().__init__()
        self.state: State = "idle"
        self.mode = "-"
        self.used = 0
        self.limit = 0
        self.refresh_text()

    def update_status(
        self,
        state: State | None = None,
        mode: str | None = None,
        usage: tuple[int, int] | None = None,
    ) -> None:
        self.state = state or self.state
        self.mode = mode or self.mode
        if usage:
            self.used, self.limit = usage
        self.refresh_text()

    def render_text(self) -> Text:
        active = self.state != "idle"
        text = Text()
        text.append(
            "● " if active else "○ ", style=f"bold {ACCENT}" if active else "dim"
        )
        text.append(_LABEL[self.state], style=ACCENT if active else "dim")
        text.append(f"  |  mode {self.mode}", style="dim")
        if self.limit:
            pct = round(100 * self.used / self.limit)
            text.append(f"  |  ctx {self.used}/{self.limit} ({pct}%)", style="dim")
        return text

    def refresh_text(self) -> None:
        self.update(self.render_text())
