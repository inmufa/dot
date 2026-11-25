"""Worker errors: JSON body {error, message}."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class VoiceError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(VoiceError)
    async def _voice_error(_: Request, exc: VoiceError) -> JSONResponse:
        return JSONResponse(
            {"error": exc.code, "message": exc.message}, status_code=exc.status
        )
