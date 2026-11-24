"""Page distillation: numbered interactive elements plus trimmed visible text.

The script below is fixed and internal; callers never supply JavaScript.
"""

import re
from typing import Any

from playwright.async_api import Page

from dot_browser.settings import Settings

SNAPSHOT_JS = r"""
(o) => {
  const SEL = 'a[href],button,input:not([type=hidden]),select,textarea,summary,'
    + '[role=button],[role=link],[role=checkbox],[role=radio],[role=tab],'
    + '[role=menuitem],[role=switch],[role=combobox],[role=textbox],'
    + '[role=searchbox],[role=option],[contenteditable=""],'
    + '[contenteditable="true"],[onclick],[tabindex]:not([tabindex="-1"])';
  const root = document.documentElement;
  let next = Number(root.getAttribute('data-dot-next') || 1);
  const clean = (s, n) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const ROLE = {a: 'link', button: 'button', select: 'combobox',
    textarea: 'textbox', summary: 'button'};
  const INPUT = {checkbox: 'checkbox', radio: 'radio', submit: 'button',
    button: 'button', reset: 'button', image: 'button', range: 'slider',
    search: 'searchbox'};
  const roleOf = (e) => {
    const r = e.getAttribute('role');
    if (r) return r;
    const t = e.tagName.toLowerCase();
    if (t === 'input') return INPUT[(e.type || '').toLowerCase()] || 'textbox';
    if (ROLE[t]) return ROLE[t];
    return e.isContentEditable ? 'textbox' : 'generic';
  };
  const nameOf = (e) => {
    let n = e.getAttribute('aria-label');
    if (!n && e.getAttribute('aria-labelledby')) {
      n = e.getAttribute('aria-labelledby').split(/\s+/).map((i) => {
        const x = document.getElementById(i); return x ? x.innerText : '';
      }).join(' ');
    }
    if (!n && e.labels && e.labels.length) n = e.labels[0].innerText;
    if (!n) n = e.getAttribute('alt') || e.getAttribute('title');
    if (!n) n = e.innerText;
    if (!n && e.tagName === 'INPUT' && /^(submit|button|reset)$/i.test(e.type)) n = e.value;
    if (!n) n = e.getAttribute('placeholder');
    return clean(n, o.maxName);
  };
  const valueOf = (e) => {
    const t = e.tagName;
    if (t === 'SELECT') return clean(Array.from(e.selectedOptions).map((x) => x.text).join(', '), o.maxName);
    if (t === 'TEXTAREA') return clean(e.value, o.maxName);
    if (t === 'INPUT') {
      const ty = (e.type || '').toLowerCase();
      if (ty === 'password') return e.value ? '(hidden)' : '';
      if (['checkbox', 'radio', 'submit', 'button', 'reset', 'image'].includes(ty)) return '';
      return clean(e.value, o.maxName);
    }
    return '';
  };
  const out = [];
  const seen = new Set();
  let truncated = false;
  for (const e of document.querySelectorAll(SEL)) {
    const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e);
    if (r.width <= 0 || r.height <= 0 || cs.visibility === 'hidden') continue;
    if (out.length >= o.maxElements) { truncated = true; break; }
    let id = Number(e.getAttribute('data-dot-id'));
    if (!id || seen.has(id)) { id = next++; e.setAttribute('data-dot-id', String(id)); }
    seen.add(id);
    const st = [];
    if (e.disabled) st.push('disabled');
    if (e.checked) st.push('checked');
    if (e.getAttribute('aria-expanded')) st.push('expanded=' + e.getAttribute('aria-expanded'));
    out.push({id, role: roleOf(e), name: nameOf(e), value: valueOf(e),
      href: e.tagName === 'A' ? clean(e.href, 200) : '', state: st.join(' ')});
  }
  root.setAttribute('data-dot-next', String(next));
  const text = document.body ? (document.body.innerText || '') : '';
  return {elements: out, truncated, text: text.slice(0, o.maxText * 2),
    scrollY: Math.round(window.scrollY), height: root.scrollHeight};
}
"""

_BLANKS = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t]+")


def tidy(text: str, limit: int) -> tuple[str, bool]:
    text = _BLANKS.sub("\n\n", _SPACES.sub(" ", text)).strip()
    return (text[:limit], True) if len(text) > limit else (text, False)


async def distill(page: Page, cfg: Settings) -> dict[str, Any]:
    raw = await page.evaluate(
        SNAPSHOT_JS,
        {
            "maxElements": cfg.max_elements,
            "maxName": cfg.max_name_chars,
            "maxText": cfg.max_text_chars,
        },
    )
    text, cut = tidy(raw["text"], cfg.max_text_chars)
    elements = [
        {k: v for k, v in el.items() if v not in ("", None)} for el in raw["elements"]
    ]
    return {
        "elements": elements,
        "elements_truncated": raw["truncated"],
        "text": text,
        "text_truncated": cut,
        "scroll_y": raw["scrollY"],
        "page_height": raw["height"],
    }
