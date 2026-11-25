"""PCM helpers: parse 16 kHz mono WAV/PCM, chunk at quiet points, encode output."""

import io
import struct
import wave

import numpy as np

from dot_voice.errors import VoiceError


def parse_audio(data: bytes, content_type: str, rate: int) -> np.ndarray:
    """Float32 samples in [-1, 1]. WAV must be 16-bit mono at `rate`; raw PCM is s16le."""
    ctype = content_type.split(";", maxsplit=1)[0].strip().lower()
    if ctype in {"audio/pcm", "audio/l16", "application/octet-stream"}:
        pcm = data
    else:
        pcm = _wav_pcm(data, rate)
    if len(pcm) % 2:
        pcm = pcm[:-1]
    if not pcm:
        raise VoiceError(400, "empty_audio", "no audio samples")
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0


def _wav_pcm(data: bytes, rate: int) -> bytes:
    try:
        with wave.open(io.BytesIO(data)) as w:
            ch, width, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
            if (ch, width, sr) != (1, 2, rate):
                raise VoiceError(
                    415,
                    "bad_audio_format",
                    f"need {rate} Hz mono 16-bit WAV, got {sr} Hz, {ch} ch, {width * 8}-bit",
                )
            return w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise VoiceError(415, "bad_audio_format", "not a readable WAV file") from exc


def split_chunks(x: np.ndarray, rate: int, chunk_s: float) -> list[np.ndarray]:
    """Cut at the quietest 20 ms frame in the last 3 s of each chunk."""
    size = int(chunk_s * rate)
    if len(x) <= size:
        return [x]
    frame, window = int(0.02 * rate), int(3 * rate)
    out, pos = [], 0
    while len(x) - pos > size:
        lo, hi = pos + size - window, pos + size
        seg = x[lo:hi]
        n = len(seg) // frame
        energy = np.square(seg[: n * frame]).reshape(n, frame).sum(axis=1)
        cut = lo + int(energy.argmin()) * frame + frame // 2
        out.append(x[pos:cut])
        pos = cut
    out.append(x[pos:])
    return out


def to_pcm16(samples: np.ndarray) -> bytes:
    return (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def wav_stream_header(rate: int) -> bytes:
    """Mono 16-bit WAV header with unknown length (streamed)."""
    big = 0xFFFFFFFF
    return (
        b"RIFF" + struct.pack("<I", big) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data" + struct.pack("<I", big)
    )  # fmt: skip
