"""Worker settings, env-driven (DOT_VOICE_*)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOT_VOICE_", extra="ignore")

    token: str | None = None
    model_dir: Path = Path("/models/voice")
    threads: int = 4
    stt_dir: str = "parakeet-tdt-0.6b-v2-int8"
    tts_dir: str = "kokoro-multi-lang-v1_0"

    sample_rate: int = 16_000
    # Parakeet peak RAM grows with clip length: decode in chunks of this size.
    chunk_s: float = 30.0
    max_audio_s: float = 120.0
    max_body_bytes: int = 4_000_000
    max_text_chars: int = 12_000
    default_voice: str = "af_heart"


@lru_cache
def get_settings() -> Settings:
    return Settings()
