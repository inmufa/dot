"""What the agent (BrowserLogin) and the owner (Browser tab) do with the vault."""

import contextlib
import logging
from typing import Any

from backend.core.api.ratelimit import TokenBucket
from backend.core.exceptions import DomainException
from backend.core.logging import scoped_secrets
from backend.vault import origins as org
from backend.vault import sessionstate
from backend.vault.models import VaultCredential
from backend.vault.service import NOT_FOUND, VaultService
from backend.vault.worker import ORIGIN_MISMATCH, VaultWorker

logger = logging.getLogger(__name__)
RATE_LIMITED = 4145
NO_PAGE, NO_SESSION = 4150, 4151
REASONS = {
    "wrong_credentials": "wrong credentials (or the site rejected the login)",
    "captcha": "a captcha blocks automated login; ask the owner to log in by hand in the Browser tab",
    "2fa_required": "a second factor is required and no TOTP secret is stored",
    "form_not_found": "no login form was found on the page",
    "failed": "the login did not finish",
}


class VaultAgent:
    def __init__(self, service: VaultService, worker: VaultWorker) -> None:
        self.svc = service
        self.worker = worker
        cfg = service.cfg
        self._bucket = TokenBucket(cfg.vault_login_rate_per_min, cfg.vault_login_burst)
        # Dot session id -> credential ids the owner approved BrowserLogin for.
        self.consent: dict[str, set[str]] = {}
        # Worker session id -> credential ids whose cookies live in that context.
        self.live: dict[str, set[str]] = {}

    def _head(self, d: dict[str, Any]) -> str:
        title = " ".join(str(d.get("title", "")).split())[:200]
        return f"Page: {str(d.get('url', ''))[:500]}\nTitle: {title}"

    async def describe(self, args: dict[str, Any]) -> str | None:
        """Approval card text: site, username, label. Never a secret."""
        try:
            row = await self.svc.row(str(args.get("credential", "")), by_label=True)
        except DomainException:
            return None
        sites = ", ".join(row.origins)
        user = row.username or "(session only)"
        return f"Sign in to {sites}\nUsername: {user}\nSaved login: {row.label}"

    async def login(self, sid: str, label: str, url: str | None) -> str:
        row = await self.svc.row(label, by_label=True)
        if url and not org.matches(url, list(row.origins)):
            await self.svc.record(
                "use", row.label, list(row.origins), "refused: origin", sid
            )
            raise DomainException(ORIGIN_MISMATCH)
        if self._bucket.take(row.public_id):
            raise DomainException(RATE_LIMITED, retry_after=60)
        cur = None
        with contextlib.suppress(DomainException):
            cur = await self.worker.page_url(sid)
        on_site = bool(cur) and org.matches(cur or "", list(row.origins))
        start = url or (cur if on_site else row.origins[0] + "/")
        text = await self._try_session(sid, row, start)
        if text:
            return text
        secrets = self.svc.secrets(row)
        if secrets is None:
            await self.svc.record(
                "use", row.label, list(row.origins), "session expired", sid
            )
            return "failed: the saved session expired and no password is stored; the owner must log in by hand and save the session"
        body = {
            "origins": list(row.origins),
            "username": row.username,
            "password": secrets.password,
            "totp_secret": secrets.totp_secret,
            "url": url or (None if on_site else start),
        }
        body = {k: v for k, v in body.items() if v is not None}
        with scoped_secrets(secrets.values()):
            try:
                res = await self.worker.login(sid, body)
            except DomainException as exc:
                await self.svc.record(
                    "use", row.label, list(row.origins), f"error {exc.code}", sid
                )
                raise
            finally:
                del body, secrets
        return await self._after(sid, row, res)

    async def _after(self, sid: str, row: VaultCredential, res: dict[str, Any]) -> str:
        outcome = str(res.get("outcome", "failed"))
        await self.svc.record("use", row.label, list(row.origins), outcome, sid)
        if outcome != "logged_in":
            return f"failed: {REASONS.get(outcome, outcome)}\n{self._head(res)}"
        await self.svc.touch(row.public_id)
        self.consent.setdefault(sid, set()).add(row.public_id)
        self.live.setdefault(sid, set()).add(row.public_id)
        await self.capture(sid, row.public_id)
        return f"logged in\n{self._head(res)}"

    async def capture(self, sid: str, cred: str) -> dict[str, Any] | None:
        """Export this context's cookies for the credential and seal them."""
        row = await self.svc.row(cred)
        state = await self.worker.export(sid, list(row.origins))
        if state is None:
            self.live.get(sid, set()).discard(cred)
            return None
        with scoped_secrets(sessionstate.secret_values(state)):
            return await self.svc.save_session(cred, state)

    async def _try_session(
        self, sid: str, row: VaultCredential, url: str
    ) -> str | None:
        """Restore a saved session; a text result when it still works, else None."""
        state = await self.svc.load_session(row)
        if state is None:
            return None
        with scoped_secrets(sessionstate.secret_values(state)):
            res = await self.worker.restore(
                sid, row.public_id, list(row.origins), state, url, acting=True
            )
        del state
        if res.get("login_form") is False:
            self.consent.setdefault(sid, set()).add(row.public_id)
            self.live.setdefault(sid, set()).add(row.public_id)
            await self.svc.touch(row.public_id)
            await self.svc.record(
                "use", row.label, list(row.origins), "session restored", sid
            )
            return "logged in (saved session restored)\n" + self._head(res)
        await self.svc.clear_session(row.public_id)
        await self.svc.record(
            "use", row.label, list(row.origins), "session expired", sid
        )
        return None

    # Owner and agent navigation -----------------------------------------------------

    async def _matching(self, url: str) -> list[VaultCredential]:
        return await self.svc.logins_for(url, with_session=True)

    async def restore_on_navigate(self, sid: str, url: str, *, owner: bool) -> None:
        """Restore bound sessions before a navigation. Never raises: navigation goes on."""
        if not self.svc.enabled:
            return
        try:
            await self._restore(sid, url, owner=owner)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vault session restore skipped: %s", type(exc).__name__)

    async def _restore(self, sid: str, url: str, *, owner: bool) -> None:
        rows = await self._matching(url)
        if not owner:
            rows = [r for r in rows if r.public_id in self.consent.get(sid, set())]
        if not rows:
            return
        done = await self.worker.restored(sid, [r.public_id for r in rows])
        for row in rows:
            if row.public_id in done:
                continue
            state = await self.svc.load_session(row)
            if state is None:
                continue
            with scoped_secrets(sessionstate.secret_values(state)):
                await self.worker.restore(
                    sid, row.public_id, list(row.origins), state, None, acting=not owner
                )
            self.live.setdefault(sid, set()).add(row.public_id)

    async def hint(self, sid: str, url: str) -> str:
        """Labels of saved logins for this site (the model needs a label to ask for one)."""
        if not self.svc.enabled:
            return ""
        with contextlib.suppress(Exception):
            labels = [r.label for r in await self.svc.logins_for(url)]
            if labels:
                names = ", ".join(repr(x) for x in labels[:5])
                return f"\nSaved logins for this site: {names}. BrowserLogin(credential=<label>) signs in (the owner approves; you never see the secret)."
        return ""

    # Owner actions ----------------------------------------------------------------------

    async def save_current(
        self, sid: str, cred: str | None, label: str | None
    ) -> dict[str, Any]:
        """Owner: save the page's session onto a credential, or a new session-only entry."""
        url = await self.worker.page_url(sid)
        origin = org.origin_of(url or "")
        if origin is None:
            raise DomainException(NO_PAGE)
        if cred:
            row = await self.svc.row(cred)
            if origin not in {org.origin_of(o) for o in row.origins}:
                await self.svc.update(cred, {"origins": [*row.origins, origin]})
        else:
            if not label:
                raise DomainException(NOT_FOUND)
            made = await self.svc.create(label=label, origins=[origin])
            cred = made["id"]
        self.live.setdefault(sid, set()).add(cred)
        meta = await self.capture(sid, cred)
        if meta is None:
            raise DomainException(NO_SESSION)
        return meta

    async def refresh(self) -> None:
        """Timer: re-export live contexts so rotated cookies and reaped contexts keep state."""
        for sid, creds in list(self.live.items()):
            for cred in list(creds):
                try:
                    await self.capture(sid, cred)
                except DomainException:
                    logger.warning("vault session refresh failed for a credential")
                    creds.discard(cred)
            if not creds:
                self.live.pop(sid, None)
