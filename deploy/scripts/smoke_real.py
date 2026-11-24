#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Opt-in smoke test against the REAL model through Dot's public API (never run in CI).

    DOT_API_TOKEN=... uv run deploy/scripts/smoke_real.py -n 10

Runs "Run echo hi in the shell and then tell me in one sentence what it printed" N
times in bypass mode on fresh sessions and reports how many ended with an empty
visible answer (the stored final assistant message), how many needed the engine's
nudge or the reasoning fallback, and turn latency. Exit 1 above --max-empty (10%).
Needs the stack up (`make up`); each run costs a few seconds of GPU time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

PROMPT = "Run echo hi in the shell and then tell me in one sentence what it printed"


@dataclass
class Run:
    answer: str
    promoted: bool
    nudged: bool
    called_bash: bool
    seconds: float

    @property
    def empty(self) -> bool:
        return not self.answer.strip()


def call(url: str, token: str, method: str, body: Any = None, timeout: float = 300):
    req = urllib.request.Request(  # noqa: S310
        url,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310


def one_run(base: str, token: str, message: str) -> Run:
    sid = json.load(call(f"{base}/v1/sessions", token, "POST", {"mode": "bypass"}))[
        "id"
    ]
    start = time.monotonic()
    with call(
        f"{base}/v1/sessions/{sid}/chat", token, "POST", {"message": message}
    ) as r:
        r.read()  # the SSE stream ends with the done event
    seconds = time.monotonic() - start
    msgs = json.load(call(f"{base}/v1/sessions/{sid}/messages", token, "GET"))
    final = next((m for m in reversed(msgs) if m["role"] == "assistant"), None)
    return Run(
        answer=(final or {}).get("content", ""),
        promoted=bool(((final or {}).get("meta") or {}).get("reasoning_promoted")),
        nudged=any(
            m["role"] == "user" and "no visible answer" in m["content"] for m in msgs
        ),
        called_bash=any(
            c["function"]["name"] == "Bash"
            for m in msgs
            for c in m.get("tool_calls") or []
        ),
        seconds=seconds,
    )


def render(runs: list[Run]) -> str:
    n = len(runs)
    count = lambda pred: sum(1 for r in runs if pred(r))  # noqa: E731
    lines = [
        f"runs: {n}",
        f"empty final answer: {count(lambda r: r.empty)}/{n}",
        f"nudged (retry used): {count(lambda r: r.nudged)}/{n}",
        f"reasoning promoted: {count(lambda r: r.promoted)}/{n}",
        f"Bash called: {count(lambda r: r.called_bash)}/{n}",
        f"mean turn time: {sum(r.seconds for r in runs) / n:.1f}s",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument("--url", default=os.environ.get("DOT_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--max-empty", type=float, default=0.10)
    ap.add_argument("--message", default=PROMPT)
    args = ap.parse_args(argv)
    token = os.environ.get("DOT_API_TOKEN", "")
    if not token:
        sys.stderr.write("set DOT_API_TOKEN\n")
        return 2
    runs = []
    for i in range(args.n):
        runs.append(one_run(args.url.rstrip("/"), token, args.message))
        sys.stdout.write(f"run {i + 1}: {runs[-1].answer.strip()[:70]!r}\n")
        sys.stdout.flush()
    sys.stdout.write(render(runs) + "\n")
    rate = sum(r.empty for r in runs) / len(runs)
    return 0 if rate <= args.max_empty else 1


if __name__ == "__main__":
    sys.exit(main())
