import re
import uuid

from fastapi import HTTPException
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.core.api.envelope import build_envelope
from backend.core.api.language import resolve_language
from backend.core.logging import request_id_var

BODY_TOO_LARGE = 1011

_VALID_RID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIdMiddleware:
    """Pure ASGI: sets request_id in scope state and a contextvar, echoes the header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        supplied = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        rid = supplied if _VALID_RID.match(supplied) else uuid.uuid4().hex[:16]
        scope.setdefault("state", {})["request_id"] = rid
        token = request_id_var.set(rid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = rid
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


_DOC_PATHS = ("/docs", "/openapi.json")


def security_headers(path: str) -> dict[str, str]:
    """Headers for every response; the API serves JSON/SSE only, so CSP is closed."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
    }
    if not path.startswith(_DOC_PATHS):  # dev-only Swagger UI needs scripts
        headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
    if path.startswith("/v1"):
        headers["Cache-Control"] = "no-store"
    return headers


class SecurityHeadersMiddleware:
    """Pure ASGI: adds the security headers without overriding existing ones."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = security_headers(scope["path"])

        async def send_secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in extra.items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_secured)


class BodyLimitMiddleware:
    """Pure ASGI: 413 (code 1011) over `limit` bytes, by Content-Length or by count."""

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.limit:
            lang = resolve_language(
                dict(scope["headers"]).get(b"accept-language", b"").decode("latin-1")
            )
            _, body = build_envelope(BODY_TOO_LARGE, lang, error_type="http_error")
            response = JSONResponse([body], status_code=413)
            await response(scope, receive, send)
            return
        seen = 0

        async def counted() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit:
                    raise HTTPException(status_code=413)
            return message

        await self.app(scope, counted, send)
