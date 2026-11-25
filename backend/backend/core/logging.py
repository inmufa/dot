import json
import logging
import re
import sys
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_REDACT = (
    "token",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "secret",
    "cookie",
    "vault",
    "totp",
    "storage_state",
)
_BEARER = re.compile(r"(?i)\b(bearer)\s+[^\s\"',]+")
_HANDLER_MARK = "_dot_handler"
# LogRecord attributes that are not caller-supplied extras.
_STD = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "request_id"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


def redact(value: Any) -> Any:
    """Mask values whose key looks secret, recursively through dicts and lists."""
    if isinstance(value, dict):
        return {
            k: "***" if any(s in str(k).lower() for s in _REDACT) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value


_SECRETS: set[str] = set()
_MIN_SECRET = 8


def register_secret(value: str | None) -> None:
    """Mask this exact value in every log line (tokens from the settings)."""
    if value and len(value) >= _MIN_SECRET:
        _SECRETS.add(value)


@contextmanager
def scoped_secrets(values: Iterable[str | None]) -> Iterator[None]:
    """Mask these values in logs only while they sit in memory (vault calls)."""
    mine = [v for v in values if v and len(v) >= _MIN_SECRET and v not in _SECRETS]
    _SECRETS.update(mine)
    try:
        yield
    finally:
        _SECRETS.difference_update(mine)


def scrub(text: str) -> str:
    for secret in _SECRETS:
        text = text.replace(secret, "***")
    return _BEARER.sub(r"\1 ***", text)


_ACCESS_QUERY = re.compile(r'("[A-Z]+ [^ ?"]+)\?[^ "]*')


def strip_query(text: str) -> str:
    """Access lines keep the path; search text and ids in the query string stay out."""
    return _ACCESS_QUERY.sub(r"\1?...", text)


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if _SECRETS:
            record.msg = scrub(record.getMessage())
            record.args = None
            if record.exc_info:
                record.exc_text = scrub(
                    logging.Formatter().formatException(record.exc_info)
                )
        return True


class QueryFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access":
            record.msg = strip_query(record.getMessage())
            record.args = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": scrub(strip_query(record.getMessage())),
        }
        extras = {k: v for k, v in vars(record).items() if k not in _STD}
        if extras:
            data.update(redact(extras))
        if record.exc_info:
            data["exc"] = scrub(self.formatException(record.exc_info))
        return json.dumps(data, ensure_ascii=False, default=str)


def setup_logging(*, as_json: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _HANDLER_MARK, True)
    handler.addFilter(RequestIdFilter())
    handler.addFilter(SecretFilter())
    handler.addFilter(QueryFilter())
    fmt = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    handler.setFormatter(JsonFormatter() if as_json else logging.Formatter(fmt))
    root = logging.getLogger()
    # Replace only our own handler so foreign ones (pytest caplog) survive.
    root.handlers = [h for h in root.handlers if not getattr(h, _HANDLER_MARK, False)]
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # httpx logs every request URL at INFO; search queries and fetched URLs stay private.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
