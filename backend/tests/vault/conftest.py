import json
from pathlib import Path

import httpx
import pytest
from backend.settings import Settings
from fastapi import FastAPI
from httpx import AsyncClient

KEY = "ab" * 32
PASSWORD = "Sup3r-Secret-pw!9"
TOTP = "JBSWY3DPEHPK3PXP"
COOKIE_VALUE = "cookie-secret-value-123456"
SITE = "https://example.com"


@pytest.fixture
def settings(tmp_path: Path, ws: Path) -> Settings:
    return Settings(
        api_token="t" * 32,
        db_path=tmp_path / "t.db",
        workspace=ws,
        log_json=False,
        env="test",
        auto_title=False,
        approval_timeout_s=0.3,
        user_settings_path=tmp_path / "home" / "settings.json",
        default_permissions_path=None,
        user_skills_dir=tmp_path / "home-skills",
        user_rules_path=tmp_path / "home" / "USER_RULES.md",
        memory_dir=tmp_path / "home" / "memory",
        vault_key=KEY,
        vault_login_burst=3,
    )


class FakeWorker:
    """Stands in for the browser worker's vault routes."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.outcome = "logged_in"
        self.url = f"{SITE}/home"
        self.login_form = False
        self.restored: set[str] = set()
        self.cookie_exp = 4_102_444_800  # 2100
        self.page = f"{SITE}/account"

    def state(self) -> dict:
        cookie = {
            "name": "sid",
            "value": COOKIE_VALUE,
            "domain": "example.com",
            "path": "/",
            "expires": self.cookie_exp,
        }
        evil = {
            "name": "t",
            "value": "tracker",
            "domain": "evil.test",
            "path": "/",
            "expires": -1,
        }
        return {"cookies": [cookie, evil], "origins": []}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        body = json.loads(req.content) if req.content else {}
        self.calls.append((path, body))
        if path == "/vault/login":
            return httpx.Response(
                200,
                json={
                    "ok": self.outcome == "logged_in",
                    "outcome": self.outcome,
                    "url": self.url,
                    "title": "Home <b>",
                    "tainted": True,
                },
            )
        if path == "/vault/session/export":
            return httpx.Response(200, json=self.state())
        if path == "/vault/session/restored":
            return httpx.Response(
                200, json={"restored": [i for i in body["ids"] if i in self.restored]}
            )
        if path == "/vault/session/restore":
            self.restored.add(body["id"])
            return httpx.Response(
                200,
                json={
                    "restored": 1,
                    "login_form": self.login_form,
                    "url": self.url,
                    "title": "Home",
                },
            )
        if path == "/view/state":
            return httpx.Response(200, json={"open": True, "url": self.page})
        return httpx.Response(200, json={"url": self.url, "title": "T", "status": 200})

    def paths(self) -> list[str]:
        return [p for p, _ in self.calls]


@pytest.fixture
def worker(app: FastAPI) -> FakeWorker:
    fake = FakeWorker()
    app.state.vault.worker._b._client = httpx.AsyncClient(
        transport=httpx.MockTransport(fake)
    )
    return fake


async def make_cred(c: AsyncClient, **kw) -> dict:
    body = {
        "label": "ex",
        "origins": [SITE],
        "username": "alice",
        "password": PASSWORD,
        "totp_secret": TOTP,
        **kw,
    }
    r = await c.post("/v1/vault", json=body)
    assert r.status_code == 201, r.text
    return r.json()
