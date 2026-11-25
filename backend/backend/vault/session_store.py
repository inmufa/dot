"""Saved browser sessions (cookies + localStorage), sealed per credential."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update

from backend.core.exceptions import DomainException
from backend.vault import crypto, sessionstate
from backend.vault.crypto import VaultDataError
from backend.vault.models import VaultCredential, meta

UNREADABLE = 4147


def _now() -> datetime:
    return datetime.now(UTC)


class SessionMixin:
    """Mixed into VaultService, which provides _maker, cfg, _key, row and record."""

    @staticmethod
    def _clear_session(row: VaultCredential) -> None:
        row.session_blob = row.session_saved_at = row.session_expires_at = None

    async def save_session(
        self, ref: str, raw_state: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Seal a worker export. Returns metadata, or None when nothing usable remained."""
        key = self._key()
        row = await self.row(ref)
        state, latest = sessionstate.tidy(
            raw_state, list(row.origins), self.cfg.vault_session_max_age_days
        )
        if latest is None:
            return None
        blob = crypto.seal(
            key,
            json.dumps(state).encode(),
            crypto.aad(row.public_id, "session", list(row.origins)),
        )
        async with self._maker() as db:
            await db.execute(
                update(VaultCredential)
                .where(VaultCredential.public_id == ref)
                .values(
                    session_blob=blob,
                    session_saved_at=_now(),
                    session_expires_at=datetime.fromtimestamp(latest, UTC),
                )
            )
            await db.commit()
        await self.record("session_save", row.label, list(row.origins), "saved")
        return meta(await self.row(ref))

    async def load_session(self, row: VaultCredential) -> dict[str, Any] | None:
        """Decrypted state, or None when absent or expired (an expired one is dropped)."""
        if row.session_blob is None:
            return None
        expires = sessionstate.aware(row.session_expires_at)
        if expires is None or expires <= _now():
            await self.clear_session(row.public_id)
            return None
        try:
            raw = crypto.unseal(
                self._key(),
                row.session_blob,
                crypto.aad(row.public_id, "session", list(row.origins)),
            )
            state = json.loads(raw)
        except (VaultDataError, ValueError) as exc:
            raise DomainException(UNREADABLE) from exc
        state, latest = sessionstate.tidy(
            state, list(row.origins), self.cfg.vault_session_max_age_days
        )
        return state if latest else None

    async def clear_session(self, ref: str | None = None) -> int:
        """Clear one saved session, or all when ref is None. Returns rows cleared."""
        async with self._maker() as db:
            q = update(VaultCredential).where(VaultCredential.session_blob.is_not(None))
            if ref:
                q = q.where(VaultCredential.public_id == ref)
            res = await db.execute(
                q.values(
                    session_blob=None, session_saved_at=None, session_expires_at=None
                )
            )
            await db.commit()
        await self.record("session_clear", ref or "*", [], f"cleared {res.rowcount}")
        return res.rowcount
