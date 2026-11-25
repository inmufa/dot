#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""E0 effort gate: does Qwen3.5 render distinct reasoning-effort levels, and what do
the Dot effort profiles cost in latency and tokens?

    uv run deploy/scripts/e0_effort_gate.py --base-url http://127.0.0.1:8080/v1

Part 1 reads chat_template_caps.reasoning_effort_levels from /props.
Part 2 sends fixed prompts per mode: Dot profiles (thinking flag and max_tokens as the
backend sends them) and, when the template reports levels, native reasoning_effort.
Prints a markdown table (seconds, completion tokens, reasoning chars). Run it only
when the GPU is free; it sends a few dozen short requests.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from typing import Any

PROMPTS = [
    "What is 17 * 23? Answer with the number only.",
    "Write a Python one-liner that reverses a string, then say why it works.",
    (
        "A bat and a ball cost 1.10 total; the bat costs 1.00 more than the ball. "
        "What does the ball cost? Explain briefly."
    ),
]
PROFILES: dict[str, dict[str, Any]] = {
    "off": {"chat_template_kwargs": {"enable_thinking": False}, "max_tokens": 2048},
    "low": {"chat_template_kwargs": {"enable_thinking": True}, "max_tokens": 3072},
    "medium": {},
    "high": {"chat_template_kwargs": {"enable_thinking": True}, "max_tokens": 12000},
    "max": {"chat_template_kwargs": {"enable_thinking": True}, "max_tokens": 20000},
}


def post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(  # noqa: S310
        url, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310
        return json.loads(r.read())


def props(root: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"{root}/props", timeout=10) as r:  # noqa: S310
            return json.loads(r.read())
    except (urllib.error.URLError, ValueError):
        return {}


def run(base: str, prompt: str, extra: dict[str, Any]) -> tuple[float, int, int, str]:
    body = {
        "model": "dot",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "cache_prompt": False,
        **extra,
    }
    t0 = time.monotonic()
    data = post(f"{base}/chat/completions", body)
    secs = time.monotonic() - t0
    msg = data["choices"][0]["message"]
    reasoning = msg.get("reasoning_content") or ""
    toks = (data.get("usage") or {}).get("completion_tokens", 0)
    return secs, toks, len(reasoning), (msg.get("content") or "")[:60]


def row(label: str, base: str, extra: dict[str, Any]) -> None:
    runs = [run(base, p, extra) for p in PROMPTS]
    secs = statistics.mean(r[0] for r in runs)
    toks = statistics.mean(r[1] for r in runs)
    chars = statistics.mean(r[2] for r in runs)
    print(f"| {label} | {secs:.1f} | {toks:.0f} | {chars:.0f} |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    base = ap.parse_args().base_url.rstrip("/")
    caps = (props(base.removesuffix("/v1")).get("chat_template_caps")) or {}
    levels = caps.get("reasoning_effort_levels") or []
    print(f"reasoning_effort_levels from /props: {levels or 'none'}\n")
    print("| mode | mean s | mean completion tokens | mean reasoning chars |")
    print("|---|---|---|---|")
    for name, extra in PROFILES.items():
        row(f"dot {name}", base, extra)
    for level in levels:
        row(f"native {level}", base, {"reasoning_effort": level})
    row("native none", base, {"reasoning_effort": "none"})


if __name__ == "__main__":
    main()
