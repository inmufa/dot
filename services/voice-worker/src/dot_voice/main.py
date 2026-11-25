"""App factory."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from dot_voice.engines import Stt, Tts, load_engines
from dot_voice.errors import install_handlers
from dot_voice.routes import speak, transcribe
from dot_voice.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    *,
    stt: Stt | None = None,
    tts: Tts | None = None,
    load: bool = False,
) -> FastAPI:
    """`load=True` reads the models from disk; tests pass fakes instead."""
    cfg = settings or get_settings()
    problems: dict[str, str] = {}
    if load:
        stt, tts, problems = load_engines(cfg)
    app = FastAPI(title="dot-voice", docs_url=None, redoc_url=None)
    app.state.settings = cfg
    app.state.stt = stt
    app.state.tts = tts
    install_handlers(app)
    app.include_router(transcribe.router)
    app.include_router(speak.router)

    @app.get("/health", operation_id="health", response_model=None)
    async def health() -> JSONResponse:
        ok = app.state.stt is not None or app.state.tts is not None
        body = {
            "status": "ok" if ok else "unavailable",
            "stt": app.state.stt is not None,
            "tts": app.state.tts is not None,
            "problems": problems,
        }
        return JSONResponse(body, status_code=200 if ok else 503)

    return app


def app_factory() -> FastAPI:
    """Production entry: refuses to serve without a token (compose may pass it empty)."""
    cfg = get_settings()
    if not cfg.token:
        msg = "DOT_VOICE_TOKEN is empty: refusing to start an open voice worker"
        raise RuntimeError(msg)
    return create_app(cfg, load=True)
