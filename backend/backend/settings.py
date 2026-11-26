from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASELINE = (
    Path(__file__).resolve().parents[2] / "deploy/config/dot/default_permissions.json"
)
_GLOBAL_RULES = (
    Path(__file__).resolve().parents[2] / "deploy/config/dot/global_rules.md"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOT_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    api_token: str = Field(min_length=16)  # required, no default
    db_path: Path = Path("data/dot.db")
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    sandbox_url: str = "http://127.0.0.1:8090"
    workspace: Path = Path("workspace")
    # Host mode: same flag the sandbox-runner uses. Auto mode stops gating on the
    # workspace boundary when the sandbox itself has no boundary either.
    unrestricted: bool = Field(
        default=False, validation_alias="DOT_SANDBOX_UNRESTRICTED"
    )
    log_json: bool = True
    sandbox_token: str | None = None
    llm_model: str = "dot"
    # Per slot. Seed only: the backend replaces it with llama-server /props n_ctx.
    llm_context_limit: int = Field(default=32768, ge=512)
    llm_context_cap: int | None = Field(default=None, ge=512)  # optional ceiling
    # Thinking: on | off | auto (auto leaves the chat template default).
    llm_thinking: Literal["on", "off", "auto"] = "on"
    llm_temperature: float = Field(default=0.6, ge=0, le=2)
    llm_top_p: float = Field(default=0.95, gt=0, le=1)
    llm_top_k: int = Field(default=20, ge=0)
    llm_presence_penalty: float = Field(default=0.0, ge=-2, le=2)
    llm_max_tokens: int | None = Field(default=None, ge=1)
    llm_debug_file: Path | None = None  # append every streamed request body (JSONL)
    max_iterations: int = 40
    approval_timeout_s: float = 300.0
    question_timeout_s: float = 300.0
    # Seed for llama-server --parallel (replaced from /props); caps concurrent subagents.
    llm_parallel_slots: int = Field(default=2, ge=1)
    user_settings_path: Path = Field(
        default_factory=lambda: Path.home() / ".dot" / "settings.json"
    )
    default_permissions_path: Path | None = _BASELINE
    skills_dir: Path = Path(__file__).resolve().parents[2] / "skills"  # bundled tier
    user_skills_dir: Path = Path("~/.dot/skills")
    global_rules_path: Path = _GLOBAL_RULES  # bundled tier-1 rules
    user_rules_path: Path = Path("~/.dot/USER_RULES.md")
    preferences_path: Path = Path("~/.dot/preferences.json")  # reply tone and emojis
    memory_dir: Path = Path("~/.dot/memory")
    memory_vectors: bool = False  # vector search needs an Embedder (not shipped yet)
    compact_threshold: float = Field(default=0.75, gt=0.1, le=0.95)
    # Absolute ceiling on the compaction threshold (tokens): big contexts compact earlier.
    compact_max_tokens: int | None = Field(default=None, ge=1024)
    searxng_url: str = "http://dot-searxng:8080"  # dev on host: http://127.0.0.1:8888
    browser_url: str = "http://dot-browser:8091"
    browser_token: str | None = None
    voice_url: str = "http://dot-voice:8092"
    voice_token: str | None = None  # empty: voice counts as off
    voice_stt_rate_per_min: float = Field(default=20.0, gt=0)
    voice_stt_burst: int = Field(default=10, ge=1)
    voice_tts_rate_per_min: float = Field(default=60.0, gt=0)
    voice_tts_burst: int = Field(default=20, ge=1)
    voice_max_audio_bytes: int = Field(default=4_000_000, ge=1024)  # ~2 min of 16 kHz
    voice_max_text_chars: int = Field(default=12_000, ge=1)
    # Master switches (DOT_WEB_SEARCH=off): the tool is not registered at all.
    web_search: bool = True
    web_fetch: bool = True
    web_unsafe_allow_loopback: bool = False  # TEST ONLY: WebFetch may reach 127.0.0.0/8

    # Credential vault (docs/security.md). Without a key the vault stays off.
    vault_key: str | None = Field(default=None, repr=False)  # 64 hex chars
    vault_max_credentials: int = Field(default=200, ge=1)
    vault_login_rate_per_min: float = Field(default=0.5, gt=0)  # per credential
    vault_login_burst: int = Field(default=3, ge=1)
    vault_api_rate_per_min: float = Field(default=60.0, gt=0)
    vault_api_burst: int = Field(default=20, ge=1)
    vault_session_max_age_days: float = Field(default=30.0, gt=0)
    vault_session_refresh_s: float = Field(default=300.0, ge=1)
    vault_allow_http: bool = False  # TEST ONLY: allow http:// origins

    # Public API limits (docs/api-contract.md, Hardening)
    max_message_chars: int = Field(default=100_000, ge=1, le=2_000_000)
    max_body_bytes: int = Field(default=1_048_576, ge=1024, le=64 * 1024 * 1024)
    chat_rate_per_min: float = Field(default=30.0, gt=0)  # chat starts per client
    chat_rate_burst: int = Field(default=10, ge=1)
    # Owner browser view: frame/state polling and input actions, per client
    browser_view_rate_per_min: float = Field(default=600.0, gt=0)
    browser_view_burst: int = Field(default=120, ge=1)
    browser_input_rate_per_min: float = Field(default=180.0, gt=0)
    browser_input_burst: int = Field(default=40, ge=1)
    auto_title: bool = True  # AI chat title after the second user message

    # MCP client (docs/api-contract.md, Phase 5)
    mcp_enabled: bool = True
    mcp_env_allowlist: str = (
        ""  # comma list: env names `${VAR}` in server configs may read
    )
    mcp_call_timeout_s: float = Field(default=60.0, gt=0, le=600)
    mcp_connect_timeout_s: float = Field(default=20.0, gt=0, le=120)
    mcp_ping_interval_s: float = Field(default=30.0, gt=0)
    mcp_reconcile_interval_s: float = Field(default=5.0, gt=0)
    mcp_max_tools_per_server: int = Field(default=50, ge=1, le=500)
    # Scheduler (in-process, SQLite-backed)
    scheduler_enabled: bool = True
    timezone: str = "UTC"  # IANA name; cron expressions are evaluated in it
    schedule_mode: str = "default"  # permission mode of scheduled runs (never bypass)
    schedule_max_jobs: int = Field(default=50, ge=1, le=500)
    schedule_run_timeout_s: float = Field(default=900.0, gt=0)
    schedule_poll_s: float = Field(default=20.0, gt=0)
    schedule_jitter_s: float = Field(default=30.0, ge=0)
    schedule_missed_grace_s: float = Field(default=300.0, gt=0)
    retention_checkpoint_days: float = Field(default=14.0, gt=0)
    retention_checkpoint_max_bytes: int = Field(default=50_000_000, ge=0)
    retention_outputs_days: float = Field(default=7.0, gt=0)

    # UI features (docs/api-contract.md "UI features v2")
    upload_max_files: int = Field(default=5, ge=1, le=20)
    upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    preview_max_bytes: int = Field(default=2 * 1024 * 1024, ge=1024)
    research_default_s: int = Field(default=180, ge=30)
    research_max_s: int = Field(default=1800, ge=30)
    research_fetch_cap: int = Field(default=12, ge=1, le=100)
    models_dir: Path = Path("/models")  # mounted read-only; lists *.gguf
    vram_sysfs: Path | None = None  # e.g. /sys/class/drm/card2/device (read-only)
    llm_registry_path: Path | None = None  # default: <models_dir>/registry.toml
    # Vision: full image data only for the last N images in replay, older ones stubbed.
    vision_keep_images: int = Field(default=2, ge=0, le=16)
    vision_max_side: int = Field(default=768, ge=64, le=4096)  # photos
    vision_max_side_text: int = Field(
        default=1024, ge=64, le=4096
    )  # PNG: screenshots, docs

    @field_validator(
        "llm_debug_file",
        "llm_max_tokens",
        "llm_context_cap",
        "compact_max_tokens",
        "llm_registry_path",
        "vram_sysfs",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, v: object) -> object:
        return None if v == "" else v

    @field_validator("api_token")
    @classmethod
    def _not_placeholder(cls, v: str) -> str:
        if v.lower().startswith("change-me"):
            msg = "DOT_API_TOKEN is still the .env.example placeholder"
            raise ValueError(msg)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
