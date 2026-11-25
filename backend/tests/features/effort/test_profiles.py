import pytest
from backend.cognition.services.engine.effort.profiles import (
    PROFILES,
    build_state,
    effective,
    has_ultrathink,
)
from dot_contracts.ui.effort import Effort


@pytest.mark.parametrize(
    ("text", "hit"),
    [
        ("ultrathink about this", True),
        ("please ULTRATHINK.", True),
        ("Ultrathink", True),
        ("ultrathinking", False),
        ("super-ultrathinker", False),
        ("see `ultrathink` in docs", False),
        ("```\nultrathink\n```", False),
        ("> ultrathink quoted", False),
        ("ultra think", False),
        ("", False),
    ],
)
def test_ultrathink_detection(text, hit):
    assert has_ultrathink(text) is hit


def test_ultrathink_raises_to_max_and_voice_wins():
    assert effective(Effort.LOW, "ultrathink", voice=False) == (Effort.MAX, True)
    assert effective(Effort.HIGH, "hi", voice=False) == (Effort.HIGH, False)
    assert effective(Effort.MAX, "ultrathink", voice=True) == (Effort.OFF, False)


def test_mapping_table():
    off = build_state(Effort.OFF, Effort.OFF, ultrathink=False, native_levels=[])
    assert off.options.thinking is False
    assert off.options.max_tokens == PROFILES[Effort.OFF].max_tokens
    med = build_state(Effort.MEDIUM, Effort.MEDIUM, ultrathink=False, native_levels=[])
    assert med.options.thinking is None
    assert med.options.max_tokens is None
    assert med.profile.hint == ""
    low = build_state(Effort.LOW, Effort.LOW, ultrathink=False, native_levels=[])
    high = build_state(Effort.HIGH, Effort.HIGH, ultrathink=False, native_levels=[])
    mx = build_state(Effort.MAX, Effort.MAX, ultrathink=True, native_levels=[])
    assert low.options.max_tokens < high.options.max_tokens < mx.options.max_tokens
    assert mx.profile.verify
    assert not high.profile.verify
    assert mx.info.ultrathink


def test_native_levels_pass_through():
    s = build_state(Effort.HIGH, Effort.HIGH, ultrathink=False, native_levels=["high"])
    assert s.options.reasoning_effort == "high"
    assert s.info.native
    s = build_state(Effort.LOW, Effort.LOW, ultrathink=False, native_levels=["high"])
    assert s.options.reasoning_effort is None
    assert not s.info.native
