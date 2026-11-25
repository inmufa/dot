"""Shared dependencies: settings, auth, engines."""

import hmac
from typing import Annotated

from fastapi import Depends, Header, Request

from dot_voice.engines import Stt, Tts
from dot_voice.errors import VoiceError
from dot_voice.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_token(
    settings: SettingsDep,
    x_voice_token: Annotated[str | None, Header()] = None,
) -> None:
    if settings.token and not hmac.compare_digest(
        (x_voice_token or "").encode(), settings.token.encode()
    ):
        raise VoiceError(401, "unauthorized", "bad or missing X-Voice-Token")


def get_stt(request: Request) -> Stt:
    stt = request.app.state.stt
    if stt is None:
        raise VoiceError(503, "stt_unavailable", "speech-to-text model not loaded")
    return stt


def get_tts(request: Request) -> Tts:
    tts = request.app.state.tts
    if tts is None:
        raise VoiceError(503, "tts_unavailable", "text-to-speech model not loaded")
    return tts


SttDep = Annotated[Stt, Depends(get_stt)]
TtsDep = Annotated[Tts, Depends(get_tts)]
