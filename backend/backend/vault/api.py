"""Owner API for the credential vault. Secret fields are write-only: nothing reads them back."""

import base64
import binascii
import math
from datetime import datetime
from typing import Annotated, Any

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from backend.core.api.auth import protected_router
from backend.core.api.ratelimit import RATE_LIMITED, TokenBucket
from backend.core.exceptions import DomainException
from backend.sessions.services.session_service import SessionService
from backend.vault.agent import VaultAgent
from backend.vault.service import DELETE_UNCONFIRMED, KEY_MISSING

router = protected_router(prefix="/v1/vault", tags=["vault"])
Label = Annotated[str, Field(min_length=1, max_length=80)]
Origins = Annotated[list[str], Field(min_length=1, max_length=10)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _totp_ok(v: SecretStr | None) -> SecretStr | None:
    if v is not None and v.get_secret_value():
        raw = "".join(v.get_secret_value().split()).upper().rstrip("=")
        try:
            base64.b32decode(raw + "=" * (-len(raw) % 8))
        except (binascii.Error, ValueError) as exc:
            msg = "not a base32 secret"
            raise ValueError(msg) from exc
    return v


class CredentialIn(_In):
    label: Label
    origins: Origins
    username: str = Field(default="", max_length=500)
    password: SecretStr | None = Field(default=None, max_length=1000)
    totp_secret: SecretStr | None = Field(default=None, max_length=200)
    notes: str = Field(default="", max_length=1000)

    _v = field_validator("totp_secret")(_totp_ok)


class CredentialPatch(_In):
    label: Label | None = None
    origins: Origins | None = None
    username: str | None = Field(default=None, max_length=500)
    password: SecretStr | None = Field(default=None, max_length=1000)
    totp_secret: SecretStr | None = Field(default=None, max_length=200)  # "" removes it
    notes: str | None = Field(default=None, max_length=1000)

    _v = field_validator("totp_secret")(_totp_ok)


class CredentialOut(BaseModel):
    id: str
    label: str
    origins: list[str]
    username: str
    notes: str
    has_password: bool
    has_totp: bool
    has_session: bool
    session_saved_at: datetime | None
    session_expires_at: datetime | None
    last_used: datetime | None
    created_at: datetime
    updated_at: datetime


class SaveSessionIn(_In):
    session_id: str = Field(min_length=1, max_length=16)
    credential: str | None = Field(default=None, max_length=16)
    label: Label | None = None


def _agent(request: Request) -> VaultAgent:
    return request.app.state.vault


def _limit(request: Request) -> VaultAgent:
    agent = _agent(request)
    cfg = request.app.state.settings
    bucket = getattr(request.app.state, "vault_bucket", None)
    if bucket is None:
        bucket = request.app.state.vault_bucket = TokenBucket(
            cfg.vault_api_rate_per_min, cfg.vault_api_burst
        )
    wait = bucket.take(request.client.host if request.client else "-")
    if wait:
        raise DomainException(RATE_LIMITED, retry_after=max(1, math.ceil(wait)))
    return agent


@router.get("/status")
async def status(request: Request) -> dict[str, bool]:
    return {"enabled": _agent(request).svc.enabled}


@router.get("")
async def list_credentials(request: Request) -> list[CredentialOut]:
    return [CredentialOut(**m) for m in await _agent(request).svc.listing()]


@router.post("", status_code=201)
async def create(request: Request, body: CredentialIn) -> CredentialOut:
    svc = _limit(request).svc
    made = await svc.create(
        label=body.label.strip(),
        origins=body.origins,
        username=body.username,
        password=body.password.get_secret_value() if body.password else None,
        totp_secret=body.totp_secret.get_secret_value() if body.totp_secret else None,
        notes=body.notes,
    )
    return CredentialOut(**made)


@router.delete("/sessions")
async def clear_all_sessions(
    request: Request, confirm: str | None = None
) -> dict[str, int]:
    agent = _limit(request)
    if not agent.svc.enabled:
        raise DomainException(KEY_MISSING)
    if confirm != "all":
        raise DomainException(DELETE_UNCONFIRMED)
    agent.live.clear()
    return {"cleared": await agent.svc.clear_session(None)}


@router.post("/save-session")
async def save_session(request: Request, body: SaveSessionIn) -> CredentialOut:
    agent = _limit(request)
    if not agent.svc.enabled:
        raise DomainException(KEY_MISSING)
    await SessionService(request.app.state.sessions).get(body.session_id)
    meta = await agent.save_current(body.session_id, body.credential, body.label)
    return CredentialOut(**meta)


@router.patch("/{credential_id}")
async def update(
    request: Request, credential_id: str, body: CredentialPatch
) -> CredentialOut:
    patch: dict[str, Any] = body.model_dump(
        exclude_unset=True, exclude={"password", "totp_secret"}
    )
    if body.password is not None:
        patch["password"] = body.password.get_secret_value()
    if body.totp_secret is not None:
        patch["totp_secret"] = body.totp_secret.get_secret_value()
    agent = _limit(request)
    out = await agent.svc.update(credential_id, patch)
    return CredentialOut(**out)


@router.delete("/{credential_id}/session")
async def clear_session(request: Request, credential_id: str) -> dict[str, bool]:
    agent = _limit(request)
    if not agent.svc.enabled:
        raise DomainException(KEY_MISSING)
    await agent.svc.row(credential_id)
    for creds in agent.live.values():
        creds.discard(credential_id)
    await agent.svc.clear_session(credential_id)
    return {"ok": True}


@router.delete("/{credential_id}")
async def delete(
    request: Request, credential_id: str, confirm: str | None = None
) -> dict[str, bool]:
    agent = _limit(request)
    await agent.svc.delete(credential_id, confirm)
    for creds in agent.live.values():
        creds.discard(credential_id)
    return {"ok": True}
