"""sherpa-onnx engines behind small interfaces (tests swap in fakes)."""

import threading
from typing import Protocol

import numpy as np

from dot_voice.settings import Settings

# Kokoro v1.0 speaker table (id2speaker in the model metadata), English voices only.
VOICE_NAMES = [
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_heart",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
    "bf_alice",
    "bf_emma",
    "bf_isabella",
    "bf_lily",
    "bm_daniel",
    "bm_fable",
    "bm_george",
    "bm_lewis",
]
VOICES = {name: sid for sid, name in enumerate(VOICE_NAMES)}


class Stt(Protocol):
    def transcribe(self, samples: np.ndarray, rate: int) -> str: ...


class Tts(Protocol):
    sample_rate: int

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray: ...


class ParakeetStt:
    def __init__(self, cfg: Settings) -> None:
        import sherpa_onnx  # noqa: PLC0415

        d = cfg.model_dir / cfg.stt_dir
        self._rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.int8.onnx"),
            joiner=str(d / "joiner.int8.onnx"),
            tokens=str(d / "tokens.txt"),
            model_type="nemo_transducer",
            num_threads=cfg.threads,
        )
        self._lock = threading.Lock()

    def transcribe(self, samples: np.ndarray, rate: int) -> str:
        with self._lock:
            stream = self._rec.create_stream()
            stream.accept_waveform(rate, samples)
            self._rec.decode_stream(stream)
            return stream.result.text.strip()


class KokoroTts:
    def __init__(self, cfg: Settings) -> None:
        import sherpa_onnx  # noqa: PLC0415

        d = cfg.model_dir / cfg.tts_dir
        kokoro = sherpa_onnx.OfflineTtsKokoroModelConfig(
            model=str(d / "model.onnx"),
            voices=str(d / "voices.bin"),
            tokens=str(d / "tokens.txt"),
            data_dir=str(d / "espeak-ng-data"),
            dict_dir=str(d / "dict"),
            lexicon=f"{d}/lexicon-us-en.txt,{d}/lexicon-zh.txt",
        )
        conf = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=kokoro, num_threads=cfg.threads, provider="cpu"
            ),
            max_num_sentences=1,
        )
        self._tts = sherpa_onnx.OfflineTts(conf)
        self.sample_rate = int(self._tts.sample_rate)
        self._lock = threading.Lock()

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        with self._lock:
            audio = self._tts.generate(text, sid=VOICES[voice], speed=speed)
        return np.asarray(audio.samples, dtype=np.float32)


def load_engines(cfg: Settings) -> tuple[Stt | None, Tts | None, dict[str, str]]:
    """Load what the model dir has. A missing or broken model is reported, not fatal."""
    problems: dict[str, str] = {}
    stt: Stt | None = None
    tts: Tts | None = None
    if (cfg.model_dir / cfg.stt_dir / "encoder.int8.onnx").is_file():
        try:
            stt = ParakeetStt(cfg)
        except Exception as exc:  # noqa: BLE001
            problems["stt"] = f"load failed: {type(exc).__name__}"
    else:
        problems["stt"] = "model files not found"
    if (cfg.model_dir / cfg.tts_dir / "model.onnx").is_file():
        try:
            tts = KokoroTts(cfg)
        except Exception as exc:  # noqa: BLE001
            problems["tts"] = f"load failed: {type(exc).__name__}"
    else:
        problems["tts"] = "model files not found"
    return stt, tts, problems
