"""Foreground and background shells with process-group kill."""

import asyncio
import contextlib
import os
import shutil
import signal
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from dot_sandbox.errors import SandboxError
from dot_sandbox.runtime.env import scrubbed_env
from dot_sandbox.runtime.output import clip_file, spill


@dataclass
class Job:
    id: str
    session: str
    proc: asyncio.subprocess.Process
    out: Path
    err: Path
    waiter: asyncio.Task = field(repr=False, default=None)  # type: ignore[assignment]
    feeder: asyncio.Task | None = field(repr=False, default=None)


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool = False
    truncated: bool = False
    spill_path: str | None = None
    shell_id: str | None = None


FSIZE_KB = 1_048_576  # per-file write cap (ulimit -f): stops disk-flooding output


async def _feed(proc: asyncio.subprocess.Process, data: str) -> None:
    """Write stdin without blocking the request; a closed pipe is fine."""
    if proc.stdin is None:
        return
    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
        proc.stdin.write(data.encode())
        await proc.stdin.drain()
    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
        proc.stdin.close()


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)


class ShellManager:
    def __init__(self, root: Path, max_jobs: int = 32) -> None:
        self.root = root
        self.max_jobs = max_jobs
        self.scratch = Path(tempfile.mkdtemp(prefix="dot-sandbox-"))
        self.jobs: dict[str, Job] = {}

    async def _spawn(
        self, session: str, command: str, cwd: Path, stdin: str | None = None
    ) -> Job:
        jid = f"sh_{uuid.uuid4().hex[:8]}"
        out, err = self.scratch / f"{jid}.out", self.scratch / f"{jid}.err"
        shell = shutil.which("bash") or "/bin/sh"
        with out.open("wb") as fo, err.open("wb") as fe:
            proc = await asyncio.create_subprocess_exec(
                shell,
                "-c",
                f"ulimit -f {FSIZE_KB} 2>/dev/null\n{command}",
                cwd=cwd,
                env=scrubbed_env(),
                stdin=asyncio.subprocess.DEVNULL
                if stdin is None
                else asyncio.subprocess.PIPE,
                stdout=fo,
                stderr=fe,
                start_new_session=True,
            )
        job = Job(jid, session, proc, out, err)
        job.waiter = asyncio.create_task(proc.wait())
        if stdin is not None:
            job.feeder = asyncio.create_task(_feed(proc, stdin))
        return job

    def _snapshot(self, job: Job, *, timed_out: bool = False) -> ExecResult:
        so, se = clip_file(job.out), clip_file(job.err)
        truncated = so.truncated or se.truncated
        path = str(spill(self.root, job.out, job.err)) if truncated else None
        return ExecResult(
            so.text, se.text, job.proc.returncode, timed_out, truncated, path
        )

    def _drop_files(self, job: Job) -> None:
        job.out.unlink(missing_ok=True)
        job.err.unlink(missing_ok=True)

    async def run(
        self,
        session: str,
        command: str,
        cwd: Path,
        timeout_s: float,
        stdin: str | None = None,
    ) -> ExecResult:
        job = await self._spawn(session, command, cwd, stdin)
        timed_out = False
        try:
            try:
                await asyncio.wait_for(asyncio.shield(job.waiter), timeout_s)
            except TimeoutError:
                timed_out = True
                _kill_group(job.proc)
                await job.waiter
            # Always sweep the group: `sleep 999 &` must not outlive the command.
            _kill_group(job.proc)
            return self._snapshot(job, timed_out=timed_out)
        finally:
            _kill_group(job.proc)
            if job.feeder:
                job.feeder.cancel()
            self._drop_files(job)

    async def start(
        self, session: str, command: str, cwd: Path, stdin: str | None = None
    ) -> ExecResult:
        self._evict()
        job = await self._spawn(session, command, cwd, stdin)
        self.jobs[job.id] = job
        return ExecResult("", "", None, shell_id=job.id)

    def _evict(self) -> None:
        done = [j for j in self.jobs.values() if j.proc.returncode is not None]
        while len(self.jobs) >= self.max_jobs and done:
            old = done.pop(0)
            self._drop_files(old)
            del self.jobs[old.id]
        if len(self.jobs) >= self.max_jobs:
            raise SandboxError(
                429, "too_many_shells", "too many running background shells"
            )

    def get(self, session: str, shell_id: str) -> Job:
        job = self.jobs.get(shell_id)
        if job is None or job.session != session:
            raise SandboxError(404, "shell_not_found", f"no shell {shell_id}")
        return job

    def output(self, session: str, shell_id: str) -> tuple[ExecResult, bool]:
        job = self.get(session, shell_id)
        running = job.proc.returncode is None
        return self._snapshot(job), running

    async def kill(self, session: str, shell_id: str) -> None:
        job = self.get(session, shell_id)
        _kill_group(job.proc)
        await job.waiter

    async def shutdown(self) -> None:
        for job in self.jobs.values():
            _kill_group(job.proc)
        for job in self.jobs.values():
            with contextlib.suppress(Exception):
                await job.waiter
        shutil.rmtree(self.scratch, ignore_errors=True)
