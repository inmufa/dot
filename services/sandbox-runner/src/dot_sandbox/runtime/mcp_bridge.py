"""Long-lived stdio MCP server processes, bridged to the backend by send/recv calls.

The backend never spawns these itself: they run here, inside the sandbox, with a
scrubbed environment (plus the explicit env from the server config), a jailed cwd
and their own process group. stdout lines are queued and handed out by `recv`.
"""

import asyncio
import contextlib
import os
import re
import shutil
import signal
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from dot_sandbox.errors import SandboxError
from dot_sandbox.runtime.env import scrubbed_env

LINE_LIMIT = 4_000_000  # one JSON-RPC message
BUFFER_LIMIT = 16_000_000  # unread stdout before the process is killed
STDERR_TAIL = 4_000
MAX_ARGS = 64
MAX_ENV = 64
MAX_ENV_VALUE = 8192
MAX_ARG = 4096
MAX_RECV_LINES = 200
MAX_RECV_BYTES = 8_000_000  # one long-poll response
SEND_TIMEOUT_S = 10.0
IDLE_S = 120.0  # no send/recv/close from the backend: it is gone, reap the process
_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_BAD_ENV = ("LD_", "DYLD_", "BASH_ENV", "ENV", "PYTHONSTARTUP", "NODE_OPTIONS")


@dataclass
class McpProc:
    id: str
    proc: asyncio.subprocess.Process
    owner: str = ""
    seen: float = field(default_factory=time.monotonic)
    gate: asyncio.Lock = field(default_factory=asyncio.Lock)
    lines: asyncio.Queue[str | None] = field(default_factory=asyncio.Queue)
    buffered: int = 0
    ended: bool = False
    stderr: deque[str] = field(default_factory=lambda: deque(maxlen=40))
    tasks: list[asyncio.Task] = field(default_factory=list)

    @property
    def alive(self) -> bool:
        return self.proc.returncode is None


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)


def _check_env(env: dict[str, str]) -> dict[str, str]:
    if len(env) > MAX_ENV:
        raise SandboxError(400, "bad_env", "too many env entries")
    for key, value in env.items():
        blocked = key.startswith(_BAD_ENV) or key in _BAD_ENV
        if not _ENV_KEY.match(key) or blocked or len(value) > MAX_ENV_VALUE:
            raise SandboxError(400, "bad_env", f"env var {key[:40]!r} is not allowed")
    return env


def _resolve_command(command: str, path: str) -> str:
    if not command or "\x00" in command or "\n" in command:
        raise SandboxError(400, "bad_command", "empty or malformed command")
    found = shutil.which(command, path=path)
    if found is None:
        raise SandboxError(404, "command_not_found", f"{command[:80]} not found")
    return found


