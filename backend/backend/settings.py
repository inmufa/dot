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
    log_json: bool = True
    sandbox_token: str | None = None
    llm_model: str = "dot"
    llm_context_limit: int = 32768  # per slot: compose -c 65536 / --parallel 2
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
    llm_parallel_slots: int = 2  # llama-server --parallel; caps concurrent subagents
    user_settings_path: Path = Field(
        default_factory=lambda: Path.home() / ".dot" / "settings.json"
    )
    default_permissions_path: Path | None = _BASELINE
    skills_dir: Path = Path(__file__).resolve().parents[2] / "skills"  # bundled tier
    user_skills_dir: Path = Path("~/.dot/skills")
    global_rules_path: Path = _GLOBAL_RULES  # bundled tier-1 rules
    user_rules_path: Path = Path("~/.dot/USER_RULES.md")
    memory_dir: Path = Path("~/.dot/memory")
    memory_vectors: bool = False  # vector search needs an Embedder (not shipped yet)
    compact_threshold: float = Field(default=0.75, gt=0.1, le=0.95)
    searxng_url: str = "http://dot-searxng:8080"  # dev on host: http://127.0.0.1:8888
    browser_url: str = "http://dot-browser:8091"
    browser_token: str | None = None
    web_unsafe_allow_loopback: bool = False  # TEST ONLY: WebFetch may reach 127.0.0.0/8

    # Public API limits (docs/api-contract.md, Hardening)
    max_message_chars: int = Field(default=100_000, ge=1, le=2_000_000)
    max_body_bytes: int = Field(default=1_048_576, ge=1024, le=64 * 1024 * 1024)
    chat_rate_per_min: float = Field(default=30.0, gt=0)  # chat starts per client
    chat_rate_burst: int = Field(default=10, ge=1)

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

    @field_validator("llm_debug_file", "llm_max_tokens", mode="before")
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
