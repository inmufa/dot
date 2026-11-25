"""Error type and handlers producing {"error", "detail"}."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class SandboxError(Exception):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def _body(status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse({"error": code, "detail": detail}, status_code=status)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(SandboxError)
    async def _sandbox(_: Request, exc: SandboxError) -> JSONResponse:
        return _body(exc.status, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ()))
        return _body(422, "validation_error", f"{loc}: {first.get('msg', 'invalid')}")

    @app.exception_handler(OSError)
    async def _os(_: Request, exc: OSError) -> JSONResponse:
        """A filesystem failure is the caller's problem, with the reason spelled out."""
        reason = exc.strerror or exc.__class__.__name__
        where = f" ({exc.filename})" if exc.filename else ""
        status = (
            403
            if isinstance(exc, PermissionError)
            else 404
            if isinstance(exc, FileNotFoundError)
            else 400
        )
        return _body(status, "os_error", f"{reason}{where}")
