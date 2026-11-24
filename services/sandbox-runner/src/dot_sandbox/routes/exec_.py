"""Shell routes."""

from fastapi import APIRouter, Depends

from dot_sandbox.errors import SandboxError
from dot_sandbox.routes import schemas as s
from dot_sandbox.routes.deps import (
    SessionDep,
    SettingsDep,
    ShellsDep,
    jail,
    require_token,
)

router = APIRouter(prefix="/exec", dependencies=[Depends(require_token)])


@router.post("", operation_id="exec_run")
async def run(
    body: s.ExecIn, cfg: SettingsDep, sid: SessionDep, sh: ShellsDep
) -> s.ExecOut:
    cwd = jail(cfg, body.cwd)
    if not cwd.is_dir():
        raise SandboxError(404, "not_found", f"cwd {cwd} is not a directory")
    if body.background:
        res = await sh.start(sid, body.command, cwd, body.stdin)
    else:
        res = await sh.run(sid, body.command, cwd, body.timeout_s, body.stdin)
    return s.ExecOut(**vars(res))


@router.post("/output", operation_id="exec_output")
async def output(body: s.ShellIn, sid: SessionDep, sh: ShellsDep) -> s.ShellOutput:
    res, running = sh.output(sid, body.shell_id)
    return s.ShellOutput(
        stdout=res.stdout, stderr=res.stderr, running=running, exit_code=res.exit_code
    )


@router.post("/kill", operation_id="exec_kill")
async def kill(body: s.ShellIn, sid: SessionDep, sh: ShellsDep) -> s.Ok:
    await sh.kill(sid, body.shell_id)
    return s.Ok()
