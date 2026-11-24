"""Textual application and CLI entry point."""

import asyncio
import os
import sys
import time
from typing import ClassVar

import httpx
from dot_contracts.events import (
    ApprovalRequiredEvent,
    CompactionEvent,
    DoneEvent,
    ErrorEvent,
    QuestionEvent,
    StreamEvent,
    SubagentEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)
from dot_contracts.permissions import PermissionMode
from dot_contracts.sessions import Message
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Input

from dot_cli.api import ApiError, Decision, DotClient
from dot_cli.commands import HELP_TEXT, parse_command
from dot_cli.config import Config, parse_config
from dot_cli.headless import run_once
from dot_cli.widgets import ApprovalBar, ChatLog, StatusBar

CSS = """
#log { height: 1fr; padding: 0 1; }
.user { margin-top: 1; }
.assistant { margin-top: 1; }
.tool-call { margin-top: 1; }
Collapsible { padding: 0; border: none; background: transparent; }
ApprovalBar { height: auto; max-height: 50%; border: tall #ffb000; padding: 0 1; }
#approval-diff-box { height: auto; max-height: 20; }
StatusBar { height: 1; padding: 0 1; }
"""


class DotApp(App[None]):
    CSS = CSS
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "approve('allow')", "allow"),
        Binding("s", "approve('always')", "always"),
        Binding("r", "approve('reject')", "reject"),
        Binding("escape", "stop", "stop"),
        Binding("ctrl+c", "quit", "quit"),
    ]

    # Keys typed while the approval prompt appears must not answer it.
    approval_grace_s = 0.8

    def __init__(self, config: Config, client: DotClient | None = None) -> None:
        super().__init__()
        self._armed_at = 0.0
        self._done = False
        self.config = config
        self.client = client or DotClient(config.url, config.token)
        self.session_id: str | None = None
        self.pending: ApprovalRequiredEvent | None = None
        self.mode = config.mode or PermissionMode.DEFAULT.value

    def compose(self) -> ComposeResult:
        yield ChatLog(id="log")
        yield ApprovalBar(id="approval")
        yield Input(placeholder="message, or /help", id="input")
        yield StatusBar()

    async def on_mount(self) -> None:
        self.query_one(Input).focus()
        self.status.update_status(mode=self.mode)
        await self._open_session(self.config.session)

    async def on_unmount(self) -> None:
        await self.client.aclose()

    @property
    def log_view(self) -> ChatLog:
        return self.query_one(ChatLog)

    @property
    def status(self) -> StatusBar:
        return self.query_one(StatusBar)

    async def _open_session(self, resume: str | None) -> None:
        try:
            if resume:
                self.session_id = resume
                for message in await self.client.messages(resume):
                    self._show_history(message)
            else:
                info = await self.client.create_session(self.config.mode)
                self.session_id = info.id
                self.mode = info.mode.value
            self.status.update_status(mode=self.mode)
        except (ApiError, httpx.HTTPError) as exc:
            self.log_view.add_notice(f"cannot open session: {exc}", error=True)

    def _show_history(self, message: Message) -> None:
        if message.role == "user":
            self.log_view.add_user(message.content)
        elif message.role == "assistant" and message.content:
            self.log_view.add_token(message.content, thinking=False)
            self.log_view.close_block()

    @on(Input.Submitted)
    async def _submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        command = parse_command(text)
        if command:
            await self._run_command(*command)
        elif self.session_id is None:
            self.log_view.add_notice("no session", error=True)
        elif self.status.state == "idle":
            self.log_view.add_user(text)
            self.run_worker(self._turn(text), exclusive=True, group="turn")

    async def _run_command(self, name: str, arg: str) -> None:
        log = self.log_view
        if name == "quit":
            self.exit()
        elif name == "help":
            log.add_notice(HELP_TEXT)
        elif name == "stop":
            await self.action_stop()
        elif name == "new":
            await self._open_session(None)
            log.add_notice(f"new session {self.session_id}")
        elif name == "mode":
            await self._set_mode(arg)
        else:
            log.add_notice(f"unknown command /{name}, try /help", error=True)

    async def _set_mode(self, arg: str) -> None:
        if arg not in {m.value for m in PermissionMode}:
            names = ", ".join(m.value for m in PermissionMode)
            self.log_view.add_notice(f"usage: /mode <{names}>", error=True)
            return
        try:
            info = await self.client.set_mode(self.session_id or "", arg)
        except (ApiError, httpx.HTTPError) as exc:
            self.log_view.add_notice(f"mode change failed: {exc}", error=True)
            return
        self.mode = info.mode.value
        self.status.update_status(mode=self.mode)

    async def _turn(self, text: str) -> None:
        self.status.update_status(state="thinking")
        self._done = False
        try:
            async for event in self.client.chat(self.session_id or "", text):
                self.handle_event(event)
            if not self._done:
                self.log_view.add_notice("stream ended without a result", error=True)
        except (ApiError, httpx.HTTPError) as exc:
            self.log_view.add_notice(f"request failed: {exc}", error=True)
        finally:
            self._finish_turn()

    def _finish_turn(self) -> None:
        self.log_view.close_block()
        self.pending = None
        self.query_one(ApprovalBar).hide_approval()
        self.query_one(Input).disabled = False
        self.query_one(Input).focus()
        self.status.update_status(state="idle")

    def handle_event(self, event: StreamEvent) -> None:
        log = self.log_view
        match event:
            case TokenEvent(text=text, thinking=thinking):
                log.add_token(text, thinking=thinking)
            case ToolCallEvent(invocation=call):
                log.add_tool_call(call.name, call.arguments)
            case ToolResultEvent(result=result):
                log.add_tool_result(result.output, is_error=result.is_error)
            case UsageEvent() | CompactionEvent():
                self._on_context_event(event)
            case ApprovalRequiredEvent():
                self._await_approval(event)
            case SubagentEvent() | QuestionEvent():
                self._show_info(event)
            case ErrorEvent(code=code, message=message):
                log.add_notice(f"error {code}: {message}", error=True)
            case DoneEvent(stop_reason=reason):
                self._done = True
                log.close_block()
                if reason == "max_iterations":
                    log.add_notice("stopped: iteration limit reached", error=True)

    def _show_info(self, event: SubagentEvent | QuestionEvent) -> None:
        if isinstance(event, QuestionEvent):
            labels = " / ".join(o.label for o in event.options)
            text = f"question: {event.question} [{labels}] (answer in the web UI)"
        elif event.status == "queued":
            return
        else:
            text = f"{event.label}: {event.status} {event.detail}".strip()
        self.log_view.add_notice(text)

    def _on_context_event(self, event: UsageEvent | CompactionEvent) -> None:
        if isinstance(event, UsageEvent):
            self.status.update_status(usage=(event.context_tokens, event.context_limit))
            return
        self.log_view.add_notice(
            f"context compacted: {event.tokens_before} -> {event.tokens_after} tokens"
        )

    def _await_approval(self, event: ApprovalRequiredEvent) -> None:
        self.pending = event
        self._armed_at = time.monotonic() + self.approval_grace_s
        self.query_one(Input).disabled = True
        self.query_one(ApprovalBar).show_approval(event)
        self.status.update_status(state="approval")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "approve":
            return self.pending is not None
        return True

    async def action_approve(self, decision: Decision) -> None:
        if self.pending is None or time.monotonic() < self._armed_at:
            return
        event, self.pending = self.pending, None
        self.query_one(ApprovalBar).hide_approval()
        self.query_one(Input).disabled = False
        self.query_one(Input).focus()
        self.status.update_status(state="thinking")
        try:
            await self.client.resolve(event.approval_id, decision)
        except (ApiError, httpx.HTTPError) as exc:
            self.log_view.add_notice(f"resolve failed: {exc}", error=True)

    async def action_stop(self) -> None:
        if self.session_id is None or self.status.state == "idle":
            return
        try:
            await self.client.stop(self.session_id)
        except (ApiError, httpx.HTTPError) as exc:
            self.log_view.add_notice(f"stop failed: {exc}", error=True)
        self.workers.cancel_group(self, "turn")
        self._finish_turn()
        self.log_view.add_notice("stopped")


def main(argv: list[str] | None = None) -> None:
    config = parse_config(sys.argv[1:] if argv is None else argv, os.environ)
    if config.once is not None:
        sys.exit(asyncio.run(run_once(config)))
    DotApp(config).run()
