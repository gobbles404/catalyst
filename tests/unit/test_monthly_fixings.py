"""The monthly fixings: three rules of meaning, and the months kept as months beside the prices."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.market_data.monthly_fixings import monthly_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def months(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[M]")


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# The page's sample: four months of 2026, each typed as its first day, and the price of each.
DATES = dates("2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01")
PRICES = prices(2.86, 3.01, 3.24, 3.19)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_month_as_a_month_beside_its_price() -> None:
    fixings = monthly_fixings(DATES, PRICES)
    assert np.array_equal(fixings.months, months("2026-05", "2026-06", "2026-07", "2026-08"))
    assert fixings.months.dtype == np.dtype("datetime64[M]")
    assert fixings.prices.tolist() == [2.86, 3.01, 3.24, 3.19]


def test_one_fixing_is_a_series() -> None:
    fixings = monthly_fixings(DATES[:1], PRICES[:1])
    assert np.array_equal(fixings.months, months("2026-05"))
    assert fixings.prices.tolist() == [2.86]


# A price at or below zero, and gaps of any length between the months: kept as given.
def test_nothing_else_is_checked() -> None:
    fixings = monthly_fixings(
        dates("2020-04-01", "2020-05-01", "2021-01-01"), prices(-37.63, 0.0, 2.5)
    )
    assert np.array_equal(fixings.months, months("2020-04", "2020-05", "2021-01"))
    assert fixings.prices.tolist() == [-37.63, 0.0, 2.5]


# --- what is rejected, naming the row, in the order the rules run ----------------


@pytest.mark.parametrize(
    ("given_dates", "given_prices", "message"),
    [
        (DATES, PRICES[:3], "price has 3 prices, expected 4, one per month"),
        (DATES[:1], PRICES, "price has 4 prices, expected 1, one per month"),
        (
            dates("2026-05-01", "2026-05-26", "2026-07-01", "2026-08-01"),
            PRICES,
            "month row 2 is 2026-05-26, expected the first day of a month",
        ),
        (
            dates("2026-06-01", "2026-05-01", "2026-07-01", "2026-08-01"),
            PRICES,
            "month row 2 is 2026-05, expected a month after row 1's 2026-06",
        ),
        (
            dates("2026-05-01", "2026-06-01", "2026-06-01", "2026-08-01"),
            PRICES,
            "month row 3 is 2026-06, expected a month after row 2's 2026-06",
        ),
        (
            dates("2026-08-01", "2026-07-01", "2026-06-01", "2026-05-01"),
            PRICES,
            "month row 2 is 2026-07, expected a month after row 1's 2026-08",
        ),
        (
            dates("2026-05-31", "2026-05-01", "2026-07-01", "2026-08-01"),
            PRICES,
            "month row 1 is 2026-05-31, expected the first day of a month",
        ),
    ],
    ids=[
        "a price column one row short",
        "four prices for one month",
        "a day that is not the first",
        "two months swapped",
        "a month twice",
        "newest first",
        "the first-day rule runs before the order",
    ],
)
def test_a_column_that_breaks_a_rule_is_rejected_naming_the_row(
    given_dates: NDArray[np.datetime64], given_prices: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        monthly_fixings(given_dates, given_prices)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


@given(count=st.integers(1, 400), data=st.data())
def test_any_increasing_months_and_their_prices_are_kept(count: int, data: st.DataObject) -> None:
    gaps = data.draw(st.lists(st.integers(1, 6), min_size=count - 1, max_size=count - 1))
    offsets = np.concatenate(([0], np.cumsum(gaps, dtype=np.int64))).astype(np.int64)
    start = data.draw(st.integers(0, 1200))
    given_months = np.datetime64("2000-01", "M") + (start + offsets).astype("timedelta64[M]")
    given_prices = np.array(
        data.draw(st.lists(st.floats(-1e6, 1e6), min_size=count, max_size=count)), dtype=np.float64
    )
    fixings = monthly_fixings(given_months.astype("datetime64[D]"), given_prices)
    assert np.array_equal(fixings.months, given_months)
    assert np.array_equal(fixings.prices, given_prices)


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_columns() -> None:
    given_dates, given_prices = DATES.copy(), PRICES.copy()
    fixings = monthly_fixings(given_dates, given_prices)
    given_dates[0] = np.datetime64("2030-01-01")
    given_prices[0] = 0.0
    assert fixings.months[0] == np.datetime64("2026-05")
    assert fixings.prices[0] == 2.86
    assert not fixings.months.flags.writeable
    assert not fixings.prices.flags.writeable
    with pytest.raises(ValueError):
        fixings.prices[0] = 0.0
