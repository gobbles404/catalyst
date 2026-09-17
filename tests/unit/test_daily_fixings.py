"""The daily fixings: the one rule of meaning, and the columns retained and aligned."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.market_data.daily_fixings import daily_fixings

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def settles(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# The page's sample: four days of May 2026, a weekend between the first two, and their settles.
DATES = dates("2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06")
SETTLES = settles(101.94, 106.42, 102.27, 95.08)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_date_and_settle_aligned() -> None:
    fixings = daily_fixings(DATES, SETTLES)
    assert np.array_equal(fixings.dates, DATES)
    assert fixings.settles.tolist() == [101.94, 106.42, 102.27, 95.08]
    assert fixings.dates.dtype == np.dtype("datetime64[D]")
    assert fixings.settles.dtype == np.dtype("float64")


def test_one_fixing_is_a_series() -> None:
    fixings = daily_fixings(DATES[:1], SETTLES[:1])
    assert np.array_equal(fixings.dates, DATES[:1])
    assert fixings.settles.tolist() == [101.94]


# A settle at or below zero, and gaps of any length between the days: kept as given. WTI's May
# 2020 contract settled at minus 37.63 on 20 April 2020.
def test_nothing_else_is_checked() -> None:
    fixings = daily_fixings(
        dates("2020-04-20", "2020-04-21", "2020-06-30"), settles(-37.63, 0.0, 39.27)
    )
    assert fixings.settles.tolist() == [-37.63, 0.0, 39.27]
    assert np.array_equal(fixings.dates, dates("2020-04-20", "2020-04-21", "2020-06-30"))


# --- what is rejected, naming the row -----------------------------------------


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (
            dates("2026-05-04", "2026-05-01", "2026-05-05", "2026-05-06"),
            "date row 2 is 2026-05-01, expected a date after row 1's 2026-05-04",
        ),
        (
            dates("2026-05-01", "2026-05-04", "2026-05-04", "2026-05-06"),
            "date row 3 is 2026-05-04, expected a date after row 2's 2026-05-04",
        ),
        (
            dates("2026-05-06", "2026-05-05", "2026-05-04", "2026-05-01"),
            "date row 2 is 2026-05-05, expected a date after row 1's 2026-05-06",
        ),
    ],
    ids=["two dates swapped", "a date twice", "newest first"],
)
def test_a_date_not_after_the_row_above_is_rejected(
    given: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        daily_fixings(given, SETTLES)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_increasing_dates_and_their_settles_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    gaps = data.draw(st.lists(st.integers(1, 10), min_size=count - 1, max_size=count - 1))
    offsets = np.concatenate(([0], np.cumsum(gaps, dtype=np.int64))).astype(np.int64)
    start = data.draw(st.integers(61, 2958465 - 5000))
    given_dates = EPOCH + (start + offsets).astype("timedelta64[D]")
    given_settles = np.array(
        data.draw(st.lists(st.floats(-1e6, 1e6), min_size=count, max_size=count)), dtype=np.float64
    )
    fixings = daily_fixings(given_dates, given_settles)
    assert np.array_equal(fixings.dates, given_dates)
    assert np.array_equal(fixings.settles, given_settles)


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_columns() -> None:
    given_dates, given_settles = DATES.copy(), SETTLES.copy()
    fixings = daily_fixings(given_dates, given_settles)
    given_dates[0] = np.datetime64("2030-01-01")
    given_settles[0] = 0.0
    assert fixings.dates[0] == np.datetime64("2026-05-01")
    assert fixings.settles[0] == 101.94
    assert not fixings.dates.flags.writeable
    assert not fixings.settles.flags.writeable
    with pytest.raises(ValueError):
        fixings.settles[0] = 0.0
