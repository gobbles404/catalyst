"""The discount curve: the rules of meaning, the retained arrays, and the reader."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.globals.discount_curve import discount_curve, factor_on

EPOCH = np.datetime64("1899-12-30")


def days(start: str, count: int) -> NDArray[np.datetime64]:
    return np.datetime64(start, "D") + np.arange(count).astype("timedelta64[D]")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def factors(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


THREE_DAYS = days("2026-09-11", 3)
THREE_FACTORS = factors(1.0, 0.9999, 0.9998)


# --- what is accepted -------------------------------------------------------


def test_a_valid_table_keeps_every_pair_aligned() -> None:
    curve = discount_curve(THREE_DAYS, THREE_FACTORS)
    assert (curve.dates == THREE_DAYS).all()
    assert curve.factors.tolist() == [1.0, 0.9999, 0.9998]
    assert curve.start_date == np.datetime64("2026-09-11")
    assert curve.max_date == np.datetime64("2026-09-13")


def test_consecutive_days_run_across_a_year_end_and_a_leap_day() -> None:
    count = 100  # 1 December 2027 to 9 March 2028, which holds 29 February 2028
    curve = discount_curve(days("2027-12-01", count), np.linspace(1.0, 0.99, count))
    assert curve.factors.size == count
    assert curve.max_date == np.datetime64("2028-03-09")


@pytest.mark.parametrize(
    "values",
    [factors(1.0, 0.9999, 0.9999), factors(1.0, 1.0, 1.0), factors(1.0)],
    ids=["a flat step", "all ones", "one row"],
)
def test_flat_and_one_row_curves_are_curves(values: NDArray[np.float64]) -> None:
    curve = discount_curve(days("2026-09-11", values.size), values)
    assert curve.factors.tolist() == values.tolist()


# --- what is rejected, with the row named as the sheet counts ---------------


@pytest.mark.parametrize(
    ("bad_dates", "message"),
    [
        (
            dates("2026-09-11", "2026-09-12", "2026-09-14"),
            "date row 3 is 2026-09-14, expected 2026-09-13, one day after the row above",
        ),
        (
            dates("2026-09-11", "2026-09-11", "2026-09-12"),
            "date row 2 is 2026-09-11, expected 2026-09-12, one day after the row above",
        ),
        (
            dates("2026-09-13", "2026-09-12", "2026-09-11"),
            "date row 2 is 2026-09-12, expected 2026-09-14, one day after the row above",
        ),
    ],
    ids=["a missing day", "a duplicate date", "reversed rows"],
)
def test_dates_are_neither_sorted_nor_filled(
    bad_dates: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        discount_curve(bad_dates, THREE_FACTORS)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            factors(0.98, 0.9),
            "discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date",
        ),
        (factors(1.0, 0.0), "discount_factor row 2 is 0.0, expected greater than 0"),
        (factors(1.0, 0.5, -0.5), "discount_factor row 3 is -0.5, expected greater than 0"),
        (factors(1.0, 1.0001), "discount_factor rises at row 2, from 1.0 to 1.0001"),
        (factors(1.0, 0.9998, 0.9999), "discount_factor rises at row 3, from 0.9998 to 0.9999"),
        (factors(1.0, float("nan")), "discount_factor row 2 is nan, expected a finite number"),
        (factors(1.0, float("inf")), "discount_factor row 2 is inf, expected a finite number"),
        (
            factors(1.0, 0.5, float("-inf")),
            "discount_factor row 3 is -inf, expected a finite number",
        ),
        (factors(float("nan"), 0.5), "discount_factor row 1 is nan, expected a finite number"),
    ],
    ids=[
        "first factor not one",
        "zero",
        "negative",
        "above one",
        "a rise",
        "nan",
        "inf",
        "-inf",
        "nan first",
    ],
)
def test_factors_are_neither_rescaled_nor_clipped(
    values: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        discount_curve(days("2026-09-11", values.size), values)
    assert str(failure.value) == message


# --- the general rules ------------------------------------------------------


@given(start=st.integers(61, 2958465 - 400), count=st.integers(1, 400), data=st.data())
def test_any_valid_table_keeps_pairing_and_length(
    start: int, count: int, data: st.DataObject
) -> None:
    steps = data.draw(st.lists(st.floats(0.0, 0.001), min_size=count - 1, max_size=count - 1))
    values = np.concatenate(([1.0], 1.0 - np.cumsum(steps)))
    table_dates = EPOCH + (start + np.arange(count)).astype("timedelta64[D]")
    curve = discount_curve(table_dates, values)
    assert curve.dates.size == curve.factors.size == count
    assert (curve.dates == table_dates).all()
    assert (curve.factors == values).all()


def test_the_curve_owns_its_arrays() -> None:
    table_dates, values = days("2026-09-11", 3), factors(1.0, 0.9999, 0.9998)
    curve = discount_curve(table_dates, values)
    values[1] = 0.5
    table_dates[1] = np.datetime64("2030-01-01")
    assert curve.factors.tolist() == [1.0, 0.9999, 0.9998]
    assert curve.dates[1] == np.datetime64("2026-09-12")
    assert not curve.factors.flags.writeable
    assert not curve.dates.flags.writeable
    with pytest.raises(ValueError):
        curve.factors[0] = 0.5


# --- the reader -------------------------------------------------------------


def test_the_reader_answers_for_each_day_the_curve_covers() -> None:
    curve = discount_curve(THREE_DAYS, THREE_FACTORS)
    assert factor_on(curve, np.datetime64("2026-09-11")) == 1.0
    assert factor_on(curve, np.datetime64("2026-09-12")) == 0.9999
    assert factor_on(curve, curve.max_date) == 0.9998


@pytest.mark.parametrize("day", ["2026-09-14", "2026-09-10", "2030-01-01"])
def test_the_reader_fails_outside_the_curve_naming_both_ends(day: str) -> None:
    curve = discount_curve(THREE_DAYS, THREE_FACTORS)
    with pytest.raises(ValueError) as failure:
        factor_on(curve, np.datetime64(day))
    assert str(failure.value) == (
        f"date is {day}, expected a date from 2026-09-11 to 2026-09-13, the curve's first and last"
    )


def test_a_one_row_curve_answers_for_its_start_alone() -> None:
    curve = discount_curve(days("2026-09-11", 1), factors(1.0))
    assert curve.start_date == curve.max_date
    assert factor_on(curve, curve.start_date) == 1.0
    with pytest.raises(ValueError):
        factor_on(curve, np.datetime64("2026-09-12"))
