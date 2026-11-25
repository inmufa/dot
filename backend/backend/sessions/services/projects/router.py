from dot_contracts.ui.files import Project, ProjectIn, ProjectPatch
from fastapi import Request

from backend.core.api.auth import protected_router
from backend.sessions.services.projects.service import ProjectService

router = protected_router(prefix="/v1/projects", tags=["projects"])


def service(request: Request) -> ProjectService:
    return request.app.state.projects


@router.get("")
async def list_projects(request: Request) -> list[Project]:
    return await service(request).list_all()


@router.post("", status_code=201)
async def create_project(request: Request, body: ProjectIn) -> Project:
    return await service(request).create(body.name, body.instructions)


@router.patch("/{name}")
async def patch_project(request: Request, name: str, body: ProjectPatch) -> Project:
    return await service(request).update(name, body.instructions)
