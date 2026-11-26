"""5-field cron parser and next-run search (stdlib only, DST-aware).

Day-of-month and day-of-week combine with OR when both are restricted (classic
cron). DST: a skipped wall time fires once, shifted forward; a repeated one
fires once, on its first occurrence.
"""

import calendar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

MAX_LEN = 100
MAX_DAYS = 366 * 8  # a Feb 29 job is at most 8 years away
_ALIASES = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}
_MONTHS = {n.lower(): i for i, n in enumerate(calendar.month_abbr) if n}
_DAYS = {n.lower(): i for i, n in enumerate(["Sun", *calendar.day_abbr[:6]])}
_DAYS["sun"] = 0


class CronError(ValueError):
    """The expression is not valid 5-field cron."""


@dataclass(frozen=True)
class CronSpec:
    minutes: tuple[int, ...]
    hours: tuple[int, ...]
    doms: frozenset[int]
    months: frozenset[int]
    dows: frozenset[int]
    dom_any: bool
    dow_any: bool

    def day_matches(self, day: datetime) -> bool:
        dom_ok = day.day in self.doms
        dow_ok = (day.isoweekday() % 7) in self.dows
        if self.dom_any and self.dow_any:
            return True
        if self.dom_any:
            return dow_ok
        if self.dow_any:
            return dom_ok
        return dom_ok or dow_ok


def _number(text: str, names: dict[str, int], low: int, high: int) -> int:
    if text.isascii() and text.isdigit():
        value = int(text)
    elif text.lower() in names:
        value = names[text.lower()]
    else:
        msg = f"bad value {text[:20]!r}"
        raise CronError(msg)
    if not low <= value <= high:
        msg = f"{value} is outside {low}-{high}"
        raise CronError(msg)
    return value


def _part(part: str, names: dict[str, int], low: int, high: int) -> set[int]:
    body, _, step_text = part.partition("/")
    if "/" in part and not (step_text.isascii() and step_text.isdigit()):
        msg = "bad step"
        raise CronError(msg)
    step = int(step_text) if step_text else 1
    if step < 1:
        msg = "step must be at least 1"
        raise CronError(msg)
    if body == "*":
        start, end = low, high
    elif "-" in body:
        a, _, b = body.partition("-")
        start, end = _number(a, names, low, high), _number(b, names, low, high)
        if start > end:
            msg = f"range {body} is backwards"
            raise CronError(msg)
    else:
        start = _number(body, names, low, high)
        end = high if step_text else start
    return set(range(start, end + 1, step))


def _field(
    text: str, names: dict[str, int], low: int, high: int
) -> tuple[set[int], bool]:
    values: set[int] = set()
    for part in text.split(","):
        if not part:
            msg = "empty list item"
            raise CronError(msg)
        values |= _part(part, names, low, high)
    return values, text.startswith("*")


def parse(expr: str) -> CronSpec:
    if not isinstance(expr, str) or len(expr) > MAX_LEN:
        msg = "expression too long"
        raise CronError(msg)
    text = _ALIASES.get(expr.strip().lower(), expr)
    fields = text.split()
    if len(fields) != 5:  # noqa: PLR2004
        msg = "expected 5 fields: minute hour day month weekday"
        raise CronError(msg)
    minute, _ = _field(fields[0], {}, 0, 59)
    hour, _ = _field(fields[1], {}, 0, 23)
    dom, dom_any = _field(fields[2], {}, 1, 31)
    month, _ = _field(fields[3], _MONTHS, 1, 12)
    dow, dow_any = _field(fields[4], _DAYS, 0, 7)
    return CronSpec(
        tuple(sorted(minute)),
        tuple(sorted(hour)),
        frozenset(dom),
        frozenset(month),
        frozenset(d % 7 for d in dow),
        dom_any,
        dow_any,
    )


def _instant(naive: datetime, tz: ZoneInfo) -> datetime:
    """Wall time -> UTC instant (fold=0: a gap shifts forward, a repeat fires first)."""
    return naive.replace(tzinfo=tz).astimezone(UTC)


def next_after(expr: str | CronSpec, after: datetime, tz: ZoneInfo) -> datetime:
    """First fire time strictly after `after` (aware), as an aware UTC datetime."""
    spec = parse(expr) if isinstance(expr, str) else expr
    start = after.astimezone(tz).replace(second=0, microsecond=0, tzinfo=None)
    start += timedelta(minutes=1)
    # Back one day: a fall-back repeat can make an earlier wall time later in UTC.
    first_day = (start - timedelta(days=1)).replace(hour=0, minute=0)
    for k in range(MAX_DAYS + 1):
        day = first_day + timedelta(days=k)
        if day.month not in spec.months or not spec.day_matches(day):
            continue
        for hour in spec.hours:
            for minute in spec.minutes:
                inst = _instant(day.replace(hour=hour, minute=minute), tz)
                if inst > after:
                    return inst
    msg = "expression never fires"
    raise CronError(msg)
