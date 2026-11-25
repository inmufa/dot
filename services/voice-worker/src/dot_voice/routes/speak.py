"""POST /speak (streamed audio, one sentence at a time), GET /voices."""

from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dot_voice.audio import to_pcm16, wav_stream_header
from dot_voice.deps import SettingsDep, TtsDep, require_token
from dot_voice.engines import VOICES, Tts
from dot_voice.errors import VoiceError
from dot_voice.textprep import clean_for_speech, split_sentences

router = APIRouter(dependencies=[Depends(require_token)])


class SpeakIn(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = None
    speed: Annotated[float, Field(ge=0.5, le=2.0)] = 1.0
    format: Literal["wav", "pcm"] = "wav"
    # False: the caller already cleaned the text
    clean: bool = True


async def _audio(
    tts: Tts, sentences: list[str], voice: str, speed: float, *, wav: bool
) -> AsyncIterator[bytes]:
    if wav:
        yield wav_stream_header(tts.sample_rate)
    for sentence in sentences:
        samples = await run_in_threadpool(tts.synth, sentence, voice, speed)
        yield to_pcm16(samples)


@router.post("/speak", operation_id="speak")
async def speak(body: SpeakIn, settings: SettingsDep, tts: TtsDep) -> StreamingResponse:
    if len(body.text) > settings.max_text_chars:
        raise VoiceError(
            413, "text_too_long", f"text over {settings.max_text_chars} chars"
        )
    voice = body.voice or settings.default_voice
    if voice not in VOICES:
        raise VoiceError(422, "unknown_voice", f"unknown voice {voice!r}")
    text = clean_for_speech(body.text) if body.clean else body.text
    sentences = split_sentences(text)
    if not sentences:
        raise VoiceError(422, "nothing_to_speak", "no speakable text")
    wav = body.format == "wav"
    return StreamingResponse(
        _audio(tts, sentences, voice, body.speed, wav=wav),
        media_type="audio/wav" if wav else "audio/L16",
        headers={
            "X-Sample-Rate": str(tts.sample_rate),
            "X-Sentences": str(len(sentences)),
            "Cache-Control": "no-store",
        },
    )


@router.get("/voices", operation_id="voices")
async def voices(settings: SettingsDep, tts: TtsDep) -> dict[str, object]:
    return {
        "default": settings.default_voice,
        "sample_rate": tts.sample_rate,
        "voices": [
            {"id": name, "accent": "US" if name[0] == "a" else "UK",
             "gender": "female" if name[1] == "f" else "male"}
            for name in VOICES
        ],
    }  # fmt: skip
