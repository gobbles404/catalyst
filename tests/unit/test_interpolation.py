"""The interpolation: every day from the first anchor to the last, each anchor kept exactly, and
the days between two anchors on the straight line between their factors."""

import numpy as np
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.globals.interpolation import interpolate_discount_factors

EPOCH = np.datetime64("1899-12-30")
ONE_DAY = np.timedelta64(1, "D")

Anchors = tuple[NDArray[np.datetime64], NDArray[np.float64]]


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def factors(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# --- examples -----------------------------------------------------------------


# Quarters are exact in binary, so every point of this line can be asserted exactly.
def test_a_straight_line_over_four_days_hits_every_quarter() -> None:
    days, values = interpolate_discount_factors(
        dates("2026-09-11", "2026-09-15"), factors(1.0, 0.5)
    )
    assert np.array_equal(
        days, dates("2026-09-11", "2026-09-12", "2026-09-13", "2026-09-14", "2026-09-15")
    )
    assert values.tolist() == [1.0, 0.875, 0.75, 0.625, 0.5]


def test_daily_anchors_come_back_as_they_were() -> None:
    every = dates("2026-09-11", "2026-09-12", "2026-09-13")
    given_factors = factors(1.0, 0.9999, 0.9998)
    days, values = interpolate_discount_factors(every, given_factors)
    assert np.array_equal(days, every)
    assert values.tolist() == given_factors.tolist()


def test_a_gap_over_a_leap_day_is_filled_a_day_at_a_time() -> None:
    days, values = interpolate_discount_factors(
        dates("2028-02-27", "2028-03-02"), factors(1.0, 0.996)
    )
    assert np.array_equal(
        days, dates("2028-02-27", "2028-02-28", "2028-02-29", "2028-03-01", "2028-03-02")
    )
    assert values[0] == 1.0 and values[-1] == 0.996
    assert np.allclose(values, [1.0, 0.999, 0.998, 0.997, 0.996], rtol=0, atol=1e-15)


def test_equal_anchors_give_a_flat_line_exactly() -> None:
    _, values = interpolate_discount_factors(dates("2026-09-11", "2026-09-30"), factors(0.9, 0.9))
    assert values.size == 20
    assert (values == 0.9).all()


def test_one_anchor_is_one_day() -> None:
    days, values = interpolate_discount_factors(dates("2026-09-11"), factors(1.0))
    assert np.array_equal(days, dates("2026-09-11"))
    assert values.tolist() == [1.0]


def test_the_anchors_are_left_as_they_were() -> None:
    anchor_days, anchor_factors = dates("2026-09-11", "2026-09-20"), factors(1.0, 0.99)
    interpolate_discount_factors(anchor_days, anchor_factors)
    assert np.array_equal(anchor_days, dates("2026-09-11", "2026-09-20"))
    assert anchor_factors.tolist() == [1.0, 0.99]


# --- the general rules, over anchors as the curve's builder has checked them ------------


@st.composite
def anchors(draw: st.DrawFn) -> Anchors:
    """Strictly increasing dates inside the calendar, a day to about a year apart, and
    non-increasing factors from 1 down: what reaches the interpolation."""
    count = draw(st.integers(1, 12))
    start = draw(st.integers(61, 2958465 - 5000))
    gaps = draw(st.lists(st.integers(1, 400), min_size=count - 1, max_size=count - 1))
    offsets = np.concatenate(([0], np.cumsum(gaps, dtype=np.int64))).astype(np.int64)
    steps = draw(st.lists(st.floats(0.0, 0.01), min_size=count - 1, max_size=count - 1))
    values = np.concatenate(([1.0], 1.0 - np.cumsum(steps)))
    return EPOCH + (start + offsets).astype("timedelta64[D]"), values


@given(anchors())
def test_every_day_from_the_first_anchor_to_the_last_once(given_anchors: Anchors) -> None:
    anchor_days, anchor_factors = given_anchors
    days, values = interpolate_discount_factors(anchor_days, anchor_factors)
    assert days[0] == anchor_days[0]
    assert days[-1] == anchor_days[-1]
    assert days.size == values.size == int((anchor_days[-1] - anchor_days[0]) / ONE_DAY) + 1
    assert (np.diff(days) == ONE_DAY).all()


@given(anchors())
def test_every_anchor_keeps_its_factor_exactly(given_anchors: Anchors) -> None:
    anchor_days, anchor_factors = given_anchors
    _, values = interpolate_discount_factors(anchor_days, anchor_factors)
    at = ((anchor_days - anchor_days[0]) / ONE_DAY).astype(np.int64)
    assert values[at].tolist() == anchor_factors.tolist()


# Non-increasing anchors give non-increasing days; with every anchor kept exactly, that puts
# every day between two anchors between their factors.
@given(anchors())
def test_the_days_never_rise_so_every_day_lies_between_its_anchors(given_anchors: Anchors) -> None:
    anchor_days, anchor_factors = given_anchors
    _, values = interpolate_discount_factors(anchor_days, anchor_factors)
    assert (values[1:] <= values[:-1]).all()
    assert values.max() == anchor_factors[0]
    assert values.min() == anchor_factors[-1]
