import stat

from backend.core.db import make_engine
from backend.main import create_app
from backend.settings import Settings


def test_db_dir_and_file_are_owner_only(tmp_path):
    db = tmp_path / "data" / "dot.db"
    make_engine(Settings(api_token="x" * 20, db_path=db))
    assert stat.S_IMODE(db.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(db.stat().st_mode) == 0o600


def test_docs_and_schema_are_off_in_prod(tmp_path):
    s = Settings(api_token="x" * 20, db_path=tmp_path / "d.db", env="prod")
    app = create_app(s)
    assert app.docs_url is None
    assert app.openapi_url is None
    dev = create_app(s.model_copy(update={"env": "dev"}))
    assert dev.docs_url == "/docs"


def test_access_log_drops_query_strings():
    from backend.core.logging import strip_query  # noqa: PLC0415

    line = '127.0.0.1:1 - "GET /v1/search?q=my%20password&x=1 HTTP/1.1" 200'
    out = strip_query(line)
    assert "password" not in out
    assert '"GET /v1/search?..." 200' in out.replace(" HTTP/1.1", "")
