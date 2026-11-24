"""Tab listing, switching, opening and closing sessions."""

from typing import Any

from fastapi import APIRouter, Depends

from dot_browser.errors import BrowserError
from dot_browser.guard import Blocked
from dot_browser.routes import schemas as s
from dot_browser.routes.actions import state
from dot_browser.routes.deps import GuardDep, ManagerDep, SessionDep, require_token
from dot_browser.session import SessionContext

router = APIRouter(dependencies=[Depends(require_token)])


async def listing(entry: SessionContext) -> dict[str, Any]:
    tabs = [
        {"tab": t, "url": p.url[:2000], "title": (await p.title())[:300]}
        for t, p in entry.tabs.items()
    ]
    return {"tabs": tabs, "active": entry.active, "tainted": True}


@router.get("/tabs")
async def tabs(session: SessionDep, mgr: ManagerDep) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        return await listing(entry)


@router.post("/tabs/new")
async def new_tab(
    body: s.NewTabBody, session: SessionDep, mgr: ManagerDep, guard: GuardDep
) -> dict[str, Any]:
    if body.url:
        try:
            await guard.check(body.url, navigation=True)
        except Blocked as exc:
            raise BrowserError(403, "ssrf_blocked", str(exc)) from exc
    async with mgr.use(session) as entry:
        page = await entry.new_tab()
        if body.url:
            entry.reset_marks()
            await page.goto(body.url)
            if reason := entry.reason():
                await page.close()
                raise BrowserError(403, "ssrf_blocked", reason)
        return await state(entry, page)


@router.post("/tabs/switch")
async def switch(
    body: s.SwitchBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        entry.active = body.tab
        await page.bring_to_front()
        return await state(entry, page)


@router.post("/close")
async def close(
    body: s.CloseBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    """Close one tab, or the whole session when no tab is given."""
    if body.tab is None:
        return {"closed": await mgr.close_session(session), "session": True}
    async with mgr.use(session) as entry:
        page = await entry.page(body.tab)
        await page.close()
        return {"closed": True, "session": False, "active": entry.active}
