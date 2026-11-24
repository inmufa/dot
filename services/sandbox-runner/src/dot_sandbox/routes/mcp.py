"""Backend-only: stdio MCP server processes, spill files and retention."""

import secrets
import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from dot_sandbox.routes.deps import SessionDep, SettingsDep, jail, require_token
from dot_sandbox.runtime import retention

router = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])
SPILL_MAX = 6_000_000


class SpawnIn(BaseModel):
    command: str = Field(min_length=1, max_length=1024)
    args: list[str] = Field(default_factory=list, max_length=64)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None


class SendIn(BaseModel):
    line: str = Field(max_length=4_000_000)


class RecvIn(BaseModel):
    timeout_s: float = Field(default=20.0, ge=0, le=25)


class SpillIn(BaseModel):
    content: str = Field(max_length=SPILL_MAX)


class RetentionIn(BaseModel):
    checkpoint_days: float = Field(default=14, gt=0, le=3650)
    checkpoint_max_bytes: int = Field(default=50_000_000, ge=0)
    outputs_days: float = Field(default=7, gt=0, le=3650)
    protect_sessions: list[str] = Field(default_factory=list, max_length=1000)
    protect_last: int = Field(default=50, ge=0, le=10_000)


@router.post("/mcp/spawn", operation_id="internal_mcp_spawn")
async def spawn(
    body: SpawnIn, request: Request, cfg: SettingsDep, sid: SessionDep
) -> dict[str, str]:
    cwd = jail(cfg, body.cwd)
    pid = await request.app.state.mcp.spawn(body.command, body.args, body.env, cwd, sid)
    return {"proc_id": pid}


@router.post("/mcp/{proc_id}/send", operation_id="internal_mcp_send")
async def send(
    proc_id: str, body: SendIn, request: Request, sid: SessionDep
) -> dict[str, bool]:
    await request.app.state.mcp.send(proc_id, body.line, sid)
    return {"ok": True}


@router.post("/mcp/{proc_id}/recv", operation_id="internal_mcp_recv")
async def recv(proc_id: str, body: RecvIn, request: Request, sid: SessionDep) -> dict:
    lines, alive, tail = await request.app.state.mcp.recv(proc_id, body.timeout_s, sid)
    return {"lines": lines, "alive": alive, "stderr": tail}


@router.post("/mcp/{proc_id}/close", operation_id="internal_mcp_close")
async def close(proc_id: str, request: Request, sid: SessionDep) -> dict[str, bool]:
    await request.app.state.mcp.close(proc_id, sid)
    return {"ok": True}


@router.post("/spill", operation_id="internal_spill")
def spill(body: SpillIn, cfg: SettingsDep) -> dict[str, str]:
    """Store oversized tool output under .dot/tool_outputs and return its path."""
    out = cfg.workspace.resolve() / ".dot" / "tool_outputs"
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"mcp_{int(time.time())}_{secrets.token_hex(4)}.log"
    target.write_text(body.content, encoding="utf-8")
    return {"path": str(target)}


@router.post("/retention", operation_id="internal_retention")
def prune(body: RetentionIn, cfg: SettingsDep) -> dict[str, int]:
    report = retention.prune(
        cfg.workspace,
        checkpoint_days=body.checkpoint_days,
        checkpoint_max_bytes=body.checkpoint_max_bytes,
        outputs_days=body.outputs_days,
        protect_sessions=frozenset(body.protect_sessions),
        protect_last=body.protect_last,
    )
    return {
        "checkpoints_removed": report.checkpoints_removed,
        "outputs_removed": report.outputs_removed,
        "bytes_freed": report.bytes_freed,
    }
