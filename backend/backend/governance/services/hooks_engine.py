"""Hooks: shell commands run inside the sandbox with the event as JSON on stdin.

Exit 0 = ok (stdout may be JSON with decision/reason/updatedInput), exit 2 =
block (stderr goes back to the model), anything else = non-blocking warning.
Hooks can block, rewrite arguments or ask for approval; they can never allow
what a rule or mode denied (the caller ignores `decision == "allow"`).
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from backend.core.exceptions import DomainException
from backend.governance.settings.schema import HookEvent, HookSpec
from backend.routing.clients.sandbox_client import SandboxClient

logger = logging.getLogger(__name__)
BLOCK_EXIT = 2


@dataclass
class HookOutcome:
    blocked: bool = False
    reason: str = ""
    decision: str | None = None  # allow | ask | deny (hook's opinion)
    updated_input: dict[str, Any] | None = None
    stdout: str = ""
    warnings: list[str] = field(default_factory=list)


def matches(matcher: str, tool_name: str | None) -> bool:
    if tool_name is None or matcher in ("", "*"):
        return True
    try:
        return re.fullmatch(matcher, tool_name) is not None
    except re.error:
        return matcher == tool_name


def _json_of(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class HooksEngine:
    def __init__(self, sandbox: SandboxClient, workspace: str) -> None:
        self._sandbox = sandbox
        self._workspace = workspace

    async def run(
        self,
        event: HookEvent,
        session: str,
        hooks: dict[HookEvent, list[HookSpec]],
        payload: dict[str, Any],
        tool_name: str | None = None,
    ) -> HookOutcome:
        """Run every matching hook in order; the first block stops the chain."""
        out = HookOutcome()
        body = {
            "hook_event_name": event.value,
            "session_id": session,
            "cwd": self._workspace,
            **payload,
        }
        for spec in hooks.get(event, []):
            if not matches(spec.matcher, tool_name):
                continue
            await self._run_one(spec, session, body, out)
            if out.blocked:
                break
            if out.updated_input is not None and "tool_input" in body:
                body["tool_input"] = out.updated_input
        return out

    async def _run_one(
        self, spec: HookSpec, session: str, body: dict[str, Any], out: HookOutcome
    ) -> None:
        request = {
            "command": spec.command,
            "timeout_s": spec.timeout,
            "stdin": json.dumps(body, default=str),
        }
        try:
            r = await self._sandbox.post(
                session, "/exec", request, timeout_s=spec.timeout
            )
        except DomainException as exc:
            out.warnings.append(f"hook could not run (error {exc.code})")
            return
        if not r.ok:
            out.warnings.append(f"hook failed to start: {r.error_text()}")
            return
        data = r.data
        if data.get("timed_out"):
            out.warnings.append(f"hook timed out after {spec.timeout:g}s")
            return
        code = data.get("exit_code")
        stderr = str(data.get("stderr", "")).strip()
        if code == BLOCK_EXIT:
            out.blocked = True
            out.reason = stderr or "blocked by hook"
        elif code == 0:
            self._read_stdout(str(data.get("stdout", "")), out)
        else:
            out.warnings.append(f"hook exited with code {code}: {stderr[:200]}")

    @staticmethod
    def _read_stdout(stdout: str, out: HookOutcome) -> None:
        out.stdout = (out.stdout + "\n" + stdout).strip()
        data = _json_of(stdout)
        if data is None:
            return
        decision = str(data.get("decision", "")).lower()
        if decision in {"block", "deny"}:
            out.blocked = True
            out.reason = str(data.get("reason") or "blocked by hook")
        elif decision in {"ask", "allow", "approve"}:
            out.decision = "allow" if decision == "approve" else decision
        updated = data.get("updatedInput")
        if isinstance(updated, dict):
            out.updated_input = updated
