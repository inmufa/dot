import pytest
from backend.core.public_id import ALPHABET, EPOCH, new_public_id


def test_shape_and_alphabet():
    pid = new_public_id("S")
    assert len(pid) == 10
    assert pid[0] == "S"
    assert set(pid) <= set(ALPHABET)


def test_time_sortable():
    a = new_public_id("T", now=EPOCH + 60)
    b = new_public_id("T", now=EPOCH + 600)
    assert a[:6] < b[:6]


def test_bad_letter():
    with pytest.raises(ValueError, match="letter"):
        new_public_id("I")


def test_before_epoch_rejected():
    with pytest.raises(ValueError, match="range"):
        new_public_id("S", now=EPOCH - 120)


def test_upper_bound_rejected():
    with pytest.raises(ValueError, match="range"):
        new_public_id("S", now=EPOCH + 60 * 32**5)


def test_last_valid_minute_and_epoch_encoding():
    assert new_public_id("S", now=EPOCH)[1:6] == "00000"
    assert new_public_id("S", now=EPOCH + 60 * (32**5 - 1))[1:6] == "ZZZZZ"
