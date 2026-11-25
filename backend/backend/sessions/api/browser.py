"""Owner view of the session's shared browser (docs/api-contract.md "Browser view")."""

from typing import Annotated, Literal

from fastapi import Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.core.api.auth import protected_router
from backend.sessions.services.browser_view import BrowserView
from backend.sessions.services.session_service import SessionService

router = protected_router(prefix="/v1/sessions/{session_id}/browser", tags=["browser"])
Tab = Annotated[str | None, Field(default=None, max_length=16)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab: Tab = None


class UrlIn(_In):
    url: str = Field(min_length=1, max_length=4096)


class ClickIn(_In):
    x: float = Field(ge=0, le=20_000)
    y: float = Field(ge=0, le=20_000)
    button: Literal["left", "right", "middle"] = "left"
    clicks: int = Field(default=1, ge=1, le=2)


class TypeIn(_In):
    text: str = Field(min_length=1, max_length=2_000)


class PressIn(_In):
    key: str = Field(pattern=r"^[A-Za-z0-9+_ ]{1,40}$")


class ScrollIn(_In):
    x: float = Field(default=0, ge=0, le=20_000)
    y: float = Field(default=0, ge=0, le=20_000)
    dy: float = Field(ge=-5_000, le=5_000)
    dx: float = Field(default=0, ge=-5_000, le=5_000)


class ViewportIn(BaseModel):
    """Panel size in CSS pixels; the worker clamps it to 320-1920 x 320-1600."""

    model_config = ConfigDict(extra="forbid")

    width: int = Field(ge=1, le=10_000)
    height: int = Field(ge=1, le=10_000)


class NewTabIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, max_length=4096)


class TabIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab: str = Field(min_length=1, max_length=16)


class BrowserTabOut(BaseModel):
    tab: str
    url: str
    title: str


class BrowserViewport(BaseModel):
    width: int
    height: int


class BrowserStateOut(BaseModel):
    open: bool
    tabs: list[BrowserTabOut] = []
    active: str | None = None
    url: str = ""
    title: str = ""
    loading: bool = False
    can_back: bool = True
    can_forward: bool = True
    viewport: BrowserViewport | None = None
    blocked: str | None = None
    agent_acting: bool
    agent_seq: int
    status: int | None = None


async def _view(request: Request, session_id: str, kind: str) -> BrowserView:
    """Rate-limit, then check the session exists. Returns the shared service."""
    view: BrowserView = request.app.state.browser_view
    view.limit(request, kind)
    await SessionService(request.app.state.sessions).get(session_id)
    return view


@router.get("/state")
async def state(request: Request, session_id: str) -> BrowserStateOut:
    view = await _view(request, session_id, "view")
    return BrowserStateOut(**await view.state(session_id))


@router.post("/frame")
async def frame(request: Request, session_id: str, body: _In) -> Response:
    """JPEG of the active tab (204 when no page is open yet)."""
    view = await _view(request, session_id, "view")
    data = await view.frame(session_id, body.tab)
    if data is None:
        return Response(status_code=204)
    return Response(data, media_type="image/jpeg")


async def _act(
    request: Request, session_id: str, kind: str, body: dict, note: dict
) -> BrowserStateOut:
    view = await _view(request, session_id, "input")
    return BrowserStateOut(**await view.act(session_id, kind, body, note))


@router.post("/navigate")
async def navigate(request: Request, session_id: str, body: UrlIn) -> BrowserStateOut:
    return await _act(
        request,
        session_id,
        "navigate",
        body.model_dump(exclude_none=True),
        {"url": body.url},
    )


@router.post("/back")
async def back(request: Request, session_id: str, body: _In) -> BrowserStateOut:
    return await _act(
        request, session_id, "back", body.model_dump(exclude_none=True), {}
    )


@router.post("/forward")
async def forward(request: Request, session_id: str, body: _In) -> BrowserStateOut:
    return await _act(
        request, session_id, "forward", body.model_dump(exclude_none=True), {}
    )


@router.post("/reload")
async def reload(request: Request, session_id: str, body: _In) -> BrowserStateOut:
    return await _act(
        request, session_id, "reload", body.model_dump(exclude_none=True), {}
    )


@router.post("/click")
async def click(request: Request, session_id: str, body: ClickIn) -> BrowserStateOut:
    note = {"x": round(body.x), "y": round(body.y), "button": body.button}
    return await _act(
        request, session_id, "click", body.model_dump(exclude_none=True), note
    )


@router.post("/type")
async def type_text(request: Request, session_id: str, body: TypeIn) -> BrowserStateOut:
    # Typed text can be a password: only its length is audited.
    note = {"chars": len(body.text)}
    return await _act(
        request, session_id, "type", body.model_dump(exclude_none=True), note
    )


@router.post("/press")
async def press(request: Request, session_id: str, body: PressIn) -> BrowserStateOut:
    return await _act(
        request,
        session_id,
        "press",
        body.model_dump(exclude_none=True),
        {"key": body.key},
    )


@router.post("/scroll")
async def scroll(request: Request, session_id: str, body: ScrollIn) -> BrowserStateOut:
    return await _act(
        request, session_id, "scroll", body.model_dump(exclude_none=True), {}
    )


@router.post("/tabs/new")
async def tab_new(request: Request, session_id: str, body: NewTabIn) -> BrowserStateOut:
    note = {"url": body.url} if body.url else {}
    return await _act(
        request, session_id, "tab_new", body.model_dump(exclude_none=True), note
    )


@router.post("/tabs/switch")
async def tab_switch(request: Request, session_id: str, body: TabIn) -> BrowserStateOut:
    return await _act(
        request, session_id, "tab_switch", body.model_dump(), {"tab": body.tab}
    )


@router.post("/tabs/close")
async def tab_close(request: Request, session_id: str, body: TabIn) -> BrowserStateOut:
    return await _act(
        request, session_id, "tab_close", body.model_dump(), {"tab": body.tab}
    )


@router.post("/viewport")
async def viewport(
    request: Request, session_id: str, body: ViewportIn
) -> BrowserStateOut:
    """Fit the shared page to the owner's panel (all tabs; the agent sees the same size)."""
    return await _act(request, session_id, "viewport", body.model_dump(), {})
