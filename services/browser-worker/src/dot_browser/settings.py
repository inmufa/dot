"""Worker settings, env-driven (DOT_BROWSER_*)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOT_BROWSER_", extra="ignore")

    token: str | None = None
    # Persistent per-session profiles live under this dir; None = ephemeral contexts.
    profiles_dir: Path | None = None
    headless: bool = True
    # Chromium's own sandbox needs user namespaces; the container is the jail instead.
    no_sandbox: bool = False
    extra_chromium_args: list[str] = []

    max_contexts: int = 4
    max_tabs: int = 8
    idle_minutes: float = 10.0
    reap_interval_s: float = 30.0
    viewport_width: int = 1280
    viewport_height: int = 800

    nav_timeout_ms: int = 20_000
    action_timeout_ms: int = 8_000
    max_redirects: int = 10
    block_resources: bool = False

    # Comma-separated host suffixes. Allowlist empty = any public host.
    allow_hosts: str = ""
    deny_hosts: str = ""
    # TEST ONLY: lets loopback through so a local fixture server works. Never set in deployments.
    unsafe_allow_loopback: bool = False
    dns_pin_seconds: float = 60.0

    max_elements: int = 250
    max_name_chars: int = 120
    max_text_chars: int = 6_000
    max_extract_chars: int = 20_000
    max_html_bytes: int = 3_000_000
    max_response_bytes: int = 25_000_000
    proxy_timeout_s: float = 120.0
    proxy_connect_s: float = 10.0
    max_screenshot_bytes: int = 1_500_000
    max_full_page_px: int = 4_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
