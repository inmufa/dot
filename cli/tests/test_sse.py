import json

from dot_cli.sse import SseDecoder, parse_data_line
from dot_contracts.events import DoneEvent, TokenEvent, UsageEvent

TOKEN = 'data: {"type":"token","text":"hi"}'


def test_parse_valid_line() -> None:
    assert parse_data_line(TOKEN) == TokenEvent(text="hi")


def test_parse_ignores_non_data_and_malformed() -> None:
    for line in [
        "",
        ": keepalive",
        "event: x",
        "data:",
        "data: {nope",
        'data: {"type":"zzz"}',
    ]:
        assert parse_data_line(line) is None


def test_split_chunks_mid_line_and_mid_utf8() -> None:
    raw = (TOKEN.replace("hi", "привет") + "\n\n").encode()
    decoder = SseDecoder()
    events = []
    for i in range(len(raw)):  # byte by byte, splits multibyte chars
        events += decoder.feed(raw[i : i + 1])
    assert events == [TokenEvent(text="привет")]


def test_multiple_events_one_chunk_crlf() -> None:
    done = json.dumps({"type": "done", "stop_reason": "x"})
    chunk = f"{TOKEN}\r\n\r\ndata: {done}\r\n\r\n"
    assert SseDecoder().feed(chunk) == [
        TokenEvent(text="hi"),
        DoneEvent(stop_reason="x"),
    ]


def test_malformed_lines_skipped_stream_continues() -> None:
    usage = json.dumps({"type": "usage", "context_tokens": 1, "context_limit": 2})
    chunk = f"data: {{broken\n\n: ping\n\ndata: {usage}\n\n"
    assert SseDecoder().feed(chunk) == [UsageEvent(context_tokens=1, context_limit=2)]


def test_flush_parses_unterminated_tail() -> None:
    decoder = SseDecoder()
    assert decoder.feed(TOKEN) == []
    assert decoder.flush() == [TokenEvent(text="hi")]


def test_future_event_types_and_extra_fields_do_not_break_the_stream() -> None:
    stream = (
        'data: {"type":"brand_new","x":1}\n\n'
        'data: {"type":"token","text":"a","future_field":true}\n\n'
        'data: {"type":"compaction","tokens_before":1,"tokens_after":1,"extra":[]}\n\n'
        'data: {"type":"done","stop_reason":"end_turn"}\n\n'
    )
    events = SseDecoder().feed(stream)
    assert [e.type for e in events] == ["token", "compaction", "done"]
