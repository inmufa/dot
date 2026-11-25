import numpy as np
from dot_voice.main import create_app
from fastapi.testclient import TestClient

from tests.conftest import wav_bytes


def test_health_open_and_reports_engines(client):
    client.headers.pop("X-Voice-Token")
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["stt"] is True
    assert r.json()["tts"] is True


def test_health_503_when_nothing_loaded(settings):
    r = TestClient(create_app(settings)).get("/health")
    assert r.status_code == 503


def test_token_required(client):
    client.headers.pop("X-Voice-Token")
    assert client.get("/voices").status_code == 401
    assert client.post("/transcribe", content=wav_bytes(1)).status_code == 401


def test_transcribe_wav(client, stt):
    r = client.post(
        "/transcribe", content=wav_bytes(2), headers={"content-type": "audio/wav"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "chunk1"
    assert body["chunks"] == 1
    assert body["duration_s"] == 2.0


def test_transcribe_raw_pcm(client):
    pcm = np.zeros(16_000, dtype="<i2").tobytes()
    r = client.post("/transcribe", content=pcm, headers={"content-type": "audio/pcm"})
    assert r.status_code == 200


def test_transcribe_chunks_long_audio(client, stt):
    r = client.post("/transcribe", content=wav_bytes(65))
    assert r.json()["chunks"] == 3
    assert r.json()["text"] == "chunk1 chunk2 chunk3"
    assert max(stt.calls) <= 30 * 16_000
    assert sum(stt.calls) == 65 * 16_000


def test_transcribe_rejects_wrong_format(client):
    r = client.post("/transcribe", content=wav_bytes(1, rate=44_100))
    assert r.status_code == 415
    assert r.json()["error"] == "bad_audio_format"
    r = client.post("/transcribe", content=wav_bytes(1, channels=2))
    assert r.status_code == 415
    r = client.post("/transcribe", content=b"not audio")
    assert r.status_code == 415


def test_transcribe_caps(client):
    assert client.post("/transcribe", content=wav_bytes(71)).status_code == 413
    r = client.post("/transcribe", content=b"\0" * 3_000_001)
    assert r.status_code == 413
    assert r.json()["error"] == "audio_too_large"


def test_transcribe_empty_audio(client):
    r = client.post("/transcribe", content=wav_bytes(0))
    assert r.status_code == 400


def test_speak_wav_stream(client, tts):
    r = client.post("/speak", json={"text": "Hello there. How are you today?"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.headers["x-sample-rate"] == "24000"
    assert r.content[:4] == b"RIFF"
    assert len(r.content) == 44 + 2 * 4800
    assert [c[0] for c in tts.calls] == ["Hello there.", "How are you today?"]
    assert r.headers["x-sentences"] == "2"


def test_speak_pcm_and_options(client, tts):
    r = client.post(
        "/speak",
        json={
            "text": "Short one.",
            "format": "pcm",
            "voice": "bm_george",
            "speed": 1.25,
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/L16"
    assert len(r.content) == 4800
    assert tts.calls[0][1:] == ("bm_george", 1.25)


def test_speak_strips_code(client, tts):
    client.post("/speak", json={"text": "Run this:\n```\nrm -rf /\n```\nDone."})
    spoken = " ".join(c[0] for c in tts.calls)
    assert "rm" not in spoken
    assert "Code omitted" in spoken


def test_speak_validation(client):
    assert client.post("/speak", json={"text": "hi", "voice": "x"}).status_code == 422
    assert client.post("/speak", json={"text": "hi", "speed": 5}).status_code == 422
    assert client.post("/speak", json={"text": ""}).status_code == 422
    assert client.post("/speak", json={"text": "```\nx\n```"}).status_code == 200
    assert client.post("/speak", json={"text": "***"}).status_code == 422
    assert client.post("/speak", json={"text": "a" * 12_001}).status_code == 413


def test_voices(client):
    body = client.get("/voices").json()
    ids = [v["id"] for v in body["voices"]]
    assert body["default"] in ids
    assert "bf_emma" in ids
    assert all(i[0] in "ab" for i in ids)


def test_unavailable_engine(settings, stt):
    c = TestClient(create_app(settings, stt=stt))
    c.headers["X-Voice-Token"] = "t0ken"
    r = c.post("/speak", json={"text": "hi"})
    assert r.status_code == 503
    assert r.json()["error"] == "tts_unavailable"
    assert c.post("/transcribe", content=wav_bytes(1)).status_code == 200
