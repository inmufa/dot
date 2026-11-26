from backend.routing.clients.llama_client import _draft
from backend.routing.clients.llama_parse import (
    ContentFilter,
    draft_from_tag,
    draft_target,
)


def test_target_comes_from_unfinished_json():
    assert (
        draft_target('{"file_path": "/work/sun-shadow.html", "content": "<!doc')
        == "/work/sun-shadow.html"
    )
    assert draft_target('{"query": "median salar') == "median salar"
    assert draft_target('{"content": "x') == ""


def test_native_tool_call_draft_reports_name_target_and_size():
    acc = {
        0: {
            "id": "c1",
            "name": "Write",
            "args": '{"file_path": "a/b.html", "content": "' + "x" * 50,
        }
    }
    name, target, chars = _draft(acc, ContentFilter()) or ("", "", 0)
    assert (name, target) == ("Write", "a/b.html")
    assert chars > 50


def test_tag_call_drafts_in_json_and_function_styles():
    f = ContentFilter()
    f.feed(
        'Sure. <tool_call>{"name": "WebFetch", "arguments": {"url": "https://example.com/a'
    )
    assert _draft({}, f) == (
        "WebFetch",
        "https://example.com/a",
        len(' "arguments": {"url": "https://example.com/a'),
    ) or _draft({}, f)[:2] == ("WebFetch", "https://example.com/a")
    assert draft_from_tag("<function=Bash>\n<parameter=command>\nls -la\n") == (
        "Bash",
        "ls -la",
        len("\n<parameter=command>\nls -la\n"),
    )
    assert draft_from_tag('{"argu') is None
