import logging
from pathlib import Path

import httpx
from fastapi import FastAPI
from httpx import AsyncClient

HEALTH = {"status": "ok", "stt": True, "tts": True, "problems": {}}


class FakeWorker:
    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.down = False
        self.health = HEALTH
        self.fail: tuple[int, str] | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        if self.down:
            msg = "refused"
            raise httpx.ConnectError(msg)
        path = req.url.path
        if path == "/health":
            return httpx.Response(200, json=self.health)
        if self.fail and path in ("/transcribe", "/speak"):
            return httpx.Response(
                self.fail[0], json={"error": self.fail[1], "message": "x"}
            )
        if path == "/transcribe":
            return httpx.Response(200, json={"text": "hello", "duration_s": 1.5})
        if path == "/speak":
            return httpx.Response(
                200,
                content=b"\x00\x01" * 50,
                headers={"content-type": "audio/L16", "x-sample-rate": "24000"},
            )
        return httpx.Response(200, json={"default": "af_heart", "voices": []})


def setup(app: FastAPI) -> FakeWorker:
    fake = FakeWorker()
    voice = app.state.voice
    voice._token = "worker-token"
    voice._client = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    voice._status = None
    return fake


WAV = {"content-type": "audio/wav"}


async def test_status_and_telemetry_flag(app: FastAPI, authed: AsyncClient) -> None:
    fake = setup(app)
    assert (await authed.get("/v1/voice/status")).json() == {
        "available": True,
        "stt": True,
        "tts": True,
    }
    assert (await authed.get("/v1/telemetry")).json()["voice_up"] is True
    fake.down = True
    app.state.voice._status = None
    assert (await authed.get("/v1/telemetry")).json()["voice_up"] is False


async def test_unconfigured_is_off(app: FastAPI, authed: AsyncClient) -> None:
    assert (await authed.get("/v1/voice/status")).json()["available"] is False
    assert (await authed.get("/v1/telemetry")).json()["voice_up"] is False
    r = await authed.post("/v1/voice/transcribe", content=b"x" * 100, headers=WAV)
    assert r.status_code == 503
    assert r.json()[0]["code"] == 4130


async def test_requires_token(app: FastAPI, client: AsyncClient) -> None:
    setup(app)
    assert (await client.get("/v1/voice/status")).status_code == 401
    assert (await client.post("/v1/voice/speak", json={"text": "x"})).status_code == 401


async def test_transcribe_forwards_token_and_audits(
    app: FastAPI, authed: AsyncClient
) -> None:
    fake = setup(app)
    r = await authed.post("/v1/voice/transcribe", content=b"RIFF" * 100, headers=WAV)
    assert r.status_code == 200
    assert r.json() == {"text": "hello", "duration_s": 1.5}
    sent = fake.calls[-1]
    assert sent.headers["x-voice-token"] == "worker-token"
    assert sent.content == b"RIFF" * 100
    audit = (await authed.get("/v1/audit")).json()
    entries = [e for e in audit["items"] if e["tool"] == "Voice.transcribe"]
    assert entries
    assert entries[0]["args"] == {"bytes": 400}
    assert "hello" not in str(audit)


async def test_transcribe_size_and_type_caps(app: FastAPI, authed: AsyncClient) -> None:
    setup(app)
    app.state.settings.voice_max_audio_bytes = 2000
    r = await authed.post("/v1/voice/transcribe", content=b"x" * 2001, headers=WAV)
    assert r.status_code == 413
    assert r.json()[0]["code"] == 4131
    r = await authed.post(
        "/v1/voice/transcribe", content=b"x", headers={"content-type": "text/plain"}
    )
    assert r.status_code == 415
    assert r.json()[0]["code"] == 4133


async def test_worker_errors_map_to_codes(app: FastAPI, authed: AsyncClient) -> None:
    fake = setup(app)
    cases = [("audio_too_long", 4132), ("bad_audio_format", 4133), ("boom", 4135)]
    for key, code in cases:
        fake.fail = (413 if code == 4132 else 500, key)
        r = await authed.post("/v1/voice/transcribe", content=b"x" * 10, headers=WAV)
        assert r.json()[0]["code"] == code
    fake.fail = (422, "unknown_voice")
    r = await authed.post("/v1/voice/speak", json={"text": "hi", "voice": "zz"})
    assert r.json()[0]["code"] == 4136


async def test_error_messages_in_three_languages(
    app: FastAPI, authed: AsyncClient
) -> None:
    setup(app).down = True
    app.state.voice._status = None
    msgs = {}
    for lang in ("en", "ru", "uz"):
        r = await authed.post(
            "/v1/voice/speak", json={"text": "hi"}, headers={"Accept-Language": lang}
        )
        assert r.json()[0]["code"] == 4130
        msgs[lang] = r.json()[0]["messages"][0]
    assert len(set(msgs.values())) == 3


async def test_speak_streams_audio(app: FastAPI, authed: AsyncClient) -> None:
    fake = setup(app)
    r = await authed.post(
        "/v1/voice/speak",
        json={"text": "Hello there.", "speed": 1.2, "voice": "af_heart"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/L16"
    assert r.headers["x-sample-rate"] == "24000"
    assert r.headers["cache-control"] == "no-store"
    assert r.content == b"\x00\x01" * 50
    body = fake.calls[-1].content.decode()
    assert '"speed":1.2' in body.replace(" ", "")
    audit = (await authed.get("/v1/audit")).json()
    spoke = [e for e in audit["items"] if e["tool"] == "Voice.speak"]
    assert spoke[0]["args"] == {"chars": 12, "voice": "af_heart"}


async def test_speak_validation_and_cap(app: FastAPI, authed: AsyncClient) -> None:
    setup(app)
    assert (await authed.post("/v1/voice/speak", json={"text": ""})).status_code == 422
    assert (
        await authed.post("/v1/voice/speak", json={"text": "x", "speed": 9})
    ).status_code == 422
    app.state.settings.voice_max_text_chars = 5
    r = await authed.post("/v1/voice/speak", json={"text": "123456"})
    assert r.json()[0]["code"] == 4134


async def test_rate_limits(app: FastAPI, authed: AsyncClient) -> None:
    setup(app)
    app.state.settings.voice_stt_burst = 2
    codes = [
        (
            await authed.post("/v1/voice/transcribe", content=b"x" * 10, headers=WAV)
        ).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


async def test_voices_passthrough(app: FastAPI, authed: AsyncClient) -> None:
    setup(app)
    assert (await authed.get("/v1/voice/voices")).json()["default"] == "af_heart"


def _files_containing(root: Path, marker: bytes) -> list[Path]:
    return [f for f in root.rglob("*") if f.is_file() and marker in f.read_bytes()]


async def test_audio_is_never_stored_or_logged(
    app: FastAPI, authed: AsyncClient, tmp_path: Path, caplog
) -> None:
    setup(app)
    marker = b"RIFFAUDIO-MARKER-9f3a"
    with caplog.at_level(logging.DEBUG):
        await authed.post(
            "/v1/voice/transcribe", content=marker + b"\0" * 2000, headers=WAV
        )
    assert marker.decode() not in caplog.text
    assert not _files_containing(tmp_path, marker)
