"""Fill a login with vault secrets. Never screenshots, never echoes a secret."""

import asyncio
import contextlib
import re
from dataclasses import dataclass
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from dot_browser.errors import BrowserError
from dot_browser.vault import loginform
from dot_browser.vault.origin import origin_matches
from dot_browser.vault.totp import totp_code

CAPTCHA_JS = """() => !!document.querySelector(
  'iframe[src*="recaptcha"],iframe[src*="hcaptcha"],iframe[src*="turnstile"],'
  + '.g-recaptcha,.h-captcha,.cf-turnstile')"""
ERROR_TEXT = re.compile(
    r"incorrect|invalid|wrong|failed|try again|неверн|ошибк|noto.?g.?ri|xato", re.I
)
MAX_STEPS = 5


@dataclass
class Creds:
    username: str
    password: str
    totp_secret: str | None
    origins: list[str]


_ORIGIN = ("origin_mismatch", "page origin is not bound to this credential")
_ACTION = ("unsafe_form", "form posts to another origin")
_HIDDEN = ("unsafe_form", "login form is hidden")
_FRAMED = ("unsafe_form", "login form is inside a frame")


def _need_origin(page: Page, creds: Creds) -> None:
    if not origin_matches(page.url, creds.origins):
        raise BrowserError(403, *_ORIGIN)


def _need_actions(plan: loginform.Plan, creds: Creds) -> None:
    for action in plan.actions:
        if not origin_matches(action, creds.origins):
            raise BrowserError(403, *_ACTION)


async def _settle(page: Page) -> None:
    with contextlib.suppress(PlaywrightError):
        await page.wait_for_load_state("domcontentloaded", timeout=5_000)
    with contextlib.suppress(PlaywrightError):
        await page.wait_for_load_state("networkidle", timeout=4_000)


async def _changed(page: Page, before_kind: str, before_url: str, secs: float) -> None:
    """Wait until the page navigates or the form on it changes."""
    for _ in range(int(secs / 0.4)):
        await asyncio.sleep(0.4)
        if page.url != before_url:
            await _settle(page)
            return
        with contextlib.suppress(PlaywrightError):
            if loginform.plan(await loginform.scan(page)).kind != before_kind:
                return


async def _submit(page: Page, idx: int, kind: str) -> None:
    before = page.url
    loc = page.locator(f'[data-dot-i="{idx}"]').first
    await loc.press("Enter")
    await _changed(page, kind, before, 2.4)
    if page.url != before:
        return
    with contextlib.suppress(PlaywrightError):
        if loginform.plan(await loginform.scan(page)).kind != kind:
            return
        btn = page.locator(
            "form button[type=submit], form input[type=submit], form button:not([type])"
        ).first
        if await btn.count():
            await btn.click(timeout=2_000)
            await _changed(page, kind, before, 3.2)


async def _fill(page: Page, idx: int, value: str) -> None:
    await page.locator(f'[data-dot-i="{idx}"]').first.fill(value)


async def _captcha(page: Page) -> bool:
    with contextlib.suppress(PlaywrightError):
        return bool(await page.evaluate(CAPTCHA_JS))
    return False


async def _error_shown(page: Page) -> bool:
    with contextlib.suppress(PlaywrightError):
        text = await page.locator(
            '[role="alert"], .error, .alert, [class*="error"]'
        ).all_inner_texts()
        return any(ERROR_TEXT.search(t) for t in text)
    return False


async def _wipe(page: Page, plan: loginform.Plan) -> None:
    for idx in (plan.password, plan.otp):
        if idx is not None:
            with contextlib.suppress(PlaywrightError):
                await _fill(page, idx, "")


async def run(page: Page, creds: Creds) -> str:
    """Return an outcome code; raises BrowserError for refusals."""
    _need_origin(page, creds)
    done: set[str] = set()
    for _ in range(MAX_STEPS):
        _need_origin(page, creds)
        if await _captcha(page):
            return "captcha"
        plan = loginform.plan(await loginform.scan(page))
        outcome = await _step(page, creds, plan, done)
        if outcome:
            return outcome
    return "failed"


async def _none(page: Page, plan: loginform.Plan, done: set[str]) -> str:
    if done:
        return "wrong_credentials" if await _error_shown(page) else "logged_in"
    if plan.hidden_password:
        raise BrowserError(403, *_HIDDEN)
    if await loginform.child_frame_has_password(page):
        raise BrowserError(403, *_FRAMED)
    return "form_not_found"


async def _username(
    page: Page, creds: Creds, plan: loginform.Plan, done: set[str]
) -> str | None:
    if "password" in done or "otp" in done:
        return "logged_in"  # a stray text box on the page after login
    if "user" in done:
        return "wrong_credentials"
    _need_actions(plan, creds)
    assert plan.user is not None  # noqa: S101
    await _fill(page, plan.user, creds.username)
    done.add("user")
    await _submit(page, plan.user, plan.kind)
    return None


async def _step(
    page: Page, creds: Creds, plan: loginform.Plan, done: set[str]
) -> str | None:
    if plan.kind == "none":
        return await _none(page, plan, done)
    if plan.kind == "username_only":
        return await _username(page, creds, plan, done)
    if plan.kind == "otp":
        return await _otp(page, creds, plan, done)
    if "password" in done:
        await _wipe(page, plan)
        return "wrong_credentials"
    _need_actions(plan, creds)
    assert plan.password is not None  # noqa: S101
    if plan.user is not None and "user" not in done:
        await _fill(page, plan.user, creds.username)
        done.add("user")
    await _fill(page, plan.password, creds.password)
    done.add("password")
    await _submit(page, plan.password, plan.kind)
    return None


async def _otp(
    page: Page, creds: Creds, plan: loginform.Plan, done: set[str]
) -> str | None:
    if not creds.totp_secret:
        return "2fa_required"
    if "otp" in done:
        await _wipe(page, plan)
        return "wrong_credentials"
    _need_actions(plan, creds)
    assert plan.otp is not None  # noqa: S101
    await _fill(page, plan.otp, totp_code(creds.totp_secret))
    done.add("otp")
    await _submit(page, plan.otp, plan.kind)
    return None


def result(outcome: str, page: Page, title: str) -> dict[str, Any]:
    return {
        "ok": outcome == "logged_in",
        "outcome": outcome,
        "url": page.url[:2000],
        "title": title[:300],
        "tainted": True,
    }


async def safe_title(page: Page) -> str:
    with contextlib.suppress(PlaywrightError):
        return await page.title()
    return ""
