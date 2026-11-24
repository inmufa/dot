"""Page actions. Everything returned from a page is untrusted (tainted)."""

import contextlib
from typing import Any

from fastapi import APIRouter, Depends
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page

from dot_browser import content, snapshot
from dot_browser.errors import BrowserError
from dot_browser.guard import Blocked
from dot_browser.routes import schemas as s
from dot_browser.routes.deps import (
    GuardDep,
    ManagerDep,
    SessionDep,
    SettingsDep,
    require_token,
)
from dot_browser.session import SessionContext

router = APIRouter(dependencies=[Depends(require_token)])
SCROLL_JS = (
    "([dir, amt]) => { const h = document.documentElement.scrollHeight;"
    " const y = dir === 'top' ? 0 : dir === 'bottom' ? h"
    " : window.scrollY + (dir === 'down' ? amt : -amt);"
    " window.scrollTo(0, Math.max(0, y)); return Math.round(window.scrollY); }"
)


async def state(entry: SessionContext, page: Page, **extra: Any) -> dict[str, Any]:
    return {
        "tab": entry.tab_of(page),
        "url": page.url[:2000],
        "title": (await page.title())[:300],
        "blocked_requests": len(entry.blocked()),
        "tainted": True,
        **extra,
    }


def _locator(page: Page, target: s.Target) -> Locator:
    if target.element_id is not None:
        return page.locator(f'[data-dot-id="{int(target.element_id)}"]').first
    assert target.selector is not None  # noqa: S101
    return page.locator(target.selector).first


async def _resolve(page: Page, target: s.Target) -> Locator:
    loc = _locator(page, target)
    if await loc.count() == 0:
        raise BrowserError(
            404, "element_not_found", "no such element; take a fresh /snapshot"
        )
    return loc


def _raise_blocked(entry: SessionContext) -> None:
    if reason := entry.reason():
        raise BrowserError(403, "ssrf_blocked", reason)


async def _settle(page: Page) -> None:
    """After an action that may navigate: let it settle briefly."""
    with contextlib.suppress(PlaywrightError):
        await page.wait_for_load_state("domcontentloaded", timeout=2_000)


async def _enforce_redirects(page: Page, entry: SessionContext, resp: Any) -> None:
    hops, prev = 0, resp.request.redirected_from if resp else None
    while prev:
        hops, prev = hops + 1, prev.redirected_from
    if hops > entry.cfg.max_redirects:
        await page.goto("about:blank")
        raise BrowserError(403, "ssrf_blocked", f"too many redirects ({hops})")


@router.post("/nav")
async def nav(
    body: s.NavBody, session: SessionDep, mgr: ManagerDep, guard: GuardDep
) -> dict[str, Any]:
    try:
        await guard.check(body.url, navigation=True)
    except Blocked as exc:
        raise BrowserError(403, "ssrf_blocked", str(exc)) from exc
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        try:
            resp = await page.goto(body.url, wait_until=body.wait_until)
        except PlaywrightError:
            _raise_blocked(entry)
            raise
        await _enforce_redirects(page, entry, resp)
        status = resp.status if resp else None
        return await state(entry, page, status=status)


@router.post("/snapshot")
async def snap(
    body: s.Body, session: SessionDep, mgr: ManagerDep, cfg: SettingsDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        view = await snapshot.distill(page, cfg)
        return await state(entry, page, **view)


@router.post("/click")
async def click(body: s.Target, session: SessionDep, mgr: ManagerDep) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        await (await _resolve(page, body)).click()
        await _settle(page)
        return await state(entry, page)


@router.post("/type")
async def type_(
    body: s.TypeBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        loc = await _resolve(page, body)
        await loc.fill(body.text)
        if body.submit:
            await loc.press("Enter")
            await _settle(page)
        return await state(entry, page)


@router.post("/select")
async def select(
    body: s.SelectBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        loc = await _resolve(page, body)
        try:
            await loc.select_option(label=body.value)
        except PlaywrightError:
            await loc.select_option(value=body.value)
        return await state(entry, page)


@router.post("/scroll")
async def scroll(
    body: s.ScrollBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        y = await page.evaluate(SCROLL_JS, [body.direction, body.amount])
        return await state(entry, page, scroll_y=y)


@router.post("/back")
async def back(body: s.Body, session: SessionDep, mgr: ManagerDep) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        resp = await page.go_back()
        return await state(entry, page, moved=resp is not None)


@router.post("/press")
async def press(
    body: s.PressBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.reset_marks()
        await page.keyboard.press(body.key)
        await _settle(page)
        return await state(entry, page)


@router.post("/extract")
async def extract(
    body: s.ExtractBody, session: SessionDep, mgr: ManagerDep, cfg: SettingsDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        out = await content.extract(page, body.goal, cfg)
        return await state(entry, page, **out)


@router.post("/screenshot")
async def shot(
    body: s.ShotBody, session: SessionDep, mgr: ManagerDep, cfg: SettingsDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        out = await content.screenshot(page, full_page=body.full_page, cfg=cfg)
        return await state(entry, page, **out)
