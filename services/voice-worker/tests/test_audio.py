import numpy as np
from dot_voice.audio import split_chunks, to_pcm16, wav_stream_header


def test_split_prefers_quiet_point():
    rate = 16_000
    x = np.ones(int(50 * rate), dtype=np.float32) * 0.5
    x[int(28.2 * rate) : int(28.3 * rate)] = 0.0
    parts = split_chunks(x, rate, 30.0)
    assert len(parts) == 2
    assert abs(len(parts[0]) / rate - 28.25) < 0.05
    assert sum(len(p) for p in parts) == len(x)


def test_short_audio_single_chunk():
    x = np.zeros(1000, dtype=np.float32)
    assert len(split_chunks(x, 16_000, 30.0)) == 1


def test_pcm_and_header():
    assert to_pcm16(np.array([0.0, 1.0, -2.0], dtype=np.float32)) == (
        b"\x00\x00\xff\x7f\x01\x80"
    )
    assert len(wav_stream_header(24_000)) == 44
