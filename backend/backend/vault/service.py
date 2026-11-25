"""Vault storage: encrypted records, metadata-only reads, audit rows without secrets."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.exceptions import DomainException
from backend.core.logging import register_secret
from backend.core.public_id import new_public_id
from backend.governance.services.audit import AuditService
from backend.settings import Settings
from backend.vault import crypto
from backend.vault import origins as org
from backend.vault.crypto import VaultDataError
from backend.vault.models import VaultCredential, meta
from backend.vault.session_store import SessionMixin

logger = logging.getLogger(__name__)
KEY_MISSING, NOT_FOUND, LABEL_TAKEN = 4140, 4141, 4142
DELETE_UNCONFIRMED, LIMIT, BAD_ORIGIN, UNREADABLE = 4143, 4146, 4149, 4147


def _now() -> datetime:
    return datetime.now(UTC)


class Secrets:
    """Decrypted login material. Internal only: repr and str never show values."""

    def __init__(self, password: str, totp_secret: str | None) -> None:
        self.password = password
        self.totp_secret = totp_secret

    def __repr__(self) -> str:
        return "Secrets(***)"

    def values(self) -> list[str | None]:
        return [self.password, self.totp_secret]


class VaultService(SessionMixin):
    def __init__(
        self,
        maker: async_sessionmaker,
        audit: AuditService,
        settings: Settings,
    ) -> None:
        self._maker = maker
        self._audit = audit
        self.cfg = settings
        self.key: bytes | None = None
        try:
            self.key = crypto.parse_key(settings.vault_key)
        except ValueError as exc:
            logger.error("credential vault disabled: %s", exc)  # noqa: TRY400
        else:
            if self.key is None:
                logger.warning("credential vault is off: DOT_VAULT_KEY is not set")
        register_secret(settings.vault_key)

    @property
    def enabled(self) -> bool:
        return self.key is not None

    def _key(self) -> bytes:
        if self.key is None:
            raise DomainException(KEY_MISSING)
        return self.key

    async def record(
        self,
        kind: str,
        label: str,
        origins: list[str],
        outcome: str,
        sid: str = "vault",
    ) -> None:
        """Audit row: label, origins and outcome only."""
        await self._audit.append(
            session=sid,
            mode="-",
            tool=f"vault.{kind}",
            args={"label": label, "origins": origins},
            decision="allow",
            source="owner" if sid == "vault" else "agent",
            reason=outcome,
        )

    def _origins(self, raw: list[str]) -> list[str]:
        try:
            return org.clean_origins(raw, allow_http=self.cfg.vault_allow_http)
        except ValueError as exc:
            raise DomainException(BAD_ORIGIN) from exc

    def _seal_secrets(self, row_id: str, origins: list[str], s: Secrets) -> bytes:
        body = json.dumps({"password": s.password, "totp_secret": s.totp_secret})
        return crypto.seal(
            self._key(), body.encode(), crypto.aad(row_id, "secret", origins)
        )

    async def listing(self) -> list[dict[str, Any]]:
        self._key()
        async with self._maker() as db:
            rows = (
                await db.scalars(
                    select(VaultCredential).order_by(VaultCredential.label)
                )
            ).all()
        return [meta(r) for r in rows]

    async def row(self, ref: str, *, by_label: bool = False) -> VaultCredential:
        col = VaultCredential.label if by_label else VaultCredential.public_id
        async with self._maker() as db:
            row = await db.scalar(select(VaultCredential).where(col == ref))
        if row is None:
            raise DomainException(NOT_FOUND)
        return row

    async def create(
        self,
        *,
        label: str,
        origins: list[str],
        username: str = "",
        password: str | None = None,
        totp_secret: str | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        self._key()
        clean = self._origins(origins)
        pid = new_public_id("V")
        row = VaultCredential(
            public_id=pid,
            label=label,
            origins=clean,
            username=username,
            notes=notes,
            has_totp=bool(totp_secret),
        )
        if password:
            row.secret_blob = self._seal_secrets(
                pid, clean, Secrets(password, totp_secret or None)
            )
        async with self._maker() as db:
            count = await db.scalar(select(func.count()).select_from(VaultCredential))
            if (count or 0) >= self.cfg.vault_max_credentials:
                raise DomainException(LIMIT)
            db.add(row)
            try:
                await db.commit()
            except IntegrityError as exc:
                raise DomainException(LABEL_TAKEN) from exc
        await self.record("create", label, clean, "created")
        return meta(row)

    async def update(self, ref: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Secret fields are write-only: sending one replaces it, omitting keeps it."""
        key = self._key()
        async with self._maker() as db:
            row = await db.scalar(
                select(VaultCredential).where(VaultCredential.public_id == ref)
            )
            if row is None:
                raise DomainException(NOT_FOUND)
            old = list(row.origins)
            new = self._origins(patch["origins"]) if patch.get("origins") else old
            secrets = self._open_secrets(row, old) if row.secret_blob else None
            if patch.get("password"):
                secrets = Secrets(
                    patch["password"], secrets.totp_secret if secrets else None
                )
            if "totp_secret" in patch and secrets:
                secrets.totp_secret = patch["totp_secret"] or None
            for field in ("label", "username", "notes"):
                if patch.get(field) is not None:
                    setattr(row, field, patch[field])
            if new != old:
                row.origins = new
                self._clear_session(row)  # cookies were scoped to the old list
            if secrets:
                row.secret_blob = self._seal_secrets(row.public_id, new, secrets)
                row.has_totp = bool(secrets.totp_secret)
            try:
                await db.commit()
            except IntegrityError as exc:
                raise DomainException(LABEL_TAKEN) from exc
            del key
            out = meta(row)
        await self.record("update", out["label"], out["origins"], "updated")
        return out

    async def delete(self, ref: str, confirm: str | None) -> None:
        self._key()
        row = await self.row(ref)
        if confirm != row.public_id:
            raise DomainException(DELETE_UNCONFIRMED)
        async with self._maker() as db:
            await db.execute(
                VaultCredential.__table__.delete().where(
                    VaultCredential.public_id == ref
                )
            )
            await db.commit()
        await self.record("delete", row.label, list(row.origins), "deleted")

    def _open_secrets(
        self, row: VaultCredential, origins: list[str] | None = None
    ) -> Secrets:
        assert row.secret_blob is not None  # noqa: S101
        try:
            raw = crypto.unseal(
                self._key(),
                row.secret_blob,
                crypto.aad(row.public_id, "secret", origins or list(row.origins)),
            )
            data = json.loads(raw)
        except (VaultDataError, ValueError) as exc:
            raise DomainException(UNREADABLE) from exc
        return Secrets(data["password"], data.get("totp_secret"))

    def secrets(self, row: VaultCredential) -> Secrets | None:
        return self._open_secrets(row) if row.secret_blob else None

    async def logins_for(
        self, url: str, *, with_session: bool = False
    ) -> list[VaultCredential]:
        """Credentials bound to the origin of `url` (optionally only those with a session)."""
        async with self._maker() as db:
            rows = (await db.scalars(select(VaultCredential))).all()
        return [
            r
            for r in rows
            if org.matches(url, list(r.origins))
            and (r.session_blob or not with_session)
        ]

    async def touch(self, ref: str) -> None:
        async with self._maker() as db:
            await db.execute(
                update(VaultCredential)
                .where(VaultCredential.public_id == ref)
                .values(last_used=_now())
            )
            await db.commit()
