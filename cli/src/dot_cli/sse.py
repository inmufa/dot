"""Server-sent events decoding into typed StreamEvents."""

import codecs
import re

from dot_contracts.events import StreamEvent
from pydantic import TypeAdapter, ValidationError

EVENT_ADAPTER: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)
_LINE_BREAK = re.compile(r"\r\n|\n|\r")


def parse_data_line(line: str) -> StreamEvent | None:
    """Parse one `data: <json>` line; anything else or malformed returns None."""
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload:
        return None
    try:
        return EVENT_ADAPTER.validate_json(payload)
    except ValidationError:
        return None


class SseDecoder:
    """Incremental decoder: feed arbitrary byte/text chunks, get complete events."""

    def __init__(self) -> None:
        self._buffer = ""
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def feed(self, chunk: bytes | str) -> list[StreamEvent]:
        text = self._utf8.decode(chunk) if isinstance(chunk, bytes) else chunk
        *lines, self._buffer = _LINE_BREAK.split(self._buffer + text)
        return self._parse(lines)

    def flush(self) -> list[StreamEvent]:
        """Parse a trailing line that had no terminating newline."""
        rest, self._buffer = self._buffer, ""
        return self._parse([rest])

    @staticmethod
    def _parse(lines: list[str]) -> list[StreamEvent]:
        events = (parse_data_line(line) for line in lines)
        return [event for event in events if event is not None]
