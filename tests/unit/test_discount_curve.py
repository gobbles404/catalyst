"""The discount curve: the rules of meaning on the anchors, and the daily arrays the curve keeps."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.globals.discount_curve import discount_curve

EPOCH = np.datetime64("1899-12-30")
ONE_DAY = np.timedelta64(1, "D")


def days(start: str, count: int) -> NDArray[np.datetime64]:
    return np.datetime64(start, "D") + np.arange(count).astype("timedelta64[D]")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def factors(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


THREE_DAYS = days("2026-09-11", 3)
THREE_FACTORS = factors(1.0, 0.9999, 0.9998)

# The page's sample: the owner's eleven anchors, 22 May to 18 December 2026, as serials.
SAMPLE_SERIALS = [46164, 46165, 46166, 46171, 46178, 46194, 46254, 46284, 46314, 46344, 46374]
SAMPLE_FACTORS = factors(
    1.0, 0.9999, 0.9998, 0.99929, 0.99858, 0.99685, 0.99374, 0.99049, 0.9873, 0.98063, 0.97761
)
SAMPLE_DATES = EPOCH + np.array(SAMPLE_SERIALS).astype("timedelta64[D]")


# --- what is accepted -------------------------------------------------------


def test_a_daily_table_keeps_every_pair_aligned() -> None:
    curve = discount_curve(THREE_DAYS, THREE_FACTORS)
    assert (curve.dates == THREE_DAYS).all()
    assert curve.factors.tolist() == [1.0, 0.9999, 0.9998]
    assert curve.start_date == np.datetime64("2026-09-11")
    assert curve.max_date == np.datetime64("2026-09-13")


# Anchors two days apart: the day between takes the straight line, and the anchors stay exact.
def test_a_gap_between_anchors_is_filled_a_day_at_a_time() -> None:
    curve = discount_curve(dates("2026-09-11", "2026-09-12", "2026-09-14"), THREE_FACTORS)
    assert np.array_equal(curve.dates, days("2026-09-11", 4))
    assert curve.factors[[0, 1, 3]].tolist() == [1.0, 0.9999, 0.9998]
    assert abs(curve.factors[2] - 0.99985) < 1e-15


def test_the_pages_eleven_anchors_fill_two_hundred_and_eleven_days() -> None:
    curve = discount_curve(SAMPLE_DATES, SAMPLE_FACTORS)
    assert curve.dates.size == curve.factors.size == 211
    assert curve.start_date == np.datetime64("2026-05-22")
    assert curve.max_date == np.datetime64("2026-12-18")
    at = np.array(SAMPLE_SERIALS) - SAMPLE_SERIALS[0]
    assert curve.factors[at].tolist() == SAMPLE_FACTORS.tolist()
    assert (curve.factors[1:] <= curve.factors[:-1]).all()


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
            dates("2026-09-11", "2026-09-11", "2026-09-12"),
            "date row 2 is 2026-09-11, expected a date after row 1's 2026-09-11",
        ),
        (
            dates("2026-09-13", "2026-09-12", "2026-09-11"),
            "date row 2 is 2026-09-12, expected a date after row 1's 2026-09-13",
        ),
        (
            dates("2026-09-11", "2026-09-20", "2026-09-15"),
            "date row 3 is 2026-09-15, expected a date after row 2's 2026-09-20",
        ),
    ],
    ids=["a duplicate date", "reversed rows", "a step back after a gap"],
)
def test_dates_are_never_sorted(bad_dates: NDArray[np.datetime64], message: str) -> None:
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
def test_any_daily_table_keeps_pairing_and_length(
    start: int, count: int, data: st.DataObject
) -> None:
    steps = data.draw(st.lists(st.floats(0.0, 0.001), min_size=count - 1, max_size=count - 1))
    values = np.concatenate(([1.0], 1.0 - np.cumsum(steps)))
    table_dates = EPOCH + (start + np.arange(count)).astype("timedelta64[D]")
    curve = discount_curve(table_dates, values)
    assert curve.dates.size == curve.factors.size == count
    assert (curve.dates == table_dates).all()
    assert (curve.factors == values).all()


@given(start=st.integers(61, 2958465 - 5000), count=st.integers(1, 12), data=st.data())
def test_any_anchors_give_one_day_per_calendar_day_with_every_anchor_kept(
    start: int, count: int, data: st.DataObject
) -> None:
    gaps = data.draw(st.lists(st.integers(1, 400), min_size=count - 1, max_size=count - 1))
    offsets = np.concatenate(([0], np.cumsum(gaps, dtype=np.int64))).astype(np.int64)
    steps = data.draw(st.lists(st.floats(0.0, 0.01), min_size=count - 1, max_size=count - 1))
    values = np.concatenate(([1.0], 1.0 - np.cumsum(steps)))
    anchor_dates = EPOCH + (start + offsets).astype("timedelta64[D]")
    curve = discount_curve(anchor_dates, values)
    assert curve.dates.size == curve.factors.size == int(offsets[-1]) + 1
    assert (np.diff(curve.dates) == ONE_DAY).all()
    assert curve.factors[offsets].tolist() == values.tolist()


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


def test_a_one_row_curve_starts_and_ends_on_its_one_day() -> None:
    curve = discount_curve(days("2026-09-11", 1), factors(1.0))
    assert curve.start_date == curve.max_date == np.datetime64("2026-09-11")
