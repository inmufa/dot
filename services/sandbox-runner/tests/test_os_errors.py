from dot_sandbox.errors import install_handlers
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_os_error_is_a_clean_4xx_with_the_reason():
    app = FastAPI()
    install_handlers(app)

    @app.get("/x")
    def _x():
        raise PermissionError(13, "Permission denied", "/nope/file")

    r = TestClient(app).get("/x")
    assert r.status_code == 403
    assert r.json()["error"] == "os_error"
    assert "Permission denied" in r.json()["detail"]
