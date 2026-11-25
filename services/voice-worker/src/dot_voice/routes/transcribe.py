"""POST /transcribe: 16 kHz mono WAV or raw s16le PCM in, text out."""

import time

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from dot_voice.audio import parse_audio, split_chunks
from dot_voice.deps import SettingsDep, SttDep, require_token
from dot_voice.errors import VoiceError

router = APIRouter(dependencies=[Depends(require_token)])


async def _read_capped(request: Request, cap: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > cap:
        raise VoiceError(413, "audio_too_large", f"audio over {cap} bytes")
    buf = bytearray()
    async for part in request.stream():
        buf += part
        if len(buf) > cap:
            raise VoiceError(413, "audio_too_large", f"audio over {cap} bytes")
    return bytes(buf)


@router.post("/transcribe", operation_id="transcribe")
async def transcribe(
    request: Request, settings: SettingsDep, stt: SttDep
) -> dict[str, object]:
    data = await _read_capped(request, settings.max_body_bytes)
    samples = parse_audio(
        data, request.headers.get("content-type", ""), settings.sample_rate
    )
    duration = len(samples) / settings.sample_rate
    if duration > settings.max_audio_s:
        raise VoiceError(
            413, "audio_too_long", f"audio over {settings.max_audio_s:g} s"
        )
    chunks = split_chunks(samples, settings.sample_rate, settings.chunk_s)
    t0 = time.perf_counter()
    texts = [
        await run_in_threadpool(stt.transcribe, c, settings.sample_rate) for c in chunks
    ]
    return {
        "text": " ".join(t for t in texts if t),
        "duration_s": round(duration, 2),
        "chunks": len(chunks),
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }
