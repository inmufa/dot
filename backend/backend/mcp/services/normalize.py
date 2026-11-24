"""Untrusted MCP metadata -> safe tool names, descriptions and llama-friendly schemas.

Tool names, descriptions and schemas come from a third party. Names are reduced to
[a-zA-Z0-9_], descriptions lose control tags and newlines and are length-capped,
and schemas keep only the JSON-schema subset llama.cpp can build grammars from.
"""

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

from backend.core.text import strip_control_tags

MAX_NAME = 64
TOOL_DESC_CHARS = 300
PROP_DESC_CHARS = 120
MAX_SCHEMA_CHARS = 8_000
MAX_DEPTH = 6
MAX_PROPS = 40
MAX_ENUM = 50
_BAD_CHARS = re.compile(r"[^A-Za-z0-9_]")
_PROP_NAME = re.compile(r"^[A-Za-z0-9_.$@-]{1,64}$")
ENUM_STR_CHARS = 100
_REF = re.compile(r"^#/(\$defs|definitions)/([\w.-]+)$")
_KEEP = frozenset(
    {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "const",
        "description",
        "anyOf",
        "oneOf",
        "additionalProperties",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
    }
)
_TYPES = frozenset(
    {"string", "number", "integer", "boolean", "array", "object", "null"}
)


def slug(text: str) -> str:
    return _BAD_CHARS.sub("_", text) or "_"


def clean_text(text: object, limit: int) -> str:
    """One line, no control tags, capped."""
    line = " ".join(strip_control_tags(str(text or "")).split())
    return line if len(line) <= limit else line[: limit - 3] + "..."


def tool_name(server_slug: str, raw: str, taken: set[str]) -> str:
    """`mcp__<server>__<tool>`, at most 64 chars, unique within `taken`."""
    base = f"mcp__{server_slug}__{slug(raw)}"
    if len(base) > MAX_NAME:
        digest = hashlib.sha256(raw.encode()).hexdigest()[:6]
        base = f"{base[: MAX_NAME - 7]}_{digest}"
    name, n = base, 1
    while name in taken:
        n += 1
        suffix = f"_{n}"
        name = base[: MAX_NAME - len(suffix)] + suffix
    taken.add(name)
    return name


def server_slugs(names: list[str]) -> dict[str, str]:
    """Sanitised, de-duplicated server part for every configured name."""
    out: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        base, cand, n = slug(name), slug(name), 1
        while cand in used:
            n += 1
            cand = f"{base}_{n}"
        used.add(cand)
        out[name] = cand
    return out


class _Ctx:
    def __init__(self, root: dict[str, Any]) -> None:
        defs = {**root.get("definitions", {}), **root.get("$defs", {})}
        self.defs = defs if isinstance(defs, dict) else {}


def _types(raw: Any) -> Any:
    if isinstance(raw, str):
        return raw if raw in _TYPES else None
    if isinstance(raw, list):
        kept = [t for t in raw if t in _TYPES]
        return kept or None
    return None


