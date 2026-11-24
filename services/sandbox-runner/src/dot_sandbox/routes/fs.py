"""File routes. Blocking handlers are plain `def` (threadpool)."""

import asyncio

from fastapi import APIRouter, Depends

from dot_sandbox import files
from dot_sandbox.jail import guard_write
from dot_sandbox.lint import lint_file
from dot_sandbox.routes import schemas as s
from dot_sandbox.routes.deps import (
    SessionDep,
    SettingsDep,
    TrackerDep,
    jail,
    require_token,
)
from dot_sandbox.search import GrepQuery, grep

router = APIRouter(prefix="/fs", dependencies=[Depends(require_token)])


@router.post("/read", operation_id="fs_read")
def read(
    body: s.ReadIn, cfg: SettingsDep, sid: SessionDep, tr: TrackerDep
) -> s.ReadOut:
    path = jail(cfg, body.path)
    content, total = files.read_file(
        tr, sid, path, body.offset, body.limit, cfg.max_read_bytes
    )
    return s.ReadOut(content=content, total_lines=total)


@router.post("/write", operation_id="fs_write")
def write(
    body: s.WriteIn, cfg: SettingsDep, sid: SessionDep, tr: TrackerDep
) -> s.WriteOut:
    path = jail(cfg, body.path)
    guard_write(cfg.workspace, path)
    created = files.write_file(tr, sid, path, body.content, cfg.max_read_bytes)
    return s.WriteOut(path=str(path), created=created)


@router.post("/edit", operation_id="fs_edit")
async def edit(
    body: s.EditIn, cfg: SettingsDep, sid: SessionDep, tr: TrackerDep
) -> s.EditOut:
    path = jail(cfg, body.path)
    guard_write(cfg.workspace, path)
    n = await asyncio.to_thread(
        files.edit_file, tr, sid, path, body.old, body.new, body.replace_all
    )
    return s.EditOut(path=str(path), replacements=n, lint=await lint_file(path))


@router.post("/glob", operation_id="fs_glob")
def glob(body: s.GlobIn, cfg: SettingsDep) -> s.GlobOut:
    base = jail(cfg, body.path)
    return s.GlobOut(
        paths=files.glob_files(cfg.workspace.resolve(), base, body.pattern)
    )


@router.post("/grep", operation_id="fs_grep")
async def grep_route(body: s.GrepIn, cfg: SettingsDep) -> s.GrepOut:
    base = jail(cfg, body.path)
    q = GrepQuery(
        body.pattern,
        body.glob,
        body.output_mode,
        body.context,
        body.ignore_case,
        body.head_limit,
    )
    out = await grep(cfg.workspace.resolve(), base, q)
    return s.GrepOut(output=out)
