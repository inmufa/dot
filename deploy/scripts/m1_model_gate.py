#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""M1 model gate: drive a running llama-server through scripted tool-call tasks and a
prefix-reuse probe, print markdown tables.

    uv run deploy/scripts/m1_model_gate.py --base-url http://127.0.0.1:8080/v1

Part 1: 20 single-step tasks. Each offers the Dot core tools and expects one specific
tool call whose arguments must parse as JSON, carry the required keys and match a
pattern. Part 2: a 10-turn conversation with a fixed prefix; per turn the prompt-eval
time and reused-token share come from the `timings` block of the response.
Exit code 0 only when both gates pass.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m1_gate_tasks import TASKS, TOOLS, Task

TASK_COUNT = 20
MIN_TURNS = 2
PASS_RATE = 0.90
REUSE_MIN = 0.80
SYSTEM = (
    "You are Dot, a coding agent. Use the provided tools to act. "
    "Call exactly one tool per reply when a tool is needed."
)


@dataclass
class TaskResult:
    task: Task
    reason: str
    called: str = ""
    latency_s: float = 0.0
    ok: bool = field(default=False, kw_only=True)


@dataclass
class Turn:
    index: int
    prompt_n: int
    prompt_ms: float
    cache_n: int

    @property
    def reuse(self) -> float:
        total = self.prompt_n + self.cache_n
        return self.cache_n / total if total else 0.0


@dataclass
class ProbeResult:
    turns: list[Turn] = field(default_factory=list)

    @property
    def later_reuse(self) -> float:
        later = [t.reuse for t in self.turns[1:]]
        return statistics.median(later) if later else 0.0

    @property
    def ok(self) -> bool:
        return len(self.turns) >= MIN_TURNS and self.later_reuse >= REUSE_MIN


def score_task(task: Task, message: dict[str, Any]) -> TaskResult:
    """Pure scoring of one assistant message against a task."""
    calls = message.get("tool_calls") or []
    if not calls:
        return TaskResult(task, "no tool call")
    fn = calls[0].get("function") or {}
    name = fn.get("name", "")
    if name != task.tool and name not in task.also:
        return TaskResult(task, f"wrong tool {name}", name)
    raw = fn.get("arguments")
    try:
        args = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        args = None
    if not isinstance(args, dict):
        return TaskResult(task, "arguments not a JSON object", name)
    schema = next(t for t in TOOLS if t["function"]["name"] == name)["function"]
    missing = [k for k in schema["parameters"]["required"] if k not in args]
    if missing:
        return TaskResult(task, f"missing {','.join(missing)}", name)
    if task.arg and not re.search(task.pattern, str(args.get(task.arg, "")), re.I):
        return TaskResult(task, f"{task.arg} does not match", name)
    return TaskResult(task, "ok", name, ok=True)


def pass_rate(results: list[TaskResult]) -> float:
    return sum(r.ok for r in results) / len(results) if results else 0.0


def post(
    base_url: str, body: dict[str, Any], key: str, timeout: float
) -> dict[str, Any]:
    req = urllib.request.Request(  # noqa: S310
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.load(resp)


# Dot's streamed defaults (settings.llm_*): Qwen thinking-mode sampling.
SAMPLING: dict[str, Any] = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "presence_penalty": 0.0,
}


def extra_body(args: argparse.Namespace) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "presence_penalty": args.presence_penalty,
    }
    if args.no_think:
        extra["chat_template_kwargs"] = {"enable_thinking": False}
    return extra


def run_tasks(
    base_url: str,
    model: str,
    key: str,
    timeout: float,
    extra: dict[str, Any] | None = None,
) -> list[TaskResult]:
    results = []
    for task in TASKS:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": task.prompt},
            ],
            "tools": TOOLS,
            **SAMPLING,
            "max_tokens": 2048,
            **(extra or {}),
        }
        start = time.monotonic()
        try:
            data = post(base_url, body, key, timeout)
            result = score_task(task, data["choices"][0]["message"])
        except (OSError, KeyError, ValueError) as exc:
            result = TaskResult(task, f"request failed: {exc}")
        result.latency_s = time.monotonic() - start
        results.append(result)
    return results


def run_probe(
    base_url: str, model: str, key: str, timeout: float, turns: int = 10
) -> ProbeResult:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
    probe = ProbeResult()
    for i in range(1, turns + 1):
        messages.append(
            {
                "role": "user",
                "content": f"Turn {i}: say a short sentence about step {i}.",
            }
        )
        body = {
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "temperature": 0,
            "max_tokens": 24,
            "cache_prompt": True,
        }
        data = post(base_url, body, key, timeout)
        t = data.get("timings") or {}
        probe.turns.append(
            Turn(
                i,
                int(t.get("prompt_n", 0)),
                float(t.get("prompt_ms", 0.0)),
                int(t.get("cache_n", 0)),
            )
        )
        reply = data["choices"][0]["message"].get("content") or "ok"
        messages.append({"role": "assistant", "content": reply})
    return probe


def render_tasks(results: list[TaskResult]) -> str:
    lines = ["| # | tool | prompt | called | result | s |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        mark = "pass" if r.ok else f"FAIL ({r.reason})"
        lines.append(
            f"| {i} | {r.task.tool} | {r.task.prompt[:48]} | {r.called or '-'} "
            f"| {mark} | {r.latency_s:.1f} |"
        )
    rate = pass_rate(results)
    verdict = "PASS" if rate >= PASS_RATE else "FAIL"
    lines.append(
        f"\nTool-call success: {rate:.0%} (gate {PASS_RATE:.0%}): **{verdict}**"
    )
    return "\n".join(lines)


def render_probe(probe: ProbeResult) -> str:
    lines = [
        "| turn | prompt tokens evaluated | prompt-eval ms | tokens reused | reuse |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {t.index} | {t.prompt_n} | {t.prompt_ms:.0f} | {t.cache_n} | {t.reuse:.0%} |"
        for t in probe.turns
    ]
    verdict = "PASS" if probe.ok else "FAIL"
    lines.append(
        f"\nMedian reuse, turns 2+: {probe.later_reuse:.0%} (gate {REUSE_MIN:.0%}): "
        f"**{verdict}**"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model", default="dot")
    ap.add_argument("--api-key", default="none")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--only", choices=["tasks", "probe"])
    ap.add_argument("--no-think", action="store_true", help="enable_thinking=false")
    ap.add_argument("--temperature", type=float, default=SAMPLING["temperature"])
    ap.add_argument("--top-p", type=float, default=SAMPLING["top_p"])
    ap.add_argument("--top-k", type=int, default=SAMPLING["top_k"])
    ap.add_argument(
        "--presence-penalty", type=float, default=SAMPLING["presence_penalty"]
    )
    args = ap.parse_args(argv)
    ok = True
    out = sys.stdout.write
    if args.only != "probe":
        results = run_tasks(
            args.base_url, args.model, args.api_key, args.timeout, extra_body(args)
        )
        out("## Tool-call tasks\n\n" + render_tasks(results) + "\n\n")
        ok &= pass_rate(results) >= PASS_RATE
    if args.only != "tasks":
        probe = run_probe(args.base_url, args.model, args.api_key, args.timeout)
        out("## Prefix reuse (10 turns)\n\n" + render_probe(probe) + "\n")
        ok &= probe.ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
