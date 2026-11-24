from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from backend.scheduler.services import cron

UTC_TZ = ZoneInfo("UTC")


def at(y, mo, d, h=0, mi=0, tz=UTC) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=tz)


def nxt(expr: str, after: datetime, tz: str = "UTC") -> datetime:
    return cron.next_after(expr, after, ZoneInfo(tz))


@pytest.mark.parametrize(
    "expr",
    [
        "* * * * *",
        "*/5 * * * *",
        "0 9 * * 1-5",
        "0,30 8-18/2 * * *",
        "15 14 1 * *",
        "0 0 29 2 *",
        "5-10/2 * * jan,mar mon-fri",
        "0 0 * * 7",
        "@daily",
        "@HOURLY",
        "  0   12 * * *  ",
        "10/15 * * * *",
        "0 0 * * Sun",
    ],
)
def test_valid_expressions_parse(expr):
    cron.parse(expr)


@pytest.mark.parametrize(
    "expr",
    [
        "",
        "* * * *",
        "* * * * * *",
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * 32 * *",
        "* * * 13 *",
        "* * * * 8",
        "*/0 * * * *",
        "5-1 * * * *",
        "a * * * *",
        "1,,2 * * * *",
        "*/x * * * *",
        "? * * * *",
        "-1 * * * *",
        "1-2-3 * * * *",
        "@reboot",
        "L * * * *",
        "* * L * *",
        "* * 15W * *",
        "* * * * 5L",
        "* * * * 5#2",
        "²  * * * *",
        "*/² * * * *",
        "* * * foo *",
        "x" * 200,
    ],
)
def test_invalid_expressions_are_rejected(expr):
    with pytest.raises(cron.CronError):
        cron.parse(expr)


def test_non_string_is_rejected():
    with pytest.raises(cron.CronError):
        cron.parse(None)  # type: ignore[arg-type]


def test_next_is_strictly_after():
    assert nxt("* * * * *", at(2026, 3, 2, 12, 0)) == at(2026, 3, 2, 12, 1)
    assert nxt("0 12 * * *", at(2026, 3, 2, 12, 0)) == at(2026, 3, 3, 12, 0)
    assert nxt("0 12 * * *", at(2026, 3, 2, 11, 59, tz=UTC_TZ)) == at(2026, 3, 2, 12, 0)


def test_seconds_are_ignored_in_the_base_time():
    base = datetime(2026, 3, 2, 12, 0, 45, tzinfo=UTC)
    assert nxt("* * * * *", base) == at(2026, 3, 2, 12, 1)


def test_steps_lists_and_ranges():
    assert nxt("*/15 * * * *", at(2026, 3, 2, 12, 1)) == at(2026, 3, 2, 12, 15)
    assert nxt("5,50 * * * *", at(2026, 3, 2, 12, 6)) == at(2026, 3, 2, 12, 50)
    assert nxt("0 9-17/4 * * *", at(2026, 3, 2, 10, 0)) == at(2026, 3, 2, 13, 0)


def test_weekdays_and_names():
    # 2026-03-02 is a Monday; Saturday is 03-07.
    assert nxt("0 9 * * sat", at(2026, 3, 2, 12, 0)) == at(2026, 3, 7, 9, 0)
    assert nxt("0 9 * * 0", at(2026, 3, 2, 12, 0)) == at(2026, 3, 8, 9, 0)
    assert nxt("0 9 * * 7", at(2026, 3, 2, 12, 0)) == at(2026, 3, 8, 9, 0)
    assert nxt("0 0 1 jun *", at(2026, 3, 2)) == at(2026, 6, 1)


def test_dom_and_dow_are_ored_when_both_restricted():
    # the 5th OR any Friday
    got = [nxt("0 0 5 * fri", at(2026, 3, 2, 12))]
    got.append(nxt("0 0 5 * fri", got[0]))
    assert got == [at(2026, 3, 5), at(2026, 3, 6)]


def test_leap_day_and_month_end():
    assert nxt("0 0 29 2 *", at(2026, 3, 1)) == at(2028, 2, 29)
    assert nxt("0 0 31 * *", at(2026, 4, 1)) == at(2026, 5, 31)


def test_year_rollover_and_aliases():
    assert nxt("@yearly", at(2026, 12, 31, 23, 59)) == at(2027, 1, 1)
    assert nxt("@weekly", at(2026, 3, 2)) == at(2026, 3, 8)
    assert nxt("@monthly", at(2026, 3, 2)) == at(2026, 4, 1)


def test_never_firing_expression_errors():
    with pytest.raises(cron.CronError, match="never"):
        nxt("0 0 31 2 *", at(2026, 1, 1))


def test_time_zone_is_applied():
    # 09:00 Tashkent (UTC+5) is 04:00 UTC
    assert nxt("0 9 * * *", at(2026, 3, 2, 0), "Asia/Tashkent") == at(2026, 3, 2, 4)


BERLIN = ZoneInfo("Europe/Berlin")


def test_dst_spring_forward_gap_fires_once_shifted():
    # 2026-03-29: 02:00-03:00 does not exist in Berlin.
    first = nxt("30 2 * * *", at(2026, 3, 28, 12, tz=UTC_TZ), "Europe/Berlin")
    assert first.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M") == "2026-03-29 03:30"
    again = nxt("30 2 * * *", first, "Europe/Berlin")
    assert again.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M") == "2026-03-30 02:30"


def test_dst_fall_back_fires_once():
    # 2026-10-25: 02:00-03:00 happens twice in Berlin.
    first = nxt("30 2 * * *", at(2026, 10, 24, 12), "Europe/Berlin")
    assert first.astimezone(BERLIN).strftime("%H:%M %Z") == "02:30 CEST"
    second = nxt("30 2 * * *", first, "Europe/Berlin")
    assert second.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M") == "2026-10-26 02:30"


def test_hourly_across_fall_back_never_goes_backwards():
    after = at(2026, 10, 24, 20)
    seen = []
    for _ in range(8):
        after = nxt("0 * * * *", after, "Europe/Berlin")
        seen.append(after)
    assert seen == sorted(seen)
    assert len(set(seen)) == len(seen)


def test_daily_wall_clock_time_is_stable_across_dst():
    t = at(2026, 3, 27, 12)
    hours = set()
    for _ in range(5):
        t = nxt("0 8 * * *", t, "Europe/Berlin")
        hours.add(t.astimezone(BERLIN).hour)
    assert hours == {8}


def test_result_is_aware_utc():
    out = nxt("* * * * *", at(2026, 3, 2), "Europe/Berlin")
    assert out.utcoffset().total_seconds() == 0
    assert out.tzinfo is not None
    assert out == datetime(2026, 3, 2, 0, 1, tzinfo=UTC)
