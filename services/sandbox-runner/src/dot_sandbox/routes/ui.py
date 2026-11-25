"""Backend-only endpoints for uploads, document text, previews and the tree."""

import asyncio
import json
import resource
import sys
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from dot_sandbox.errors import SandboxError
from dot_sandbox.jail import resolve
from dot_sandbox.routes.deps import SettingsDep, jail, require_token
from dot_sandbox.runtime import browse
from dot_sandbox.runtime.env import scrubbed_env
from dot_sandbox.runtime.uploads import upload_target, write_stream

router = APIRouter(prefix="/internal", dependencies=[Depends(require_token)])
EXTRACT_TIMEOUT_S = 25.0
EXTRACT_MEM = 1_500_000_000


class ExtractIn(BaseModel):
    path: str
    kind: str = Field(pattern=r"^(pdf|docx|xlsx)$")


class TreeIn(BaseModel):
    path: str | None = None
    depth: int = Field(default=1, ge=1, le=browse.MAX_DEPTH)


class RecentIn(BaseModel):
    since: float = 0
    limit: int = Field(default=200, ge=1, le=500)


class StatIn(BaseModel):
    paths: list[str] = Field(max_length=500)


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (EXTRACT_MEM, EXTRACT_MEM))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))


@router.post("/write_binary", operation_id="internal_write_binary")
async def write_binary(
    request: Request, cfg: SettingsDep, path: Annotated[str, Query()]
) -> dict[str, Any]:
    real = resolve(cfg.workspace, path)
    upload_target(cfg.workspace, real)
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > cfg.max_upload_bytes:
        raise SandboxError(413, "too_large", "upload exceeds the cap")
    size = await write_stream(real, request.stream(), cfg.max_upload_bytes)
    return {"path": str(real), "size": size}


class DeleteIn(BaseModel):
    path: str


@router.post("/delete_upload", operation_id="internal_delete_upload")
def delete_upload(body: DeleteIn, cfg: SettingsDep) -> dict[str, bool]:
    real = resolve(cfg.workspace, body.path)
    upload_target(cfg.workspace, real)
    existed = real.is_file() and not real.is_symlink()
    if existed:
        real.unlink()
    return {"deleted": existed}


@router.post("/extract", operation_id="internal_extract")
async def extract(body: ExtractIn, cfg: SettingsDep) -> dict[str, Any]:
    real = jail(cfg, body.path)
    if not browse.visible(cfg.workspace.resolve(), real) or not real.is_file():
        raise SandboxError(404, "not_found", "no such file")
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "dot_sandbox.runtime.extract",
        str(real),
        body.kind,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=scrubbed_env(),
        preexec_fn=_limits,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), EXTRACT_TIMEOUT_S)
    except TimeoutError as exc:
        proc.kill()
        raise SandboxError(422, "extract_failed", "extraction timed out") from exc
    try:
        data = json.loads(out or b"{}")
    except ValueError:
        data = {}
    if not isinstance(data, dict) or "text" not in data:
        detail = str(data.get("error", "unreadable")) if isinstance(data, dict) else "x"
        raise SandboxError(422, "extract_failed", detail)
    return data


@router.get("/raw", operation_id="internal_raw")
def raw(
    cfg: SettingsDep,
    path: Annotated[str, Query()],
    max_bytes: Annotated[int, Query(ge=1)] = 2_000_000,
) -> Response:
    real = jail(cfg, path)
    data = browse.read_raw(cfg.workspace, real, min(max_bytes, cfg.max_read_bytes))
    return Response(data, media_type="application/octet-stream")


@router.post("/tree", operation_id="internal_tree")
def tree(body: TreeIn, cfg: SettingsDep) -> dict[str, Any]:
    base = jail(cfg, body.path)
    return {"entries": browse.tree(cfg.workspace, base, body.depth)}


@router.post("/recent", operation_id="internal_recent")
def recent(body: RecentIn, cfg: SettingsDep) -> dict[str, Any]:
    return {"entries": browse.recent(cfg.workspace, body.since, body.limit)}


@router.post("/stat", operation_id="internal_stat")
def stat(body: StatIn, cfg: SettingsDep) -> dict[str, Any]:
    return {"entries": browse.stat_many(cfg.workspace, body.paths)}
