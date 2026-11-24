"""GET /v1/skills and /v1/skills/{name}."""

from dot_contracts.skills import SkillDetail, SkillInfo
from fastapi import Request

from backend.cognition.services.skills import files, frontmatter
from backend.cognition.services.skills.model import Skill
from backend.core.api.auth import protected_router
from backend.core.exceptions import DomainException

router = protected_router(prefix="/v1/skills", tags=["skills"])
NOT_FOUND = 1002


def to_info(s: Skill) -> SkillInfo:
    return SkillInfo(
        name=s.name,
        description=s.description,
        source=s.source,
        available=s.available,
        reason=s.reason,
        model_invocable=s.model_invocable,
    )


@router.get("")
async def list_skills(request: Request) -> list[SkillInfo]:
    await request.app.state.skills.ensure_binaries()
    index = request.app.state.skills.index(fresh=True)
    return [to_info(s) for s in sorted(index.skills.values(), key=lambda s: s.name)]


@router.get("/{name}")
async def get_skill(request: Request, name: str) -> SkillDetail:
    await request.app.state.skills.ensure_binaries()
    skill = request.app.state.skills.index(fresh=True).skills.get(name)
    if skill is None:
        raise DomainException(NOT_FOUND)
    return SkillDetail(
        **to_info(skill).model_dump(),
        license=skill.license,
        allowed_tools=skill.allowed_tools,
        requires=skill.requires.as_dict(),
        body=frontmatter.read_body(skill.path),
        files=files.list_files(skill.path),
    )
