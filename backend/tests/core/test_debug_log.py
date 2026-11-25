import stat

from backend.core.logging import register_secret
from backend.routing.clients.debug_log import append_payload


def test_debug_file_is_private_scrubbed_and_capped(tmp_path):
    register_secret("sekret-token-123456")
    f = tmp_path / "llm.jsonl"
    append_payload(f, {"m": "has sekret-token-123456"}, max_bytes=200)
    assert "sekret" not in f.read_text()
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    for _ in range(20):
        append_payload(f, {"m": "x" * 40}, max_bytes=200)
    assert f.stat().st_size <= 200
    assert f.with_name("llm.jsonl.1").exists()
