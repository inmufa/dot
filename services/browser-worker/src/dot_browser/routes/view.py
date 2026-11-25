"""Owner-facing view: cheap JPEG frames, pointer and keyboard input.

The page is the same one the agent drives. Frames and state never take the
session lock (they must not queue behind a slow agent action), and nothing
here returns page text into a model context.
"""

import asyncio
import contextlib
from typing import Any

from fastapi import APIRouter, Depends, Response
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from dot_browser.errors import BrowserError
from dot_browser.routes import schemas as s
from dot_browser.routes.actions import _raise_blocked, _settle, state
from dot_browser.routes.deps import ManagerDep, SessionDep, SettingsDep, require_token
from dot_browser.session import SessionContext

router = APIRouter(prefix="/view", dependencies=[Depends(require_token)])
LOADING_JS = "document.readyState !== 'complete'"
# Owner navigation returns once the server answers; frames show the page as it paints.
OWNER_WAIT = "commit"
PROBE_S = 0.5


def _live(mgr: ManagerDep, session: str) -> SessionContext | None:
    """Existing context only: viewing never launches Chromium."""
    return mgr.sessions.get(session)


def _page(entry: SessionContext, tab: str | None) -> Page:
    tid = tab or entry.active
    page = entry.tabs.get(tid) if tid else None
    if page is None:
        raise BrowserError(404, "no_such_tab", f"unknown tab {tab!r}")
    return page


async def _loading(page: Page) -> bool:
    try:
        return bool(await asyncio.wait_for(page.evaluate(LOADING_JS), PROBE_S))
    except (TimeoutError, PlaywrightError):
        return True


async def _title(page: Page) -> str:
    """Title without waiting on a navigating page (title() blocks until the new document)."""
    try:
        return (await asyncio.wait_for(page.title(), PROBE_S))[:300]
    except (TimeoutError, PlaywrightError):
        return ""


async def _history(page: Page) -> tuple[bool, bool]:
    """(can_back, can_forward) from Chromium's navigation list; unknown -> both True."""
    try:
        cdp = await page.context.new_cdp_session(page)
    except PlaywrightError:
        return True, True
    try:
        h = await asyncio.wait_for(cdp.send("Page.getNavigationHistory"), PROBE_S)
        idx, items = int(h["currentIndex"]), h["entries"]
        # the blank page a new tab starts on is not worth going back to
        back = any(e.get("url") != "about:blank" for e in items[:idx])
        return back, idx < len(items) - 1
    except (TimeoutError, PlaywrightError, KeyError, ValueError, TypeError):
        return True, True
    finally:
        with contextlib.suppress(PlaywrightError):
            await cdp.detach()


@router.get("/state")
async def view_state(session: SessionDep, mgr: ManagerDep) -> dict[str, Any]:
    entry = _live(mgr, session)
    if entry is None or not entry.tabs:
        return {
            "open": False,
            "tabs": [],
            "active": None,
            "viewport": mgr.viewports.get(session),
            "tainted": True,
        }
    page = _page(entry, None)
    tabs = [
        {"tab": t, "url": p.url[:2000], "title": await _title(p)}
        for t, p in list(entry.tabs.items())
    ]
    back, fwd = await _history(page)
    return {
        "open": True,
        "tabs": tabs,
        "active": entry.active,
        "tainted": True,
        "url": page.url[:2000],
        "title": next((t["title"] for t in tabs if t["tab"] == entry.active), ""),
        "loading": await _loading(page),
        "can_back": back,
        "can_forward": fwd,
        "viewport": page.viewport_size or {"width": 0, "height": 0},
        "blocked": entry.reason(),
    }


@router.post("/viewport")
async def viewport(
    body: s.ViewportBody, session: SessionDep, mgr: ManagerDep, cfg: SettingsDep
) -> dict[str, Any]:
    """Resize the shared page (all tabs) to the owner's panel. Never launches Chromium."""
    size = {
        "width": max(cfg.view_min_width, min(cfg.view_max_width, body.width)),
        "height": max(cfg.view_min_height, min(cfg.view_max_height, body.height)),
    }
    mgr.remember_viewport(session, size)
    entry = _live(mgr, session)
    if entry is not None:
        async with entry.lock:
            await entry.resize(size)
    return {"viewport": size, "tainted": True}


@router.post("/frame")
async def frame(
    body: s.FrameBody, session: SessionDep, mgr: ManagerDep, cfg: SettingsDep
) -> Response:
    entry = _live(mgr, session)
    if entry is None or not entry.tabs or entry.masked:
        return Response(status_code=204)
    page = _page(entry, body.tab)
    quality = body.quality
    for _ in range(2):
        try:
            data = await page.screenshot(
                type="jpeg", quality=quality, scale="css", timeout=3_000
            )
        except PlaywrightError as exc:
            raise BrowserError(
                502, "frame_failed", str(exc).splitlines()[0][:200]
            ) from exc
        if len(data) <= cfg.max_frame_bytes:
            return Response(data, media_type="image/jpeg")
        quality = 30
    raise BrowserError(413, "frame_too_large", f"{len(data)} bytes over cap")


def _inside(page: Page, x: float, y: float) -> None:
    size = page.viewport_size
    if size and (x > size["width"] or y > size["height"]):
        raise BrowserError(422, "out_of_view", "point is outside the viewport")


@router.post("/click")
async def click_at(
    body: s.ClickAt, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        _inside(page, body.x, body.y)
        entry.reset_marks()
        await page.mouse.click(
            body.x, body.y, button=body.button, click_count=body.clicks
        )
        await _settle(page)
        return await state(entry, page, blocked=entry.reason())


@router.post("/type")
async def type_text(
    body: s.TextBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        await page.keyboard.type(body.text)
        return await state(entry, page)


@router.post("/wheel")
async def wheel(
    body: s.WheelBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        await page.mouse.move(body.x, body.y)
        await page.mouse.wheel(body.dx, body.dy)
        return await state(entry, page)


@router.post("/forward")
async def forward(body: s.Body, session: SessionDep, mgr: ManagerDep) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        resp = await page.go_forward(wait_until=OWNER_WAIT)
        _raise_blocked(entry)
        return await state(entry, page, moved=resp is not None)


@router.post("/back")
async def back(body: s.Body, session: SessionDep, mgr: ManagerDep) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        resp = await page.go_back(wait_until=OWNER_WAIT)
        _raise_blocked(entry)
        return await state(entry, page, moved=resp is not None)


@router.post("/reload")
async def reload(body: s.Body, session: SessionDep, mgr: ManagerDep) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        with contextlib.suppress(PlaywrightError):
            await page.reload(wait_until=OWNER_WAIT)
        _raise_blocked(entry)
        return await state(entry, page)
