import io
import wave

import numpy as np
import pytest
from dot_voice.main import create_app
from dot_voice.settings import Settings
from fastapi.testclient import TestClient

TOKEN = "t0ken"


class FakeStt:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def transcribe(self, samples: np.ndarray, rate: int) -> str:
        self.calls.append(len(samples))
        return f"chunk{len(self.calls)}"


class FakeTts:
    sample_rate = 24_000

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        self.calls.append((text, voice, speed))
        return np.zeros(2400, dtype=np.float32)


def wav_bytes(seconds: float, rate: int = 16_000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x01" * int(seconds * rate) * channels)
    return buf.getvalue()


@pytest.fixture
def stt() -> FakeStt:
    return FakeStt()


@pytest.fixture
def tts() -> FakeTts:
    return FakeTts()


@pytest.fixture
def settings() -> Settings:
    return Settings(token=TOKEN, max_audio_s=70, max_body_bytes=3_000_000)


@pytest.fixture
def client(settings, stt, tts) -> TestClient:
    c = TestClient(create_app(settings, stt=stt, tts=tts))
    c.headers["X-Voice-Token"] = TOKEN
    return c
