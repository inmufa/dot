import pytest
from backend.core.db import make_engine
from backend.settings import Settings
from pydantic import ValidationError
from sqlalchemy import text


def test_placeholder_token_rejected(tmp_path):
    with pytest.raises(ValidationError):
        Settings(api_token="change-me-to-a-long-random-string")


def test_short_token_rejected():
    with pytest.raises(ValidationError):
        Settings(api_token="short")


async def test_engine_uses_wal_and_foreign_keys(settings: Settings):
    engine = make_engine(settings)
    async with engine.connect() as conn:
        mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
        fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
    await engine.dispose()
    assert mode == "wal"
    assert fk == 1
