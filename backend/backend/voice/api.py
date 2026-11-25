"""Voice proxy: /v1/voice/{status,transcribe,speak,voices}. Audio is never stored."""

import re
from typing import Annotated, Any, Literal

from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from backend.core.api.auth import protected_router
from backend.core.api.ratelimit import RATE_LIMITED, TokenBucket
from backend.core.exceptions import DomainException
from backend.voice.client import (
    AUDIO_TOO_LARGE,
    BAD_AUDIO,
    BAD_TEXT,
    VOICE_UNAVAILABLE,
    VoiceClient,
)

router = protected_router(prefix="/v1/voice", tags=["voice"])
_AUDIO_TYPES = re.compile(r"audio/(wav|x-wav|wave|pcm|l16)", re.IGNORECASE)


class SpeakIn(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = Field(default=None, max_length=32)
    speed: Annotated[float, Field(ge=0.5, le=2.0)] = 1.0
    format: Literal["wav", "pcm"] = "pcm"


def _client(request: Request) -> VoiceClient:
    return request.app.state.voice


def _limit(request: Request, kind: str) -> None:
    cfg = request.app.state.settings
    buckets = request.app.state.voice_buckets
    if kind not in buckets:
        rate, burst = (
            (cfg.voice_stt_rate_per_min, cfg.voice_stt_burst)
            if kind == "stt"
            else (cfg.voice_tts_rate_per_min, cfg.voice_tts_burst)
        )
        buckets[kind] = TokenBucket(rate, burst)
    wait = buckets[kind].take(request.client.host if request.client else "-")
    if wait:
        raise DomainException(RATE_LIMITED, retry_after=max(1, int(wait) + 1))


async def _audit(request: Request, tool: str, args: dict[str, Any]) -> None:
    # Sizes only: no audio, no transcript, no spoken text.
    await request.app.state.audit.append(
        session="-", mode="-", tool=tool, args=args, decision="allow", source="user"
    )


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    return await _client(request).status()


@router.get("/voices")
async def voices(request: Request) -> dict[str, Any]:
    return await _client(request).get_json("/voices")


@router.post("/transcribe")
async def transcribe(request: Request) -> dict[str, Any]:
    cap = request.app.state.settings.voice_max_audio_bytes
    ctype = request.headers.get("content-type", "")
    if not _AUDIO_TYPES.match(ctype):
        raise DomainException(BAD_AUDIO)
    _limit(request, "stt")
    buf = bytearray()
    async for part in request.stream():
        buf += part
        if len(buf) > cap:
            raise DomainException(AUDIO_TOO_LARGE)
    if not buf:
        raise DomainException(BAD_AUDIO)
    if not (await _client(request).status())["stt"]:
        raise DomainException(VOICE_UNAVAILABLE)
    out = await _client(request).transcribe(bytes(buf), ctype)
    await _audit(request, "Voice.transcribe", {"bytes": len(buf)})
    return {"text": out.get("text", ""), "duration_s": out.get("duration_s")}


@router.post("/speak")
async def speak(request: Request, body: SpeakIn) -> StreamingResponse:
    if len(body.text) > request.app.state.settings.voice_max_text_chars:
        raise DomainException(BAD_TEXT)
    _limit(request, "tts")
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    upstream = await _client(request).speak(payload)
    await _audit(request, "Voice.speak", {"chars": len(body.text), "voice": body.voice})
    headers = {"Cache-Control": "no-store"}
    for name in ("X-Sample-Rate", "X-Sentences"):
        if name in upstream.headers:
            headers[name] = upstream.headers[name]
    return StreamingResponse(
        upstream.aiter_bytes(),
        media_type=upstream.headers.get("content-type", "audio/L16"),
        headers=headers,
        background=BackgroundTask(upstream.aclose),
    )
