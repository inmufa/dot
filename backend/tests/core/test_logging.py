import json
import logging

from backend.core.api.language import resolve_language
from backend.core.logging import JsonFormatter, redact, scrub


def test_redact_nested():
    out = redact(
        {
            "a": 1,
            "api_token": "x",
            "h": {"Authorization": "y", "k": [{"password": "p"}]},
        }
    )
    assert out == {
        "a": 1,
        "api_token": "***",
        "h": {"Authorization": "***", "k": [{"password": "***"}]},
    }


def test_scrub_bearer():
    assert "abc123" not in scrub("sent Authorization: Bearer abc123 ok")


def test_json_formatter_redacts_extras_and_message():
    rec = logging.LogRecord("n", logging.INFO, "f", 1, "hit Bearer s3cr3t", None, None)
    rec.fields = {"api_token": "s3cr3t", "n": 1}
    data = json.loads(JsonFormatter().format(rec))
    assert "s3cr3t" not in json.dumps(data)
    assert data["fields"]["n"] == 1


def test_language_respects_q_values():
    assert resolve_language("en;q=0.1, ru;q=0.9") == "ru"
    assert resolve_language("de, uz-UZ") == "uz"
    assert resolve_language("ru;q=0") == "en"
    assert resolve_language(None) == "en"
