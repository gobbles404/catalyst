"""The valuation date: both values kept exactly, and the fraction checked once."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from catalyst.globals.valuation_date import ValuationDate, valuation_date

FRIDAY = np.datetime64("2026-09-11")
EPOCH = np.datetime64("1899-12-30")


@pytest.mark.parametrize("fraction", [0.0, 0.5, 1.0])
def test_an_accepted_fraction_keeps_both_values(fraction: float) -> None:
    made = valuation_date(FRIDAY, fraction)
    assert made.as_of == FRIDAY
    assert made.day_fraction_elapsed == fraction


@pytest.mark.parametrize(
    "fraction",
    [
        -1.0,
        2.0,
        float(np.nextafter(0.0, -np.inf)),
        float(np.nextafter(1.0, np.inf)),
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_a_rejected_fraction_is_not_clamped(fraction: float) -> None:
    with pytest.raises(ValueError, match=r"^day_fraction_elapsed is number .*, expected a number"):
        valuation_date(FRIDAY, fraction)


def test_the_message_names_the_value() -> None:
    with pytest.raises(ValueError) as failure:
        valuation_date(FRIDAY, 1.5)
    assert str(failure.value) == (
        "day_fraction_elapsed is number 1.5, expected a number from 0 to 1"
    )


@given(serial=st.integers(61, 2958465), fraction=st.floats(0.0, 1.0))
def test_any_valid_date_and_fraction_are_preserved(serial: int, fraction: float) -> None:
    day = EPOCH + np.timedelta64(serial, "D")
    made = valuation_date(day, fraction)
    assert made.as_of == day
    assert made.day_fraction_elapsed == fraction


@given(
    fraction=st.floats(allow_nan=False, allow_infinity=False).filter(lambda f: not 0.0 <= f <= 1.0)
)
def test_any_finite_fraction_outside_the_interval_fails(fraction: float) -> None:
    with pytest.raises(ValueError):
        valuation_date(FRIDAY, fraction)


# A Saturday, a Sunday, a leap day, a year end, and the last day Excel can show.
@pytest.mark.parametrize(
    "day", ["2026-09-12", "2026-09-13", "2028-02-29", "2026-12-31", "9999-12-31"]
)
def test_a_fraction_of_one_keeps_the_date(day: str) -> None:
    made = valuation_date(np.datetime64(day), 1.0)
    assert made.as_of == np.datetime64(day)


def test_the_end_of_friday_and_the_start_of_saturday_are_different_records() -> None:
    end_of_friday = valuation_date(FRIDAY, 1.0)
    start_of_saturday = valuation_date(np.datetime64("2026-09-12"), 0.0)
    assert end_of_friday != start_of_saturday
    assert end_of_friday == ValuationDate(FRIDAY, 1.0)
