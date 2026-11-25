"""Runner settings, env-driven."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(populate_by_name=True, extra="ignore")

    workspace: Path = Field(
        default=Path("/workspace"), validation_alias="DOT_WORKSPACE"
    )
    token: str | None = Field(default=None, validation_alias="DOT_SANDBOX_TOKEN")
    # Host mode: any path on the machine is reachable; the workspace is only the default cwd.
    unrestricted: bool = Field(
        default=False, validation_alias="DOT_SANDBOX_UNRESTRICTED"
    )
    max_read_bytes: int = 20_000_000
    max_upload_bytes: int = 20_971_520
    max_background_jobs: int = 32
    max_mcp_servers: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
