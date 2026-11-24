"""Request bodies."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab: str | None = None


class NavBody(Body):
    url: str = Field(min_length=1, max_length=4096)
    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load"


class Target(Body):
    element_id: int | None = Field(default=None, ge=1)
    selector: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def _one_target(self) -> "Target":
        if (self.element_id is None) == (self.selector is None):
            msg = "give exactly one of element_id or selector"
            raise ValueError(msg)
        return self


class TypeBody(Target):
    text: str = Field(max_length=10_000)
    submit: bool = False


class SelectBody(Target):
    value: str = Field(min_length=1, max_length=500)


class ScrollBody(Body):
    direction: Literal["up", "down", "top", "bottom"] = "down"
    amount: int = Field(default=600, ge=1, le=20_000)


class PressBody(Body):
    key: str = Field(pattern=r"^[A-Za-z0-9+_ ]{1,40}$")


class ExtractBody(Body):
    goal: str | None = Field(default=None, max_length=500)


class ShotBody(Body):
    full_page: bool = False


class NewTabBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, max_length=4096)


class SwitchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab: str


class CloseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab: str | None = None
