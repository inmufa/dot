"""Storage state (cookies, localStorage) scoped to credential origins."""

import json
import time
from typing import Any

from dot_browser.session import SessionContext
from dot_browser.vault.origin import cookie_in_scope, origin_of

_MAX_STATE_BYTES = 2_000_000


def filter_state(raw: dict[str, Any], origins: list[str]) -> dict[str, Any]:
    """Keep only cookies and storage that belong to the bound origins; drop expired."""
    now = time.time()
    bound = {origin_of(o) for o in origins}
    cookies = [
        c
        for c in raw.get("cookies", [])
        if cookie_in_scope(str(c.get("domain", "")), origins)
        and not (0 < float(c.get("expires", -1)) <= now)
    ]
    stores = [
        {"origin": o["origin"], "localStorage": o.get("localStorage", [])}
        for o in raw.get("origins", [])
        if origin_of(str(o.get("origin", ""))) in bound and o.get("localStorage")
    ]
    out = {"cookies": cookies, "origins": stores}
    if len(json.dumps(out)) > _MAX_STATE_BYTES:
        return {"cookies": [], "origins": []}
    return out


_STORAGE_JS = """(items) => {
  const mine = items[location.origin];
  if (!mine) return;
  for (const [k, v] of mine) { try { localStorage.setItem(k, v); } catch (e) {} }
}"""


async def apply(entry: SessionContext, cred_id: str, clean: dict[str, Any]) -> int:
    """Install the (already filtered) state in this context; returns cookies added."""
    cookies = clean.get("cookies", [])
    if cookies:
        await entry.context.add_cookies(cookies)
    stores = {
        o["origin"]: [[i["name"], i["value"]] for i in o["localStorage"]]
        for o in clean.get("origins", [])
    }
    if stores:
        script = f"({_STORAGE_JS})({json.dumps(stores)})"
        await entry.context.add_init_script(script)
    entry.restored.add(cred_id)
    return len(cookies)
