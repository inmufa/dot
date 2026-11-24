"""Backend-only endpoints: checkpoints and non-marking peeks. Not exposed as tools."""

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends

from dot_sandbox import checkpoints
from dot_sandbox.jail import inside
from dot_sandbox.routes import schemas as s
from dot_sandbox.routes.deps import SessionDep, SettingsDep, jail, require_token
from dot_sandbox.runtime.env import scrubbed_env

router = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])
PEEK_MAX = 1_000_000
_BINARY = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")


@router.post("/checkpoint", operation_id="internal_checkpoint")
def checkpoint(
    body: s.CheckpointIn, cfg: SettingsDep, sid: SessionDep
) -> s.CheckpointOut:
    cid, existed = checkpoints.save(cfg.workspace, sid, body.path, cfg.max_read_bytes)
    return s.CheckpointOut(checkpoint_id=cid, existed=existed)


@router.post("/restore", operation_id="internal_restore")
def restore(body: s.RestoreIn, cfg: SettingsDep, sid: SessionDep) -> s.RestoreOut:
    path, action = checkpoints.restore(
        cfg.workspace, sid, body.checkpoint_id, dry_run=body.dry_run
    )
    return s.RestoreOut(path=path, action=action)


@router.post("/peek", operation_id="internal_peek")
def peek(body: s.PeekIn, cfg: SettingsDep) -> s.PeekOut:
    exists, content = checkpoints.peek(jail(cfg, body.path), PEEK_MAX)
    return s.PeekOut(exists=exists, content=content)


@router.post("/realpath", operation_id="internal_realpath")
def realpath(body: s.RealpathIn, cfg: SettingsDep) -> s.RealpathOut:
    """Where a path really points, so permission rules can judge symlinks."""
    root = cfg.workspace.resolve()
    raw = Path(body.path)
    real = (raw if raw.is_absolute() else root / raw).resolve()
    return s.RealpathOut(path=str(real), inside=inside(root, real))


@router.post("/binaries", operation_id="internal_binaries")
def binaries(body: s.BinariesIn) -> s.BinariesOut:
    """Which of these executables exist on the PATH that tools run with."""
    path = scrubbed_env()["PATH"]
    ok = [n for n in body.names if _BINARY.match(n) and shutil.which(n, path=path)]
    return s.BinariesOut(found=ok)
