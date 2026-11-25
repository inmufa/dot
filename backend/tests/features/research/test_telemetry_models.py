import httpx
import pytest
from backend.routing.services.telemetry import TelemetryService, read_vram
from fastapi import FastAPI
from httpx import AsyncClient

PROPS = {
    "model_path": "/models/Qwen-Q4.gguf",
    "default_generation_settings": {"n_ctx": 32768},
    "chat_template_caps": {"reasoning_effort_levels": ["low", "high"]},
}
SLOTS = [
    {
        "id": 0,
        "is_processing": True,
        "n_ctx": 32768,
        "n_past": 100,
        "timings": {"predicted_per_second": 28.94},
    },
    {"id": 1, "is_processing": False, "n_ctx": 32768},
]


def llama(routes: dict[str, object], loads: list | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/models/load":
            (loads if loads is not None else []).append(req.content)
            return httpx.Response(200, json={"success": True})
        if req.url.path in routes:
            return httpx.Response(200, json=routes[req.url.path])
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def install(app: FastAPI, client: httpx.AsyncClient, **settings) -> TelemetryService:
    for k, v in settings.items():
        setattr(app.state.settings, k, v)
    svc = TelemetryService(app.state.settings, app.state.sandbox, client)
    app.state.telemetry = svc
    return svc


async def test_telemetry_full(authed: AsyncClient, app: FastAPI, tmp_path):
    (tmp_path / "mem_info_vram_used").write_text(str(3000 * 1024 * 1024))
    (tmp_path / "mem_info_vram_total").write_text(str(8192 * 1024 * 1024))
    install(
        app,
        llama({"/health": {"status": "ok"}, "/props": PROPS, "/slots": SLOTS}),
        vram_sysfs=tmp_path,
    )
    t = (await authed.get("/v1/telemetry")).json()
    assert t["llm_up"] is True
    assert t["model"] == "Qwen-Q4.gguf"
    assert t["context_size"] == 32768
    assert [s["busy"] for s in t["slots"]] == [True, False]
    assert t["tokens_per_s"] == 28.9
    assert (t["vram_used_mb"], t["vram_total_mb"]) == (3000, 8192)
    assert t["sandbox_up"] is True
    assert t["reasoning_effort_levels"] == ["low", "high"]


async def test_telemetry_llm_down_is_all_null(authed: AsyncClient, app: FastAPI):
    install(app, llama({}), vram_sysfs=None)
    t = (await authed.get("/v1/telemetry")).json()
    assert t["llm_up"] is False
    assert t["model"] is None
    assert t["slots"] == []
    assert t["vram_used_mb"] is None


async def test_garbage_from_llama_is_tolerated(authed: AsyncClient, app: FastAPI):
    install(
        app,
        llama({"/health": {}, "/props": [1], "/slots": {"x": 1}}),
        vram_sysfs=None,
    )
    assert (await authed.get("/v1/telemetry")).status_code == 200


def test_vram_unreadable(tmp_path):
    assert read_vram(None) == (None, None)
    (tmp_path / "mem_info_vram_used").write_text("nope")
    assert read_vram(tmp_path) == (None, None)


@pytest.fixture
def models_dir(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    (d / "Qwen-Q4.gguf").write_bytes(b"0" * (3 * 1024 * 1024))
    (d / "Other.gguf").write_bytes(b"0" * 1024 * 1024)
    (d / "mmproj-Qwen-BF16.gguf").write_bytes(b"0")
    (d / "notes.txt").write_text("x")
    return d


async def test_models_listing(authed: AsyncClient, app: FastAPI, models_dir):
    install(app, llama({"/props": PROPS}), models_dir=models_dir)
    got = {m["name"]: m for m in (await authed.get("/v1/models")).json()}
    assert set(got) == {"Qwen-Q4.gguf", "Other.gguf"}
    assert got["Qwen-Q4.gguf"]["active"] is True
    assert (
        got["Qwen-Q4.gguf"]["vision"] is False
    )  # unlisted: no registry entry, no vision
    assert got["Qwen-Q4.gguf"]["listed"] is False
    assert got["Qwen-Q4.gguf"]["effort_levels"] == []
    assert got["Other.gguf"]["active"] is False
    assert got["Qwen-Q4.gguf"]["size_mb"] == 3


async def test_models_missing_dir(authed: AsyncClient, app: FastAPI, tmp_path):
    install(app, llama({}), models_dir=tmp_path / "nope")
    assert (await authed.get("/v1/models")).json() == []


async def test_select_is_501_with_exact_command(
    authed: AsyncClient, app: FastAPI, models_dir
):
    install(app, llama({}), models_dir=models_dir)
    r = await authed.post("/v1/models/select", json={"name": "Other.gguf"})
    assert r.status_code == 501
    assert "make model" in r.text
    listed = {m["name"]: m for m in (await authed.get("/v1/models")).json()}
    assert listed["Other.gguf"]["switch_command"] == "make model NAME=Other.gguf"


async def test_select_unknown_is_404(authed: AsyncClient, app: FastAPI, models_dir):
    install(app, llama({}), models_dir=models_dir)
    r = await authed.post("/v1/models/select", json={"name": "../etc/passwd"})
    assert r.status_code == 404
