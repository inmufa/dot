import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core.api.envelope import UNKNOWN_CODE, build_envelope
from backend.core.api.language import resolve_language
from backend.core.exceptions import DomainException
from backend.core.middleware import security_headers

logger = logging.getLogger(__name__)

# HTTP status raised by Starlette/FastAPI -> catalog code
_HTTP_CODES = {
    400: 1007,
    401: 1001,
    403: 1005,
    404: 1002,
    405: 1006,
    413: 1011,
    429: 1004,
    503: 1008,
}
_BAD_REQUEST = 1007


def request_id_of(request: Request) -> str:
    return request.scope.get("state", {}).get("request_id", "-")


def _respond(
    request: Request,
    entries: list[tuple[int, str | None, str]],
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """entries: (code, key, error_type). The first entry sets the HTTP status."""
    lang = resolve_language(request.headers.get("accept-language"))
    built = [
        build_envelope(code, lang, key=key, error_type=kind)
        for code, key, kind in entries
    ]
    status = built[0][0]
    out: dict[str, str] = dict(headers or {})
    if status == HTTPStatus.UNAUTHORIZED:
        out.setdefault("WWW-Authenticate", "Bearer")
    if status in (HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.SERVICE_UNAVAILABLE):
        out.setdefault("Retry-After", "5")
    for name, value in security_headers(request.url.path).items():
        out.setdefault(name, value)
    rid = request_id_of(request)
    if rid != "-":
        out["X-Request-ID"] = rid
    return JSONResponse([b for _, b in built], status_code=status, headers=out)


def _field_key(loc: tuple[Any, ...]) -> str | None:
    parts = [str(p) for p in loc[1:]]  # drop "body"/"query"/"path"
    return ".".join(parts) or None


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainException)
    async def _domain(request: Request, exc: DomainException) -> JSONResponse:
        headers = None
        if exc.retry_after is not None:
            headers = {"Retry-After": str(exc.retry_after)}
        return _respond(request, [(exc.code, None, "domain_error")], headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        entries = [
            (1003, _field_key(tuple(err["loc"])), "validation_error")
            for err in exc.errors()
        ] or [(1003, None, "validation_error")]
        return _respond(request, entries)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code)
        if code is None:
            client_error = exc.status_code < HTTPStatus.INTERNAL_SERVER_ERROR
            code = _BAD_REQUEST if client_error else UNKNOWN_CODE
        return _respond(request, [(code, None, "http_error")], headers=exc.headers)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Never leak str(exc) to the client; the log keeps the traceback.
        logger.error(
            "unhandled error",
            exc_info=exc,
            extra={"request_id": request_id_of(request)},
        )
        return _respond(request, [(UNKNOWN_CODE, None, "server_error")])
