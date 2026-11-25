import json
import math

import pytest
from backend.cognition.services.widgets.present_tool import (
    WidgetError,
    validate_present,
)


def ok(kind, props, title=None):
    return validate_present({"kind": kind, "title": title, "props": props})


VALID = {
    "table": {"columns": ["A", "B"], "rows": [["x", 1], [None, True]], "caption": "c"},
    "chart": {
        "type": "bar",
        "labels": ["a", "b"],
        "series": [{"name": "s", "values": [1, 2.5]}],
        "unit": "ms",
    },
    "stats": {"items": [{"label": "L", "value": 5, "delta": "+1", "trend": "up"}]},
    "steps": {"items": [{"label": "a", "status": "done", "detail": "d"}]},
    "checklist": {"items": [{"label": "a", "checked": True}, {"label": "b"}]},
    "cards": {
        "items": [
            {
                "title": "T",
                "tags": ["x"],
                "fields": [{"label": "RAM", "value": "16 GB"}],
            }
        ]
    },
    "callout": {"tone": "warning", "text": "careful"},
    "tabs": {"tabs": [{"label": "a", "text": "b"}]},
    "accordion": {"items": [{"title": "a", "text": "b"}]},
    "choices": {"options": ["Yes", "No"]},
}


@pytest.mark.parametrize(("kind", "props"), VALID.items())
def test_valid_kinds_roundtrip(kind, props):
    k, title, out = ok(kind, props, "Hello")
    assert (k, title) == (kind, "Hello")
    json.dumps(out)  # JSON-safe, no None keys
    assert None not in out.values()


INVALID = [
    ("table", {"columns": ["A"], "rows": [["x", "y"]]}),  # ragged
    ("table", {"columns": [], "rows": [["x"]]}),
    ("table", {"columns": ["A"], "rows": []}),
    ("table", {"columns": ["A"] * 13, "rows": [["x"] * 13]}),
    ("table", {"columns": ["A"], "rows": [[{"a": 1}]]}),
    ("table", {"columns": ["A"], "rows": [["x"]], "extra": 1}),
    (
        "chart",
        {"type": "donut", "labels": ["a"], "series": [{"name": "s", "values": [1]}]},
    ),
    (
        "chart",
        {"type": "bar", "labels": ["a", "b"], "series": [{"name": "s", "values": [1]}]},
    ),
    (
        "chart",
        {"type": "pie", "labels": ["a"], "series": [{"name": "s", "values": [-1]}]},
    ),
    (
        "chart",
        {
            "type": "pie",
            "labels": ["a"],
            "series": [{"name": "s", "values": [1]}, {"name": "t", "values": [1]}],
        },
    ),
    (
        "chart",
        {"type": "bar", "labels": ["a"], "series": [{"name": "s", "values": ["1"]}]},
    ),
    ("stats", {"items": []}),
    ("stats", {"items": [{"label": "a", "value": 1, "trend": "sideways"}]}),
    ("steps", {"items": [{"label": "a", "status": "paused"}]}),
    ("checklist", {"items": [{"label": "a", "checked": "yes"}]}),
    ("cards", {"items": [{"title": "t", "tags": ["x"] * 7}]}),
    ("callout", {"tone": "loud", "text": "x"}),
    ("tabs", {"tabs": []}),
    ("accordion", {"items": [{"title": "a"}]}),
    ("choices", {"options": ["one"]}),
    ("choices", {"options": ["a", "A"]}),
    ("choices", {"options": ["a", ""]}),
]


@pytest.mark.parametrize(("kind", "props"), INVALID)
def test_invalid_props_raise_readable_errors(kind, props):
    with pytest.raises(WidgetError) as exc:
        ok(kind, props)
    assert kind in str(exc.value) or "props" in str(exc.value)


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"kind": "video", "props": {}},
        {"kind": "table"},
        {"kind": "table", "props": []},
        {"kind": "table", "props": "x"},
        {"kind": "callout", "props": {"tone": "info", "text": "x"}, "title": 5},
        {"kind": "callout", "props": {"tone": "info", "text": "x"}, "title": "t" * 500},
    ],
)
def test_bad_envelopes(args):
    with pytest.raises(WidgetError):
        validate_present(args)


def test_caps_are_enforced():
    rows = [["x"]] * 101
    with pytest.raises(WidgetError):
        ok("table", {"columns": ["A"], "rows": rows})
    with pytest.raises(WidgetError):
        ok("callout", {"tone": "info", "text": "x" * 1001})
    with pytest.raises(WidgetError):
        ok("tabs", {"tabs": [{"label": "a", "text": "x" * 2001}]})


def test_non_finite_numbers_rejected():
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(WidgetError):
            ok(
                "chart",
                {
                    "type": "bar",
                    "labels": ["a"],
                    "series": [{"name": "s", "values": [bad]}],
                },
            )
        with pytest.raises(WidgetError):
            ok("stats", {"items": [{"label": "a", "value": bad}]})
