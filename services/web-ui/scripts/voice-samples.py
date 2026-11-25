"""Pre-record one short Kokoro clip per voice for the Settings voice list.

Uses the voice worker's own engine and model dir, so clips match what Read aloud sounds like.
Run from services/web-ui:
  uv run --project ../voice-worker --with soundfile python scripts/voice-samples.py
Writes public/voice-samples/<voice>.ogg (Opus) and manifest.json.
"""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from dot_voice.engines import VOICE_NAMES, KokoroTts
from dot_voice.settings import Settings

TEXT = "Hi, I'm Dot. This is how I sound when I read aloud."
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "voice-samples"
MODELS = ROOT.parents[1] / "models" / "voice"


def trim(a: np.ndarray, rate: int) -> np.ndarray:
    """Drop leading/trailing silence, keep 80 ms of air, fade the ends."""
    loud = np.flatnonzero(np.abs(a) > 0.01)
    if loud.size:
        pad = int(rate * 0.08)
        a = a[max(0, loud[0] - pad) : loud[-1] + pad]
    f = min(len(a) // 2, int(rate * 0.01))
    if f:
        ramp = np.linspace(0, 1, f, dtype=np.float32)
        a[:f] *= ramp
        a[-f:] *= ramp[::-1]
    return a


def main() -> None:
    tts = KokoroTts(Settings(model_dir=MODELS, threads=4))
    OUT.mkdir(parents=True, exist_ok=True)
    rate = tts.sample_rate
    items = []
    for v in VOICE_NAMES:
        a = trim(tts.synth(TEXT, v, 1.0), rate)
        a = (
            a / max(1e-6, float(np.abs(a).max())) * 0.89
        )  # same loudness ceiling for every voice
        f = OUT / f"{v}.ogg"
        sf.write(f, a, rate, format="OGG", subtype="OPUS", compression_level=0.8)
        items.append({"id": v, "file": f.name, "duration_s": round(len(a) / rate, 2)})
        print(
            f"{v}: {len(a) / rate:.2f}s {f.stat().st_size // 1024} KB", file=sys.stderr
        )
    manifest = {"text": TEXT, "format": "audio/ogg; codecs=opus", "voices": items}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")


if __name__ == "__main__":
    main()
