"""GET/POST /v1/schedules, DELETE /v1/schedules/{id}."""

from dot_contracts.schedules import ScheduleIn, ScheduleInfo
from fastapi import Request

from backend.core.api.auth import protected_router

router = protected_router(prefix="/v1/schedules", tags=["schedules"])


@router.get("")
async def list_schedules(request: Request) -> list[ScheduleInfo]:
    return await request.app.state.jobs.all()


@router.post("", status_code=201)
async def create_schedule(request: Request, body: ScheduleIn) -> ScheduleInfo:
    return await request.app.state.jobs.create(
        body.cron, body.prompt, enabled=body.enabled
    )


@router.get("/{job_id}")
async def get_schedule(request: Request, job_id: str) -> ScheduleInfo:
    return await request.app.state.jobs.get(job_id)


@router.delete("/{job_id}")
async def delete_schedule(request: Request, job_id: str) -> dict[str, bool]:
    await request.app.state.jobs.delete(job_id)
    return {"ok": True}
