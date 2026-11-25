"""Find the login form: one DOM scan, then a pure planning step."""

import re
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page

# Tags every input with data-dot-i and describes it. Nothing is read from values.
SCAN_JS = """() => {
  const vis = (e) => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    if (r.width < 4 || r.height < 4 || s.visibility === 'hidden'
        || s.display === 'none' || parseFloat(s.opacity) < 0.1) return false;
    if (e.closest('[aria-hidden="true"],[hidden],[inert]')) return false;
    return r.right > 0 && r.bottom + scrollY > 0 && r.left < document.documentElement.scrollWidth;
  };
  const abs = (a) => { try { return new URL(a, document.baseURI).href; } catch { return 'invalid:'; } };
  const forms = [...document.forms];
  return [...document.querySelectorAll('input')].map((e, i) => {
    e.setAttribute('data-dot-i', String(i));
    const f = e.form;
    const acts = [];
    if (f) {
      acts.push(f.hasAttribute('action') ? abs(f.getAttribute('action')) : location.href);
      f.querySelectorAll('[formaction]').forEach((b) => acts.push(abs(b.getAttribute('formaction'))));
    }
    return {
      i, type: (e.getAttribute('type') || 'text').toLowerCase(),
      name: e.name || '', id: e.id || '', ac: (e.autocomplete || '').toLowerCase(),
      mode: (e.inputMode || '').toLowerCase(), max: e.maxLength,
      label: ((e.getAttribute('aria-label') || '') + ' ' + (e.placeholder || '')).slice(0, 120),
      form: f ? forms.indexOf(f) : -1, actions: acts, visible: vis(e),
    };
  });
}"""

TEXTY = {"text", "email", "tel"}
USER_HINT = re.compile(r"user|login|e-?mail|phone|account|ident|member|uname", re.I)
OTP_HINT = re.compile(
    r"otp|totp|2fa|mfa|verif|authenticator|security.?code|one.?time", re.I
)
NOT_USER = re.compile(r"search|query|^q$|newsletter|coupon|promo", re.I)


@dataclass
class Plan:
    kind: str  # full | username_only | password_only | otp | none
    user: int | None = None
    password: int | None = None
    otp: int | None = None
    actions: list[str] = field(default_factory=list)
    hidden_password: bool = False


def _text(d: dict[str, Any]) -> str:
    return f"{d['name']} {d['id']} {d['label']}"


def _is_otp(d: dict[str, Any]) -> bool:
    if d["ac"] == "one-time-code" or OTP_HINT.search(_text(d)):
        return True
    return d["mode"] == "numeric" and 4 <= d["max"] <= 8  # noqa: PLR2004


def _is_user(d: dict[str, Any]) -> bool:
    if d["type"] not in TEXTY or _is_otp(d):
        return False
    return d["ac"] in ("username", "email") or not NOT_USER.search(_text(d))


def plan(inputs: list[dict[str, Any]]) -> Plan:
    """Decide what to fill on this page. Only visible inputs are ever chosen."""
    shown = [d for d in inputs if d["visible"]]
    pws = [d for d in shown if d["type"] == "password"]
    hidden_pw = any(d["type"] == "password" and not d["visible"] for d in inputs)
    if pws:
        p = pws[0]
        before = [d for d in shown if d["i"] < p["i"] and _is_user(d)]
        same = [d for d in before if d["form"] == p["form"]]
        user = (same or before or [None])[-1]
        kind = "full" if user else "password_only"
        return Plan(kind, user["i"] if user else None, p["i"], None, p["actions"])
    otp = next(
        (d for d in shown if d["type"] in TEXTY | {"number"} and _is_otp(d)), None
    )
    if otp:
        return Plan(
            "otp", otp=otp["i"], actions=otp["actions"], hidden_password=hidden_pw
        )
    pick = [d for d in shown if _is_user(d)]
    hinted = [
        d
        for d in pick
        if d["ac"] in ("username", "email") or USER_HINT.search(_text(d))
    ]
    user = (hinted or pick or [None])[0]
    if user:
        return Plan("username_only", user["i"], actions=user["actions"])
    return Plan("none", hidden_password=hidden_pw)


async def scan(page: Page) -> list[dict[str, Any]]:
    return await page.evaluate(SCAN_JS)


async def child_frame_has_password(page: Page) -> bool:
    for frame in page.frames[1:]:
        try:
            if await frame.locator("input[type=password]").count():
                return True
        except Exception:  # noqa: BLE001, S112
            continue
    return False
