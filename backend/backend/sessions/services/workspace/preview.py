"""Locked-down preview responses for workspace files.

Rendered HTML runs scripts in an opaque origin with no network at all: the sandbox
never gets allow-same-origin, and the CSP leaves only inline script/style and
data:/blob: images. The bundled chart library and a console/error reporter are
inlined here, so the page never has to fetch anything.
"""

import re
from functools import cache
from pathlib import Path

from fastapi import Response

IMAGES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}
_LOCKED = "default-src 'none'; sandbox"
_RENDER = (
    "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; "
    "connect-src 'none'; frame-src 'none'; frame-ancestors 'self'; form-action 'none'; "
    "base-uri 'none'"
)
_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_CHART_TAG = re.compile(
    r"""<script\b[^>]*\bsrc\s*=\s*["']?(?:\./)?dot-chart\.js["']?[^>]*>\s*</script>""",
    re.IGNORECASE,
)
_HEAD = re.compile(r"<head\b[^>]*>", re.IGNORECASE)


@cache
def _asset(name: str) -> str:
    return (
        (_ASSETS / name).read_text(encoding="utf-8").replace("</script", "<\\/script")
    )


def prepare_html(data: bytes) -> bytes:
    """Inline `<script src="dot-chart.js">` and prepend the console/error reporter."""
    text = data.decode("utf-8", errors="replace")
    text = _CHART_TAG.sub(lambda _: f"<script>{_asset('chart.umd.js')}</script>", text)
    runtime = f"<script>{_asset('artifact_runtime.js')}</script>"
    head = _HEAD.search(text)
    if head:
        text = text[: head.end()] + runtime + text[head.end() :]
    else:
        text = runtime + text
    return text.encode("utf-8")


_RENDERABLE = {"html": "text/html", "htm": "text/html", "svg": "image/svg+xml"}


def _is_text(data: bytes) -> bool:
    if b"\x00" in data[:8192]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return exc.start >= len(data) - 4
    return True


def preview_response(data: bytes, path: str, *, render: bool) -> Response:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    base = {"X-Content-Type-Options": "nosniff"}
    if render and ext in _RENDERABLE:
        headers = {
            **base,
            "Content-Security-Policy": _RENDER,
            "X-Frame-Options": "SAMEORIGIN",
        }
        if ext in ("html", "htm"):
            data = prepare_html(data)
        return Response(data, media_type=_RENDERABLE[ext], headers=headers)
    headers = {**base, "Content-Security-Policy": _LOCKED}
    if ext in IMAGES:
        return Response(data, media_type=IMAGES[ext], headers=headers)
    if ext == "pdf":
        return Response(data, media_type="application/pdf", headers=headers)
    if _is_text(data):
        return Response(data, media_type="text/plain; charset=utf-8", headers=headers)
    headers["Content-Disposition"] = "attachment"
    return Response(data, media_type="application/octet-stream", headers=headers)