def _merge_all_of(parts: list[Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for part in parts:
        if not isinstance(part, dict):
            continue
        merged["properties"].update(part.get("properties") or {})
        merged["required"] += [
            r for r in part.get("required") or [] if isinstance(r, str)
        ]
    return merged


def _scalar(v: Any) -> Any:
    return clean_text(v, ENUM_STR_CHARS) if isinstance(v, str) else v


Handler = Callable[[Any, "_Ctx", int], Any]


def _h_type(v: Any, _c: "_Ctx", _d: int) -> Any:
    return _types(v)


def _h_props(v: Any, c: "_Ctx", d: int) -> Any:
    if not isinstance(v, dict):
        return None
    items = [
        (k, x) for k, x in v.items() if isinstance(k, str) and _PROP_NAME.match(k)
    ][:MAX_PROPS]
    return {k: _node(x, c, d + 1) for k, x in items}


def _h_items(v: Any, c: "_Ctx", d: int) -> Any:
    return _node(v, c, d + 1)


def _h_any(v: Any, c: "_Ctx", d: int) -> Any:
    return [_node(x, c, d + 1) for x in v[:8]] if isinstance(v, list) else None


def _h_enum(v: Any, _c: "_Ctx", _d: int) -> Any:
    if not isinstance(v, list):
        return None
    return [_scalar(x) for x in v[:MAX_ENUM] if isinstance(x, str | int | float | bool)]


def _h_desc(v: Any, _c: "_Ctx", _d: int) -> Any:
    return clean_text(v, PROP_DESC_CHARS)


def _h_required(v: Any, _c: "_Ctx", _d: int) -> Any:
    return [r for r in v if isinstance(r, str)] if isinstance(v, list) else None


def _h_bool(v: Any, _c: "_Ctx", _d: int) -> Any:
    return v if isinstance(v, bool) else True


def _h_const(v: Any, _c: "_Ctx", _d: int) -> Any:
    return _scalar(v) if isinstance(v, str | int | float | bool) else None


def _h_number(v: Any, _c: "_Ctx", _d: int) -> Any:
    return v if isinstance(v, int | float) and not isinstance(v, bool) else None


_HANDLERS: dict[str, Handler] = {
    "type": _h_type,
    "properties": _h_props,
    "required": _h_required,
    "items": _h_items,
    "enum": _h_enum,
    "const": _h_const,
    "description": _h_desc,
    "anyOf": _h_any,
    "oneOf": _h_any,
    "additionalProperties": _h_bool,
    **dict.fromkeys(
        ("minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength"),
        _h_number,
    ),
}
assert set(_HANDLERS) == _KEEP  # noqa: S101


def _resolve(raw: dict[str, Any], ctx: "_Ctx", depth: int) -> dict[str, Any] | None:
    """Inline a local $ref / merge allOf; None means the node resolved to nothing."""
    ref = raw.get("$ref")
    if isinstance(ref, str):
        m = _REF.match(ref)
        target = ctx.defs.get(m.group(2)) if m else None
        return _node(target, ctx, depth + 1) if target is not None else {}
    if isinstance(raw.get("allOf"), list):
        rest = {k: v for k, v in raw.items() if k != "allOf"}
        return _plain({**rest, **_merge_all_of(raw["allOf"])}, ctx, depth)
    return None


def _plain(raw: dict[str, Any], ctx: "_Ctx", depth: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, handler in _HANDLERS.items():
        if key in raw and (val := handler(raw[key], ctx, depth)) is not None:
            out[key] = val
    if "oneOf" in out:  # llama grammars treat both as a union
        out.setdefault("anyOf", out.pop("oneOf"))
    have = out.get("properties") or {}
    if "required" in out:
        out["required"] = [r for r in out["required"] if r in have]
        if not out["required"]:
            del out["required"]
    return out


def _node(raw: Any, ctx: "_Ctx", depth: int) -> dict[str, Any]:
    if not isinstance(raw, dict) or depth > MAX_DEPTH:
        return {}
    resolved = _resolve(raw, ctx, depth)
    return resolved if resolved is not None else _plain(raw, ctx, depth)


def _strip_descriptions(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: _strip_descriptions(v)
            for k, v in node.items()
            if not (k == "description" and isinstance(v, str))
        }
    if isinstance(node, list):
        return [_strip_descriptions(v) for v in node]
    return node


def normalize_schema(raw: Any) -> dict[str, Any]:
    """A bounded object schema; anything unusable collapses to a free-form object."""
    if not isinstance(raw, dict):
        return {"type": "object", "properties": {}}
    schema = _node(raw, _Ctx(raw), 0)
    schema["type"] = "object"
    schema.setdefault("properties", {})
    if len(json.dumps(schema)) > MAX_SCHEMA_CHARS:
        schema = _strip_descriptions(schema)
    if len(json.dumps(schema)) > MAX_SCHEMA_CHARS:
        return {"type": "object", "additionalProperties": True}
    return schema
