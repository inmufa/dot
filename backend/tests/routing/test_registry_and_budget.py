from pathlib import Path

import httpx
from backend.routing.services.budget import LimitWatcher, parse_props
from backend.routing.services.registry import load_registry, parse_registry
from backend.sessions.services.compactor import Compactor
from backend.settings import Settings


def test_registry_parses_entries_and_defaults():
    reg = parse_registry(
        '[[model]]\nfile = "a.gguf"\nname = "A"\nmmproj = "p.gguf"\ncontext_max = 8192\n'
        'thinking = true\neffort_levels = ["low", "high"]\n[[model]]\nfile = "b.gguf"\n'
    )
    a, b = reg["a.gguf"], reg["b.gguf"]
    assert (a.name, a.vision, a.context_max, a.thinking) == ("A", True, 8192, True)
    assert a.effort_levels == ("low", "high")
    assert (b.name, b.vision, b.context_max, b.thinking, b.effort_levels) == (
        "b.gguf",
        False,
        None,
        False,
        (),
    )


def test_registry_tolerates_garbage(tmp_path):
    assert parse_registry("not = [toml") == {}
    assert parse_registry('model = "x"') == {}
    reg = parse_registry(
        '[[model]]\nname = "no file"\n[[model]]\nfile = "ok.gguf"\ncontext_max = "big"\n'
        'effort_levels = "low"\nthinking = "yes"\n'
    )
    assert list(reg) == ["ok.gguf"]
    assert reg["ok.gguf"].context_max is None
    assert reg["ok.gguf"].effort_levels == ()
    assert reg["ok.gguf"].thinking is False
    assert load_registry(tmp_path / "missing.toml") == {}


def test_shipped_registry_is_valid():
    root = Path(__file__).resolve().parents[3]
    reg = load_registry(root / "models/registry.toml")
    assert reg
    assert all(e.file.endswith(".gguf") for e in reg.values())


def test_parse_props():
    props = {"default_generation_settings": {"n_ctx": 65536}, "total_slots": 4}
    assert parse_props(props) == (65536, 4)
    assert parse_props({}) == (None, None)
    assert parse_props(None) == (None, None)
    assert parse_props(
        {"default_generation_settings": {"n_ctx": 10}, "total_slots": 0}
    ) == (
        None,
        None,
    )
    assert parse_props({"default_generation_settings": {"n_ctx": True}}) == (None, None)


def settings(**kw) -> Settings:
    return Settings(api_token="x" * 20, llm_base_url="http://llm:8080/v1", **kw)


def watcher(s: Settings, body, status: int = 200) -> LimitWatcher:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/props"
        return httpx.Response(status, json=body)

    return LimitWatcher(s, httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_watcher_applies_server_numbers():
    s = settings()
    assert s.llm_context_limit == 32768
    ok = await watcher(
        s, {"default_generation_settings": {"n_ctx": 131072}, "total_slots": 6}
    ).refresh()
    assert ok
    assert (s.llm_context_limit, s.llm_parallel_slots) == (131072, 6)


async def test_watcher_cap_and_unreachable_keep_the_seed():
    s = settings(llm_context_cap=50000)
    await watcher(s, {"default_generation_settings": {"n_ctx": 131072}}).refresh()
    assert s.llm_context_limit == 50000
    s2 = settings(llm_context_limit=4096)
    assert await watcher(s2, {}, status=503).refresh() is False
    assert await watcher(s2, {"junk": 1}).refresh() is False
    assert (s2.llm_context_limit, s2.llm_parallel_slots) == (4096, 2)


def compactor(limit, **kw):
    return Compactor(
        store=None,  # type: ignore[arg-type]
        llm=None,  # type: ignore[arg-type]
        restorer=None,  # type: ignore[arg-type]
        workspace="",
        limit=limit,
        **kw,
    )


def test_compaction_threshold_follows_a_live_limit_and_cap():
    s = settings()
    c = compactor(lambda: s.llm_context_limit, threshold=0.75)
    assert c.threshold == 24576
    s.llm_context_limit = 262144  # a bigger -c after /props refresh
    assert c.threshold == 196608
    assert compactor(262144, threshold=0.75, max_tokens=100_000).threshold == 100_000
    assert compactor(32768, threshold=0.75, max_tokens=100_000).threshold == 24576
