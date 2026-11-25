"""Vault routes: login fill, session export and restore. Token-authed like the rest."""

import contextlib
from typing import Any

from fastapi import APIRouter, Depends
from playwright.async_api import Error as PlaywrightError

from dot_browser.errors import BrowserError
from dot_browser.guard import Blocked
from dot_browser.routes import actions
from dot_browser.routes import vault_schemas as v
from dot_browser.routes.deps import GuardDep, ManagerDep, SessionDep, require_token
from dot_browser.vault import flow, loginform, state
from dot_browser.vault.origin import origin_matches

router = APIRouter(prefix="/vault", dependencies=[Depends(require_token)])


@router.post("/login")
async def login(
    body: v.LoginBody, session: SessionDep, mgr: ManagerDep, guard: GuardDep
) -> dict[str, Any]:
    if body.url:
        if not origin_matches(body.url, body.origins):
            raise BrowserError(
                403, "origin_mismatch", "url is not bound to this credential"
            )
        try:
            await guard.check(body.url, navigation=True)
        except Blocked as exc:
            raise BrowserError(403, "ssrf_blocked", str(exc)) from exc
    creds = flow.Creds(
        body.username,
        body.password.get_secret_value(),
        body.totp_secret.get_secret_value() if body.totp_secret else None,
        body.origins,
    )
    async with mgr.use(session) as entry:
        entry.masked = True
        try:
            page = await entry.page(body.tab)
            if body.url:
                entry.reset_marks()
                try:
                    resp = await page.goto(body.url)
                except PlaywrightError:
                    actions._raise_blocked(entry)  # noqa: SLF001
                    raise
                await actions._enforce_redirects(page, entry, resp)  # noqa: SLF001
            outcome = await flow.run(page, creds)
            return flow.result(outcome, page, await flow.safe_title(page))
        except PlaywrightError as exc:
            # Playwright text can quote what was typed: report only a fixed reason.
            raise BrowserError(502, "action_failed", "login step failed") from exc
        finally:
            entry.masked = False
            del creds


@router.post("/session/export")
async def export(
    body: v.ExportBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    entry = mgr.sessions.get(session)
    if entry is None:
        raise BrowserError(404, "no_session", "no live browser context")
    async with entry.lock:  # no last_used bump: exporting must not keep a context alive
        raw = await entry.context.storage_state()
    return state.filter_state(raw, body.origins)


@router.post("/session/restored")
async def restored(
    body: v.RestoredBody, session: SessionDep, mgr: ManagerDep
) -> dict[str, Any]:
    entry = mgr.sessions.get(session)
    known = entry.restored if entry else set()
    return {"restored": [i for i in body.ids if i in known]}


@router.post("/session/restore")
async def restore(
    body: v.RestoreBody, session: SessionDep, mgr: ManagerDep, guard: GuardDep
) -> dict[str, Any]:
    if body.url:
        if not origin_matches(body.url, body.origins):
            raise BrowserError(
                403, "origin_mismatch", "url is not bound to this credential"
            )
        try:
            await guard.check(body.url, navigation=True)
        except Blocked as exc:
            raise BrowserError(403, "ssrf_blocked", str(exc)) from exc
    clean = state.filter_state(body.state, body.origins)
    async with mgr.use(session) as entry:
        count = await state.apply(entry, body.id, clean)
        form = None
        if body.url:
            page = await entry.page(None)
            entry.reset_marks()
            with contextlib.suppress(PlaywrightError):
                resp = await page.goto(body.url)
                await actions._enforce_redirects(page, entry, resp)  # noqa: SLF001
            if origin_matches(page.url, body.origins):
                plan = loginform.plan(await loginform.scan(page))
                form = plan.kind in ("full", "password_only", "username_only")
        return {"restored": count, "login_form": form, "tainted": True}
