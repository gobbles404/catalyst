"""The Gas Daily fixings: a series given newest first and kept oldest first, three rules of
meaning on the rows as the sheet gave them, the flow days and prices retained, and the index
kept."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.globals.unit_conversions import UNITS
from goosedove.index_definitions.contract_specifications import contract_specifications
from goosedove.index_definitions.futures_schedule import futures_schedule
from goosedove.index_definitions.gas_daily_schedule import gas_daily_schedule
from goosedove.index_definitions.holiday_calendar import holiday_calendar
from goosedove.index_definitions.iferc_schedule import iferc_schedule
from goosedove.index_definitions.index import Index, index
from goosedove.index_definitions.index_conventions import index_conventions
from goosedove.market_data.gas_daily_fixings import gas_daily_fixings

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


CONVENTIONS = index_conventions("USD", "MMBTU", "USD", "ENERGY", "MMBTU", UNITS)
SPECIFICATIONS = contract_specifications(
    ("ICE",), np.array([2500.0]), ("MMBTU",), np.array([0.0]), np.array([0.0]), UNITS
)


def an_index(schedule: object, name: str = "Henry Hub Gas Daily") -> Index:
    """The index of that schedule with one set of conventions and specifications throughout,
    since nothing here reads either, and no holiday calendar, as an IFERC or a Gas Daily index
    has none."""
    return index(name, f"{name} index", schedule, CONVENTIONS, SPECIFICATIONS, None, None, UNITS)


# The page's sample as the desk keeps it, the newest flow day in the first row: Henry Hub Gas
# Daily over Labor Day week 2026, Friday 4 September's print covering Saturday 5 to Tuesday 8,
# the four rows carrying one number, over the index of the one month of September.
DAYS = dates("2026-09-09", "2026-09-08", "2026-09-07", "2026-09-06", "2026-09-05", "2026-09-04")
PRICES = prices(2.900, 2.875, 2.875, 2.875, 2.875, 2.930)
INDEX = an_index(gas_daily_schedule(("U26",), dates("2026-09-01"), dates("2026-09-30")))
FUTURES_INDEX = index(
    "WTI NYMEX",
    "West Texas Intermediate crude oil - NYMEX",
    futures_schedule(("m26", "n26"), dates("2026-05-19", "2026-06-22"), None),
    CONVENTIONS,
    SPECIFICATIONS,
    holiday_calendar(dates("2026-05-25")),
    None,
    UNITS,
)
IFERC_INDEX = an_index(iferc_schedule(("F26",), dates("2026-01-05")), "Waha IFERC")


# --- what is kept -------------------------------------------------------------


# The series is given newest first and kept oldest first, each price still beside its own flow
# day: the first row given is the last one kept.
def test_the_sample_is_kept_oldest_first_with_every_price_beside_its_day_and_the_index() -> None:
    fixings = gas_daily_fixings(DAYS, PRICES, INDEX)
    assert (
        fixings.dates.tolist()
        == dates(
            "2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08", "2026-09-09"
        ).tolist()
    )
    assert fixings.prices.tolist() == [2.930, 2.875, 2.875, 2.875, 2.875, 2.900]
    assert dict(zip(fixings.dates.tolist(), fixings.prices.tolist(), strict=True)) == dict(
        zip(DAYS.tolist(), PRICES.tolist(), strict=True)
    )
    assert fixings.dates.dtype == np.dtype("datetime64[D]")
    assert fixings.prices.dtype == np.dtype(np.float64)
    assert fixings.dates.ndim == fixings.prices.ndim == 1
    # The weekend and the holiday are rows like any other, carrying Friday's number.
    assert fixings.prices[1:5].tolist() == [2.875] * 4
    assert fixings.index is INDEX


# One row is a series, with nothing above or below it to be the day before.
def test_the_fixings_of_one_day_are_a_series() -> None:
    fixings = gas_daily_fixings(DAYS[:1], PRICES[:1], INDEX)
    assert np.array_equal(fixings.dates, dates("2026-09-09"))
    assert np.array_equal(fixings.prices, prices(2.900))
    oldest = gas_daily_fixings(DAYS[-1:], PRICES[-1:], INDEX)
    assert np.array_equal(oldest.dates, dates("2026-09-04"))
    assert np.array_equal(oldest.prices, prices(2.930))


# A whole month given from its last day up to its first: thirty prices, no two alike, each kept
# beside the flow day it was given with.
def test_a_whole_month_given_newest_first_is_kept_oldest_first() -> None:
    oldest_first = np.arange("2026-09-01", "2026-10-01", dtype="datetime64[D]")
    their_prices = prices(*(2.8 + i / 100 for i in range(30)))
    fixings = gas_daily_fixings(oldest_first[::-1], their_prices[::-1], INDEX)
    assert fixings.dates.size == 30
    assert np.array_equal(fixings.dates, oldest_first)
    assert np.array_equal(fixings.prices, their_prices)


def test_a_price_below_zero_and_a_zero_are_kept_beside_their_days() -> None:
    fixings = gas_daily_fixings(DAYS[:3], prices(-1.25, 0.0, 1.95), INDEX)
    assert np.array_equal(fixings.prices, prices(1.95, 0.0, -1.25))
    assert fixings.dates[-1] == np.datetime64("2026-09-09") and fixings.prices[-1] == -1.25


# A run across a month end and one across a year end: no month or year is looked at, and days
# outside the index's schedule, September alone, are kept, since a series may run past the
# calendar on either side.
def test_a_run_across_a_month_end_and_a_year_end_is_kept() -> None:
    month_end = dates("2026-10-02", "2026-10-01", "2026-09-30")
    assert np.array_equal(gas_daily_fixings(month_end, PRICES[:3], INDEX).dates, month_end[::-1])
    year_end = dates("2027-01-02", "2027-01-01", "2026-12-31")
    assert np.array_equal(gas_daily_fixings(year_end, PRICES[:3], INDEX).dates, year_end[::-1])


# A series of no rows reaches the builder only from a Python caller, the seam never sending a
# range of no cells, and makes fixings of no rows: the one comparison asks nothing of it.
def test_a_series_of_no_rows_is_fixings_of_no_rows() -> None:
    fixings = gas_daily_fixings(dates(), prices(), INDEX)
    assert fixings.dates.size == 0 and fixings.prices.size == 0
    assert not fixings.dates.flags.writeable and not fixings.prices.flags.writeable


# --- what is rejected ---------------------------------------------------------


# The kind is the first rule: a count the columns would refuse is not reached.
def test_an_index_of_another_kind_is_refused_before_the_columns_are_looked_at() -> None:
    for other, what in ((FUTURES_INDEX, "a futures index"), (IFERC_INDEX, "an IFERC index")):
        with pytest.raises(ValueError) as failure:
            gas_daily_fixings(DAYS, PRICES[:5], other)
        assert str(failure.value) == f"index is {what}, expected a Gas Daily index"


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
            dates("2026-09-06", "2026-09-05", "2026-09-05", "2026-09-04"),
            PRICES[:4],
            "flow_date row 3 is 2026-09-05, expected 2026-09-04, the day before row 2's 2026-09-05",
        ),
        (
            dates("2026-09-07", "2026-09-06", "2026-09-04"),
            PRICES[:3],
            "flow_date row 3 is 2026-09-04, expected 2026-09-05, the day before row 2's 2026-09-06",
        ),
        (
            dates("2026-09-06", "2026-09-04"),
            PRICES[:2],
            "flow_date row 2 is 2026-09-04, expected 2026-09-05, the day before row 1's 2026-09-06",
        ),
        (
            dates("2026-09-07", "2026-09-04"),
            PRICES[:2],
            "flow_date row 2 is 2026-09-04, expected 2026-09-06, the day before row 1's 2026-09-07",
        ),
        (
            dates("2026-09-04", "2026-09-05", "2026-09-06"),
            PRICES[:3],
            "flow_date row 2 is 2026-09-05, expected 2026-09-03, the day before row 1's 2026-09-04",
        ),
        (
            dates("2026-09-07", "2026-09-05", "2026-09-06", "2026-09-04"),
            PRICES[:4],
            "flow_date row 2 is 2026-09-05, expected 2026-09-06, the day before row 1's 2026-09-07",
        ),
        (
            dates("2026-09-09", "2026-09-08", "2026-09-07", "2026-09-05", "2026-09-06"),
            PRICES[:5],
            "flow_date row 4 is 2026-09-05, expected 2026-09-06, the day before row 3's 2026-09-07",
        ),
        (
            dates("2026-09-06", "2026-09-04"),
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
        "a day skipped lower down",
        "a day skipped",
        "two days skipped",
        "oldest first, as the series was once given",
        "two days swapped in the middle",
        "two days swapped at the bottom",
        "a day skipped and the count wrong, the count named first",
    ],
)
def test_fixings_that_cannot_be_made_say_why(
    days: NDArray[np.datetime64], given_prices: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        gas_daily_fixings(days, given_prices, INDEX)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


# Any run of consecutive days, given from its last day up to its first, is kept whole, oldest
# first, each price beside the day it was given with.
@given(first=st.integers(61, 2958000), count=st.integers(1, 400), data=st.data())
def test_any_run_of_consecutive_days_with_one_price_each_is_kept_aligned(
    first: int, count: int, data: st.DataObject
) -> None:
    days = EPOCH + (first + np.arange(count)).astype("timedelta64[D]")
    their_prices = np.array(
        data.draw(
            st.lists(
                st.floats(-100, 100, allow_nan=False, allow_infinity=False),
                min_size=count,
                max_size=count,
            )
        ),
        dtype=np.float64,
    )
    fixings = gas_daily_fixings(days[::-1], their_prices[::-1], INDEX)
    assert np.array_equal(fixings.dates, days)
    assert np.array_equal(fixings.prices, their_prices)
    assert fixings.index is INDEX


# Any such run given oldest first, of two rows or more, is refused at its second row: one
# direction is taken, and the other is never sorted into it.
@given(first=st.integers(61, 2958000), count=st.integers(2, 400))
def test_any_run_given_oldest_first_is_refused_at_its_second_row(first: int, count: int) -> None:
    days = EPOCH + (first + np.arange(count)).astype("timedelta64[D]")
    with pytest.raises(ValueError) as failure:
        gas_daily_fixings(days, np.zeros(count), INDEX)
    assert str(failure.value) == (
        f"flow_date row 2 is {days[1]}, expected {days[0] - np.timedelta64(1, 'D')}, "
        f"the day before row 1's {days[0]}"
    )


# With one day left out of a run, the row below the gap is refused, as the sheet counts its rows
# from the newest down, naming the day expected.
@given(first=st.integers(61, 2958000), count=st.integers(3, 60), data=st.data())
def test_a_day_left_out_of_a_run_is_refused_at_the_row_below_the_gap(
    first: int, count: int, data: st.DataObject
) -> None:
    left_out = data.draw(st.integers(1, count - 2))
    days = EPOCH + (first + np.arange(count)).astype("timedelta64[D]")
    newest_first = np.delete(days, left_out)[::-1]
    with pytest.raises(ValueError) as failure:
        gas_daily_fixings(newest_first, np.zeros(newest_first.size), INDEX)
    expected = EPOCH + np.timedelta64(first + left_out, "D")
    before = EPOCH + np.timedelta64(first + left_out - 1, "D")
    after = EPOCH + np.timedelta64(first + left_out + 1, "D")
    assert str(failure.value) == (
        f"flow_date row {count - left_out} is {before}, expected {expected}, "
        f"the day before row {count - left_out - 1}'s {after}"
    )


# --- ownership ----------------------------------------------------------------


# The builder leaves what it was given as it was, in its order and writable, and keeps columns
# of its own: a later change to an input changes no fixing, and what is kept refuses writes.
def test_the_fixings_own_their_columns_and_keep_the_index_that_arrived() -> None:
    days, given_prices = DAYS.copy(), PRICES.copy()
    fixings = gas_daily_fixings(days, given_prices, INDEX)
    assert np.array_equal(days, DAYS) and np.array_equal(given_prices, PRICES)
    assert days.flags.writeable and given_prices.flags.writeable
    assert not np.shares_memory(fixings.dates, days)
    assert not np.shares_memory(fixings.prices, given_prices)
    days[-1] = np.datetime64("2030-01-01")
    given_prices[-1] = 9.99
    assert fixings.dates[0] == np.datetime64("2026-09-04")
    assert fixings.prices[0] == 2.930
    assert fixings.dates.flags.owndata and fixings.dates.flags.c_contiguous
    assert fixings.prices.flags.owndata and fixings.prices.flags.c_contiguous
    assert not fixings.dates.flags.writeable
    assert not fixings.prices.flags.writeable
    with pytest.raises(ValueError):
        fixings.dates[0] = np.datetime64("2030-01-01")
    with pytest.raises(ValueError):
        fixings.prices[0] = 9.99
    assert fixings.index is INDEX
