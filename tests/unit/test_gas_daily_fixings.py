"""The Gas Daily fixings: two rules of meaning, and the flow days and prices retained."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.market_data.gas_daily_fixings import gas_daily_fixings

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# The page's sample: Henry Hub Gas Daily over Labor Day week 2026, Friday 4 September's print
# covering Saturday 5 to Tuesday 8, the four rows carrying one number.
DAYS = dates("2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08", "2026-09-09")
PRICES = prices(2.930, 2.875, 2.875, 2.875, 2.875, 2.900)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_day_and_every_price_aligned() -> None:
    fixings = gas_daily_fixings(DAYS, PRICES)
    assert np.array_equal(fixings.dates, DAYS)
    assert np.array_equal(fixings.prices, PRICES)
    assert fixings.dates.dtype == np.dtype("datetime64[D]")
    assert fixings.prices.dtype == np.dtype(np.float64)
    assert fixings.dates.ndim == fixings.prices.ndim == 1
    # The weekend and the holiday are rows like any other, carrying Friday's number.
    assert fixings.prices[1:5].tolist() == [2.875] * 4


def test_the_fixings_of_one_day_are_a_series() -> None:
    fixings = gas_daily_fixings(DAYS[:1], PRICES[:1])
    assert np.array_equal(fixings.dates, dates("2026-09-04"))
    assert np.array_equal(fixings.prices, prices(2.930))


def test_a_whole_month_is_kept_in_its_order() -> None:
    days = np.arange("2026-09-01", "2026-10-01", dtype="datetime64[D]")
    given_prices = prices(*(2.8 + i / 100 for i in range(30)))
    fixings = gas_daily_fixings(days, given_prices)
    assert fixings.dates.size == 30
    assert np.array_equal(fixings.dates, days)
    assert np.array_equal(fixings.prices, given_prices)


def test_a_price_below_zero_and_a_zero_are_kept_as_given() -> None:
    fixings = gas_daily_fixings(DAYS[:3], prices(-1.25, 0.0, 1.95))
    assert np.array_equal(fixings.prices, prices(-1.25, 0.0, 1.95))


# A run across a month end and one across a year end: no month or year is looked at.
def test_a_run_across_a_month_end_and_a_year_end_is_kept_as_given() -> None:
    month_end = dates("2026-09-30", "2026-10-01", "2026-10-02")
    assert np.array_equal(gas_daily_fixings(month_end, PRICES[:3]).dates, month_end)
    year_end = dates("2026-12-31", "2027-01-01", "2027-01-02")
    assert np.array_equal(gas_daily_fixings(year_end, PRICES[:3]).dates, year_end)


# --- what is rejected ---------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "given_prices", "message"),
    [
        (DAYS, PRICES[:5], "price has 5 prices, expected 6, one per flow_date"),
        (
            DAYS,
            np.append(PRICES, 2.9),
            "price has 7 prices, expected 6, one per flow_date",
        ),
        (DAYS, PRICES[:1], "price has 1 price, expected 6, one per flow_date"),
        (DAYS[:1], PRICES, "price has 6 prices, expected 1, one per flow_date"),
        (
            dates("2026-09-04", "2026-09-05", "2026-09-05", "2026-09-06"),
            PRICES[:4],
            "flow_date row 3 is 2026-09-05, expected 2026-09-06, the day after row 2's 2026-09-05",
        ),
        (
            dates("2026-09-04", "2026-09-05", "2026-09-07"),
            PRICES[:3],
            "flow_date row 3 is 2026-09-07, expected 2026-09-06, the day after row 2's 2026-09-05",
        ),
        (
            dates("2026-09-04", "2026-09-07"),
            PRICES[:2],
            "flow_date row 2 is 2026-09-07, expected 2026-09-05, the day after row 1's 2026-09-04",
        ),
        (
            dates("2026-09-09", "2026-09-08", "2026-09-07"),
            PRICES[:3],
            "flow_date row 2 is 2026-09-08, expected 2026-09-10, the day after row 1's 2026-09-09",
        ),
        (
            dates("2026-09-04", "2026-09-06", "2026-09-05", "2026-09-07"),
            PRICES[:4],
            "flow_date row 2 is 2026-09-06, expected 2026-09-05, the day after row 1's 2026-09-04",
        ),
        (
            dates("2026-09-04", "2026-09-06"),
            PRICES[:3],
            "price has 3 prices, expected 2, one per flow_date",
        ),
    ],
    ids=[
        "a price column one row short",
        "a price column one row long",
        "one price for six days",
        "six prices for one day",
        "a day given twice",
        "a day skipped",
        "two days skipped",
        "a series pasted newest first",
        "two days swapped in the middle",
        "a day skipped and the count wrong, the count named first",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    days: NDArray[np.datetime64], given_prices: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        gas_daily_fixings(days, given_prices)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(first=st.integers(61, 2958000), count=st.integers(1, 400), data=st.data())
def test_any_run_of_consecutive_days_with_one_price_each_is_kept_aligned(
    first: int, count: int, data: st.DataObject
) -> None:
    days = EPOCH + (first + np.arange(count)).astype("timedelta64[D]")
    given_prices = np.array(
        data.draw(
            st.lists(
                st.floats(-100, 100, allow_nan=False, allow_infinity=False),
                min_size=count,
                max_size=count,
            )
        ),
        dtype=np.float64,
    )
    fixings = gas_daily_fixings(days, given_prices)
    assert np.array_equal(fixings.dates, days)
    assert np.array_equal(fixings.prices, given_prices)


# With one day left out of a run, the row after the gap is refused, naming the day expected.
@given(first=st.integers(61, 2958000), count=st.integers(3, 60), data=st.data())
def test_a_day_left_out_of_a_run_is_refused_at_the_row_after_the_gap(
    first: int, count: int, data: st.DataObject
) -> None:
    left_out = data.draw(st.integers(1, count - 2))
    days = EPOCH + (first + np.arange(count)).astype("timedelta64[D]")
    days = np.delete(days, left_out)
    with pytest.raises(ValueError) as failure:
        gas_daily_fixings(days, np.zeros(days.size))
    expected = EPOCH + np.timedelta64(first + left_out, "D")
    before = EPOCH + np.timedelta64(first + left_out - 1, "D")
    after = EPOCH + np.timedelta64(first + left_out + 1, "D")
    assert str(failure.value) == (
        f"flow_date row {left_out + 1} is {after}, expected {expected}, "
        f"the day after row {left_out}'s {before}"
    )


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_columns() -> None:
    days, given_prices = DAYS.copy(), PRICES.copy()
    fixings = gas_daily_fixings(days, given_prices)
    days[0] = np.datetime64("2030-01-01")
    given_prices[0] = 9.99
    assert fixings.dates[0] == np.datetime64("2026-09-04")
    assert fixings.prices[0] == 2.930
    assert not fixings.dates.flags.writeable
    assert not fixings.prices.flags.writeable
    with pytest.raises(ValueError):
        fixings.dates[0] = np.datetime64("2030-01-01")
    with pytest.raises(ValueError):
        fixings.prices[0] = 9.99
