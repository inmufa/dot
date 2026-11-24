"""Readable-markdown extraction and capped screenshots."""

import asyncio
import base64
from typing import Any

import trafilatura
from playwright.async_api import Page

from dot_browser.errors import BrowserError
from dot_browser.settings import Settings
from dot_browser.snapshot import tidy

PAGE_HEIGHT_JS = "() => document.documentElement.scrollHeight"


def _markdown(html: str) -> str:
    out = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        favor_recall=True,
    )
    return out or ""


async def extract(page: Page, goal: str | None, cfg: Settings) -> dict[str, Any]:
    if goal:
        loc = page.locator(goal).first
        if await page.locator(goal).count() == 0:
            raise BrowserError(404, "element_not_found", f"no match for {goal!r}")
        html = await loc.evaluate("(e) => e.outerHTML")
        fallback = await loc.inner_text()
    else:
        html = await page.content()
        fallback = await page.locator("body").inner_text()
    html = html[: cfg.max_html_bytes]
    md = await asyncio.to_thread(_markdown, html) or fallback
    text, cut = tidy(md, cfg.max_extract_chars)
    return {"markdown": text, "truncated": cut}


async def screenshot(page: Page, *, full_page: bool, cfg: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"type": "png"}
    if full_page:
        height = min(int(await page.evaluate(PAGE_HEIGHT_JS)), cfg.max_full_page_px)
        width = page.viewport_size["width"] if page.viewport_size else 1280
        kwargs.update(
            full_page=True, clip={"x": 0, "y": 0, "width": width, "height": height}
        )
    data = await page.screenshot(**kwargs)
    mime = "image/png"
    if len(data) > cfg.max_screenshot_bytes:
        kwargs.update(type="jpeg", quality=55)
        data = await page.screenshot(**kwargs)
        mime = "image/jpeg"
    if len(data) > cfg.max_screenshot_bytes:
        raise BrowserError(413, "screenshot_too_large", f"{len(data)} bytes over cap")
    return {
        "mime": mime,
        "bytes": len(data),
        "data": base64.b64encode(data).decode(),
    }
