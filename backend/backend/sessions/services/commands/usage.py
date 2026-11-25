"""Aggregate per-turn usage records (assistant row meta["usage"]) for /usage."""

from dot_contracts.ui.telemetry import UsageOut

from backend.sessions.models import Message


def aggregate(rows: list[Message], context: int, limit: int) -> UsageOut:
    prompt = completion = steps = 0
    speeds: list[float] = []
    efforts: dict[str, int] = {}
    last_ms = None
    last_at = None
    turns = sum(1 for r in rows if r.role == "user")
    for r in rows:
        u = (r.meta or {}).get("usage") if r.role == "assistant" else None
        if not isinstance(u, dict):
            continue
        steps += 1
        prompt += int(u.get("prompt_tokens") or 0)
        done = int(u.get("completion_tokens") or 0)
        completion += done
        ms = u.get("duration_ms")
        if isinstance(ms, int | float) and ms > 0:
            last_ms, last_at = int(ms), r.created_at
            if done:
                speeds.append(done / (ms / 1000))
        if level := u.get("effort"):
            efforts[str(level)] = efforts.get(str(level), 0) + 1
    return UsageOut(
        turns=turns,
        prompt_tokens=prompt,
        completion_tokens=completion,
        context_tokens=context,
        context_limit=limit,
        tokens_per_s=round(sum(speeds) / len(speeds), 1) if speeds else None,
        last_turn_ms=last_ms,
        last_turn_at=last_at,
        efforts=efforts,
    )
