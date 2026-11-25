"""Vault request bodies. Secret fields are SecretStr so they never print."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginBody(_Strict):
    origins: list[str] = Field(min_length=1, max_length=20)
    username: str = Field(max_length=500)
    password: SecretStr = Field(max_length=2_000)
    totp_secret: SecretStr | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=4096)
    tab: str | None = None


class ExportBody(_Strict):
    origins: list[str] = Field(min_length=1, max_length=20)


class RestoredBody(_Strict):
    ids: list[str] = Field(max_length=50)


class RestoreBody(_Strict):
    id: str = Field(min_length=1, max_length=32)
    origins: list[str] = Field(min_length=1, max_length=20)
    state: dict[str, Any] = Field(repr=False)
    url: str | None = Field(default=None, max_length=4096)
