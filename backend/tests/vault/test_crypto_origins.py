import pytest
from backend.core.logging import scoped_secrets, scrub
from backend.vault import crypto, rotate
from backend.vault.crypto import VaultDataError
from backend.vault.origins import clean_origins, cookie_in_scope, matches, origin_of
from conftest import KEY as ENV_KEY
from conftest import PASSWORD, make_cred

KEY = bytes.fromhex("11" * 32)


def test_round_trip_and_fresh_nonce():
    aad = crypto.aad("V123456789", "secret", ["https://a.com"])
    a, b = crypto.seal(KEY, b"hunter2", aad), crypto.seal(KEY, b"hunter2", aad)
    assert a != b
    assert b"hunter2" not in a
    assert crypto.unseal(KEY, a, aad) == b"hunter2"


def test_tamper_is_detected():
    aad = crypto.aad("V1", "secret", ["https://a.com"])
    blob = bytearray(crypto.seal(KEY, b"hunter2", aad))
    for pos in (0, 15, len(blob) - 1):  # nonce, body, tag
        bad = bytearray(blob)
        bad[pos] ^= 1
        with pytest.raises(VaultDataError):
            crypto.unseal(KEY, bytes(bad), aad)
    with pytest.raises(VaultDataError):
        crypto.unseal(KEY, bytes(blob[:8]), aad)


def test_blob_is_bound_to_record_kind_origin_and_key():
    blob = crypto.seal(KEY, b"x", crypto.aad("V1", "secret", ["https://a.com"]))
    for other in (
        crypto.aad("V2", "secret", ["https://a.com"]),
        crypto.aad("V1", "session", ["https://a.com"]),
        crypto.aad("V1", "secret", ["https://b.com"]),
    ):
        with pytest.raises(VaultDataError):
            crypto.unseal(KEY, blob, other)
    with pytest.raises(VaultDataError):
        crypto.unseal(
            bytes.fromhex("22" * 32),
            blob,
            crypto.aad("V1", "secret", ["https://a.com"]),
        )


def test_key_parsing_never_echoes_the_value():
    assert crypto.parse_key(None) is None
    assert crypto.parse_key("  ") is None
    assert crypto.parse_key("ab" * 32) == bytes.fromhex("ab" * 32)
    with pytest.raises(ValueError, match="64 hex") as exc:
        crypto.parse_key("not-a-key-zzzz")
    assert "zzzz" not in str(exc.value)


OK = ["https://example.com"]


@pytest.mark.parametrize(
    "url",
    [
        "https://evil-example.com/",
        "https://example.com.evil.net/",
        "https://example.com@evil.net/",
        "https://sub.example.com/",
        "http://example.com/",
        "https://example.com:8443/",
        "https://exаmple.com/",  # cyrillic a
        "https://xn--exmple-cua.com/",
        "javascript:alert(1)",
        "",
    ],
)
def test_lookalikes_do_not_match(url):
    assert not matches(url, OK)


def test_matching_normalises():
    assert matches("HTTPS://EXAMPLE.com:443/x?y#z", OK)
    assert matches("https://bücher.example/", ["https://xn--bcher-kva.example"])
    assert origin_of("https://xn--bcher-kva.example") == "https://xn--bcher-kva.example"


def test_clean_origins_rules():
    assert clean_origins(["HTTPS://A.com/x", "https://a.com"], allow_http=False) == [
        "https://a.com"
    ]
    for bad in (["http://a.com"], ["ftp://a.com"], ["a.com"], []):
        with pytest.raises(ValueError, match="origin"):
            clean_origins(bad, allow_http=False)
    assert clean_origins(["http://127.0.0.1:9"], allow_http=True)


def test_cookie_scope():
    o = ["https://app.example.com"]
    assert cookie_in_scope(".example.com", o)
    assert not cookie_in_scope("evil.com", o)
    assert not cookie_in_scope("com", o)


def test_scoped_secrets_mask_logs_only_while_in_scope():
    with scoped_secrets(["pa55word-long-enough"]):
        assert scrub("x pa55word-long-enough y") == "x *** y"
    assert scrub("x pa55word-long-enough y") == "x pa55word-long-enough y"


async def test_rotation_reseals_everything(
    authed, app, settings, worker, tmp_path, monkeypatch
):
    made = await make_cred(authed)
    await app.state.vault.svc.save_session(made["id"], worker.state())
    env = tmp_path / ".env"
    env.write_text(f"A=1\nDOT_VAULT_KEY={ENV_KEY}\nB=2\n")
    assert rotate.rotate(env, settings.db_path) == 1
    text = env.read_text()
    new_hex = next(
        ln.split("=", 1)[1]
        for ln in text.splitlines()
        if ln.startswith("DOT_VAULT_KEY=")
    )
    assert new_hex != ENV_KEY
    assert text.startswith("A=1\n")
    assert (env.stat().st_mode & 0o777) == 0o600
    svc = app.state.vault.svc
    row = await svc.row(made["id"])
    with pytest.raises(Exception):  # old key no longer opens it  # noqa: B017, PT011
        svc.secrets(row)
    svc.key = bytes.fromhex(new_hex)
    assert svc.secrets(row).password == PASSWORD
    assert await svc.load_session(row)
    assert list(settings.db_path.parent.glob("t.db.pre-rotate-*"))
