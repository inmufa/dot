"""Public skill DTOs served under /v1/skills."""

from typing import Literal

from pydantic import BaseModel

SkillSource = Literal["workspace", "user", "bundled"]


class SkillInfo(BaseModel):
    name: str
    description: str
    source: SkillSource
    available: bool
    reason: str | None = None
    model_invocable: bool = True


class SkillDetail(SkillInfo):
    license: str | None = None
    allowed_tools: list[str] = []
    requires: dict[str, list[str]] = {}
    body: str
    files: list[str] = []
