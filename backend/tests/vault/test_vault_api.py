import logging
from pathlib import Path

from backend.main import create_app
from backend.settings import Settings
from conftest import COOKIE_VALUE, PASSWORD, SITE, TOTP, make_cred
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

SECRETS = (PASSWORD, TOTP, COOKIE_VALUE)


def clean(text: str) -> None:
    for s in SECRETS:
        assert s not in text


async def test_crud_never_returns_secrets(authed: AsyncClient, caplog):
    caplog.set_level(logging.DEBUG)
    made = await make_cred(authed)
    assert made["has_password"] is True
    assert made["has_totp"] is True
    assert made["has_session"] is False
    seen = [str(made)]
    seen.append((await authed.get("/v1/vault")).text)
    r = await authed.patch(
        f"/v1/vault/{made['id']}", json={"password": PASSWORD + "2", "username": "bob"}
    )
    seen.append(r.text)
    assert r.json()["username"] == "bob"
    assert set(r.json()) == set(made)
    for body in seen:
        clean(body)
        assert PASSWORD + "2" not in body
    clean(caplog.text)
    assert "password" not in r.json()


async def test_no_reveal_endpoint(authed: AsyncClient):
    made = await make_cred(authed)
    for method in ("get", "post"):
        r = await getattr(authed, method)(f"/v1/vault/{made['id']}/reveal")
        assert r.status_code in (404, 405)
    r = await authed.get(f"/v1/vault/{made['id']}")
    assert r.status_code == 405


async def test_label_unique_and_validation(authed: AsyncClient):
    await make_cred(authed)
    r = await authed.post("/v1/vault", json={"label": "ex", "origins": [SITE]})
    assert r.status_code == 409
    assert r.json()[0]["code"] == 4142
    for bad in ({"origins": ["http://example.com"]}, {"origins": ["nonsense"]}):
        r = await authed.post(
            "/v1/vault", json={"label": "z", "password": PASSWORD, **bad}
        )
        assert r.status_code == 422
        clean(r.text)
    r = await authed.post(
        "/v1/vault",
        json={"label": "z", "origins": [SITE], "totp_secret": "!!!notbase32"},
    )
    assert r.status_code == 422
    assert "notbase32" not in r.text
    r = await authed.post(
        "/v1/vault", json={"label": "q", "origins": [SITE], "password": "p" * 2000}
    )
    assert r.status_code == 422
    assert "pppp" not in r.text


async def test_update_origins_and_secret_keep(authed: AsyncClient, app: FastAPI):
    made = await make_cred(authed)
    r = await authed.patch(
        f"/v1/vault/{made['id']}", json={"origins": [SITE, "https://login.example.com"]}
    )
    assert r.json()["origins"] == [SITE, "https://login.example.com"]
    row = await app.state.vault.svc.row(made["id"])
    secrets = app.state.vault.svc.secrets(row)
    assert secrets.password == PASSWORD  # omitted secret fields are kept
    assert secrets.totp_secret == TOTP
    r = await authed.patch(f"/v1/vault/{made['id']}", json={"totp_secret": ""})
    assert r.json()["has_totp"] is False


async def test_delete_needs_confirm(authed: AsyncClient):
    made = await make_cred(authed)
    r = await authed.delete(f"/v1/vault/{made['id']}")
    assert r.json()[0]["code"] == 4143
    r = await authed.delete(f"/v1/vault/{made['id']}?confirm=wrong")
    assert r.status_code == 400
    assert (
        await authed.delete(f"/v1/vault/{made['id']}?confirm={made['id']}")
    ).json() == {"ok": True}
    assert (await authed.get("/v1/vault")).json() == []
    assert (
        await authed.delete(f"/v1/vault/{made['id']}?confirm={made['id']}")
    ).status_code == 404


async def test_auth_required(authed: AsyncClient, client: AsyncClient):
    anon = AsyncClient(
        transport=ASGITransport(app=client._transport.app), base_url="http://t"
    )
    assert (await anon.get("/v1/vault")).status_code == 401


async def test_encrypted_at_rest(authed: AsyncClient, settings: Settings):
    await make_cred(authed)
    raw = b"".join(p.read_bytes() for p in Path(settings.db_path).parent.glob("t.db*"))
    for s in (PASSWORD, TOTP):
        assert s.encode() not in raw
    assert b"alice" in raw  # username is metadata, not a secret


async def test_audit_rows_have_no_secrets(authed: AsyncClient):
    made = await make_cred(authed)
    await authed.patch(f"/v1/vault/{made['id']}", json={"password": PASSWORD + "x"})
    await authed.delete(f"/v1/vault/{made['id']}?confirm={made['id']}")
    text = (await authed.get("/v1/audit")).text
    for tool in ("vault.create", "vault.update", "vault.delete"):
        assert tool in text
    clean(text)
    assert PASSWORD + "x" not in text


async def test_rate_limit(authed: AsyncClient, app: FastAPI):
    app.state.settings.vault_api_burst = 1
    app.state.settings.vault_api_rate_per_min = 0.1
    app.state.vault_bucket = None
    codes = [
        (
            await authed.post("/v1/vault", json={"label": f"l{i}", "origins": [SITE]})
        ).status_code
        for i in range(3)
    ]
    assert 429 in codes


async def test_count_cap(authed: AsyncClient, app: FastAPI):
    app.state.vault.svc.cfg.vault_max_credentials = 1
    await make_cred(authed)
    r = await authed.post("/v1/vault", json={"label": "b", "origins": [SITE]})
    assert r.json()[0]["code"] == 4146


async def test_vault_off_without_key(tmp_path: Path, ws: Path, llm, sandbox, caplog):

    cfg = Settings(
        _env_file=None,
        api_token="t" * 32,
        db_path=tmp_path / "n.db",
        workspace=ws,
        log_json=False,
        env="test",
        auto_title=False,
        default_permissions_path=None,
        user_settings_path=tmp_path / "h" / "s.json",
        user_skills_dir=tmp_path / "hs",
        user_rules_path=tmp_path / "h" / "U.md",
        memory_dir=tmp_path / "h" / "m",
    )
    app = create_app(cfg, llm=llm, sandbox=sandbox)
    async with app.router.lifespan_context(app):
        c = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            headers={"Authorization": "Bearer " + "t" * 32},
        )
        assert (await c.get("/v1/vault/status")).json() == {"enabled": False}
        r = await c.get("/v1/vault")
        assert r.status_code == 503
        assert r.json()[0]["code"] == 4140
        assert (
            await c.post("/v1/vault", json={"label": "a", "origins": [SITE]})
        ).status_code == 503
        assert (await c.get("/v1/sessions")).status_code == 200


async def test_bad_key_disables_vault_without_echo(
    tmp_path: Path, ws: Path, llm, sandbox, caplog
):
    bad = "zz-not-hex-key-" * 4
    cfg = Settings(
        api_token="t" * 32,
        db_path=tmp_path / "n.db",
        workspace=ws,
        log_json=False,
        env="test",
        auto_title=False,
        default_permissions_path=None,
        user_settings_path=tmp_path / "h" / "s.json",
        user_skills_dir=tmp_path / "hs",
        user_rules_path=tmp_path / "h" / "U.md",
        memory_dir=tmp_path / "h" / "m",
        vault_key=bad,
    )
    app = create_app(cfg, llm=llm, sandbox=sandbox)
    async with app.router.lifespan_context(app):
        assert app.state.vault.svc.enabled is False
    assert bad not in caplog.text
    assert "vault disabled" in caplog.text