class McpBridge:
    def __init__(self, max_procs: int = 8) -> None:
        self.max_procs = max_procs
        self.procs: dict[str, McpProc] = {}
        self._starting = 0  # slots reserved by spawns still in flight

    async def spawn(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
        cwd: Path,
        owner: str = "",
    ) -> str:
        await self._sweep()
        if len(self.procs) + self._starting >= self.max_procs:
            raise SandboxError(429, "too_many_mcp", "too many MCP server processes")
        self._starting += 1
        try:
            return await self._spawn(command, args, env, cwd, owner)
        finally:
            self._starting -= 1

    async def _spawn(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
        cwd: Path,
        owner: str,
    ) -> str:
        if len(args) > MAX_ARGS or any("\x00" in a or len(a) > MAX_ARG for a in args):
            raise SandboxError(400, "bad_args", "too many or malformed arguments")
        full = {**scrubbed_env(), **_check_env(env)}
        exe = _resolve_command(command, full["PATH"])
        if not await asyncio.to_thread(cwd.is_dir):
            raise SandboxError(400, "bad_cwd", "cwd is not a directory")
        try:
            proc = await asyncio.create_subprocess_exec(
                exe,
                *args,
                cwd=cwd,
                env=full,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                limit=LINE_LIMIT,
            )
        except OSError as exc:
            raise SandboxError(400, "spawn_failed", type(exc).__name__) from exc
        mp = McpProc(f"mcp_{uuid.uuid4().hex}", proc, owner)
        mp.tasks = [
            asyncio.create_task(self._read_stdout(mp)),
            asyncio.create_task(self._read_stderr(mp)),
        ]
        self.procs[mp.id] = mp
        return mp.id

    async def _sweep(self) -> None:
        """Forget finished processes; kill ones whose backend stopped polling."""
        now = time.monotonic()
        for pid, p in list(self.procs.items()):
            if not p.alive and p.lines.empty():
                del self.procs[pid]
            elif now - p.seen > IDLE_S:
                await self.close(pid)

    async def _read_stdout(self, mp: McpProc) -> None:
        stream = mp.proc.stdout
        assert stream is not None  # noqa: S101
        try:
            while line := await stream.readline():
                mp.buffered += len(line)
                if mp.buffered > BUFFER_LIMIT:
                    _kill_group(mp.proc)
                    break
                mp.lines.put_nowait(line.decode("utf-8", "replace").rstrip("\r\n"))
        except (ValueError, asyncio.LimitOverrunError):
            _kill_group(mp.proc)  # a single message over LINE_LIMIT
        finally:
            await mp.proc.wait()
            mp.lines.put_nowait(None)

    async def _read_stderr(self, mp: McpProc) -> None:
        stream = mp.proc.stderr
        assert stream is not None  # noqa: S101
        with contextlib.suppress(ValueError, asyncio.LimitOverrunError):
            while line := await stream.readline():
                mp.stderr.append(line.decode("utf-8", "replace")[:STDERR_TAIL])

    def get(self, proc_id: str, owner: str = "") -> McpProc:
        mp = self.procs.get(proc_id)
        if mp is None or mp.owner != owner:  # another session's process is invisible
            raise SandboxError(404, "mcp_not_found", f"no MCP process {proc_id}")
        mp.seen = time.monotonic()
        return mp

    async def send(self, proc_id: str, line: str, owner: str = "") -> None:
        mp = self.get(proc_id, owner)
        stdin = mp.proc.stdin
        if not mp.alive or stdin is None or "\n" in line:
            raise SandboxError(409, "mcp_closed", "process is not accepting input")
        try:
            stdin.write(line.encode() + b"\n")
            await asyncio.wait_for(stdin.drain(), SEND_TIMEOUT_S)
        except (BrokenPipeError, ConnectionResetError, TimeoutError) as exc:
            raise SandboxError(409, "mcp_closed", "process closed its stdin") from exc

    async def recv(
        self, proc_id: str, timeout_s: float, owner: str = ""
    ) -> tuple[list[str], bool, str]:
        """Wait for output: (lines, alive, stderr tail). Empty + alive = timed out."""
        mp = self.get(proc_id, owner)
        async with mp.gate:  # one poller at a time keeps lines in order
            return await self._recv(mp, timeout_s)

    async def _recv(self, mp: McpProc, timeout_s: float) -> tuple[list[str], bool, str]:
        tail = "".join(mp.stderr)[-STDERR_TAIL:]
        if mp.ended:
            return [], False, tail
        try:
            item = await asyncio.wait_for(mp.lines.get(), timeout_s)
        except TimeoutError:
            return [], True, tail
        out: list[str] = []
        size = 0
        while item is not None:
            out.append(item)
            size += len(item)
            mp.buffered = max(0, mp.buffered - len(item) - 1)
            full = len(out) >= MAX_RECV_LINES or size >= MAX_RECV_BYTES
            if full or mp.lines.empty():
                return out, True, tail
            item = mp.lines.get_nowait()
        mp.ended = True
        return out, False, tail

    async def close(self, proc_id: str, owner: str | None = None) -> None:
        mp = self.procs.get(proc_id)
        if mp is None or (owner is not None and mp.owner != owner):
            return
        del self.procs[proc_id]
        _kill_group(mp.proc)
        for task in mp.tasks:
            task.cancel()
        with contextlib.suppress(Exception):
            await mp.proc.wait()
        await asyncio.gather(*mp.tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        for pid in list(self.procs):
            await self.close(pid)
