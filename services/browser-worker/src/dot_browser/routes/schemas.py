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
    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load"


class SwitchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab: str


class CloseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab: str | None = None


class FrameBody(Body):
    quality: int = Field(default=55, ge=20, le=85)


class ClickAt(Body):
    x: float = Field(ge=0, le=20_000)
    y: float = Field(ge=0, le=20_000)
    button: Literal["left", "right", "middle"] = "left"
    clicks: int = Field(default=1, ge=1, le=2)


class WheelBody(Body):
    x: float = Field(default=0, ge=0, le=20_000)
    y: float = Field(default=0, ge=0, le=20_000)
    dy: float = Field(ge=-5_000, le=5_000)
    dx: float = Field(default=0, ge=-5_000, le=5_000)


class TextBody(Body):
    text: str = Field(min_length=1, max_length=2_000)


class ViewportBody(BaseModel):
    """Panel size in CSS pixels; clamped to the configured bounds, not rejected."""

    model_config = ConfigDict(extra="forbid")

    width: int = Field(ge=1, le=10_000)
    height: int = Field(ge=1, le=10_000)
