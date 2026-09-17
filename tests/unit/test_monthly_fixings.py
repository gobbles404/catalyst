"""The monthly fixings: five rules of meaning, and the publication dates and prices retained."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.market_data.monthly_fixings import monthly_fixings


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def prices(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


# The page's sample, Waha IFERC gas: the day Platts published each month's final index, from
# January to April 2026, January's on 5 January as announced, and an illustrative price beside
# each, not a published value.
DATES = dates("2026-01-05", "2026-02-02", "2026-03-02", "2026-04-01")
PRICES = prices(1.85, 2.10, 1.95, 1.60)

# The schedule's publication dates, November 2025 to June 2026: the sample's four with two before
# and two after, as the schedule's builder handed them over, sorted and one per contract.
SCHEDULED = dates(
    "2025-11-03",
    "2025-12-01",
    "2026-01-05",
    "2026-02-02",
    "2026-03-02",
    "2026-04-01",
    "2026-05-01",
    "2026-06-01",
)


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_publication_date_and_price_aligned() -> None:
    fixings = monthly_fixings(DATES, PRICES, SCHEDULED)
    assert np.array_equal(fixings.publication_dates, DATES)
    assert fixings.publication_dates.dtype == np.dtype("datetime64[D]")
    assert fixings.prices.tolist() == [1.85, 2.10, 1.95, 1.60]
    assert fixings.prices.dtype == np.dtype("float64")


def test_one_fixing_is_a_series() -> None:
    fixings = monthly_fixings(DATES[:1], PRICES[:1], SCHEDULED)
    assert np.array_equal(fixings.publication_dates, DATES[:1])
    assert fixings.prices.tolist() == [1.85]


# February and March alone: the publications before the first date and after the last impose
# nothing, and a partial history is whole between its own ends.
def test_publications_before_the_first_date_and_after_the_last_impose_nothing() -> None:
    fixings = monthly_fixings(DATES[1:3], PRICES[1:3], SCHEDULED)
    assert np.array_equal(fixings.publication_dates, DATES[1:3])


# A price at or below zero is kept as given: Waha has printed below zero.
def test_a_price_at_or_below_zero_is_kept() -> None:
    fixings = monthly_fixings(DATES[:3], prices(-1.25, 0.0, 1.95), SCHEDULED)
    assert fixings.prices.tolist() == [-1.25, 0.0, 1.95]


# The schedule's dates are a set: shuffled and repeated, they say the same, and the array handed
# over is neither written to nor kept.
def test_unsorted_or_repeated_schedule_dates_say_the_same() -> None:
    shuffled = dates(
        "2026-04-01", "2025-12-01", "2026-02-02", "2026-01-05", "2026-03-02", "2026-02-02"
    )
    shuffled.setflags(write=False)
    fixings = monthly_fixings(DATES, PRICES, shuffled)
    assert np.array_equal(fixings.publication_dates, DATES)
    assert (
        shuffled.tolist()
        == dates(
            "2026-04-01", "2025-12-01", "2026-02-02", "2026-01-05", "2026-03-02", "2026-02-02"
        ).tolist()
    )
    with pytest.raises(ValueError) as failure:
        monthly_fixings(dates("2026-01-05", "2026-03-02"), PRICES[:2], shuffled)
    assert str(failure.value) == (
        "publication_date row 2 is 2026-03-02, expected 2026-02-02, "
        "the schedule's publication after row 1's 2026-01-05"
    )


# A publication the schedule puts on a Saturday, 3 January 2026, or on a holiday, 1 January, is
# a publication: the schedule's dates are authoritative, and no calendar is consulted.
def test_a_publication_the_schedule_puts_on_a_weekend_or_a_holiday_is_accepted() -> None:
    scheduled = dates("2025-12-01", "2026-01-01", "2026-01-03", "2026-02-02")
    given = dates("2026-01-01", "2026-01-03", "2026-02-02")
    fixings = monthly_fixings(given, PRICES[:3], scheduled)
    assert np.array_equal(fixings.publication_dates, given)


# --- what is rejected, naming the row, in the order the rules run ----------------


@pytest.mark.parametrize(
    ("given_dates", "given_prices", "scheduled", "message"),
    [
        (
            DATES,
            PRICES,
            None,
            "expiry_schedule has no publication dates, expected a schedule with one per contract",
        ),
        (DATES, PRICES[:3], SCHEDULED, "price has 3 prices, expected 4, one per publication_date"),
        (DATES[:1], PRICES, SCHEDULED, "price has 4 prices, expected 1, one per publication_date"),
        (
            dates("2026-02-02", "2026-01-05", "2026-03-02", "2026-04-01"),
            PRICES,
            SCHEDULED,
            "publication_date row 2 is 2026-01-05, expected a date after row 1's 2026-02-02",
        ),
        (
            dates("2026-01-05", "2026-02-02", "2026-02-02", "2026-04-01"),
            PRICES,
            SCHEDULED,
            "publication_date row 3 is 2026-02-02, expected a date after row 2's 2026-02-02",
        ),
        (
            dates("2026-04-01", "2026-03-02", "2026-02-02", "2026-01-05"),
            PRICES,
            SCHEDULED,
            "publication_date row 2 is 2026-03-02, expected a date after row 1's 2026-04-01",
        ),
        (
            dates("2026-01-01", "2026-02-02"),
            PRICES[:2],
            SCHEDULED,
            "publication_date row 1 is 2026-01-01, "
            "expected one of the schedule's publication dates",
        ),
        (
            dates("2026-01-05", "2026-01-06"),
            PRICES[:2],
            SCHEDULED,
            "publication_date row 2 is 2026-01-06, "
            "expected one of the schedule's publication dates",
        ),
        (
            dates("2025-10-01", "2025-11-03"),
            PRICES[:2],
            SCHEDULED,
            "publication_date row 1 is 2025-10-01, "
            "expected one of the schedule's publication dates",
        ),
        (
            dates("2026-06-01", "2026-07-01"),
            PRICES[:2],
            SCHEDULED,
            "publication_date row 2 is 2026-07-01, "
            "expected one of the schedule's publication dates",
        ),
        (
            dates("2026-01-05", "2026-03-02"),
            PRICES[:2],
            SCHEDULED,
            "publication_date row 2 is 2026-03-02, expected 2026-02-02, "
            "the schedule's publication after row 1's 2026-01-05",
        ),
        (
            dates("2025-12-01", "2026-04-01"),
            PRICES[:2],
            SCHEDULED,
            "publication_date row 2 is 2026-04-01, expected 2026-01-05, "
            "the schedule's publication after row 1's 2025-12-01",
        ),
        (
            dates("2026-02-02", "2026-01-06"),
            PRICES[:2],
            SCHEDULED,
            "publication_date row 2 is 2026-01-06, expected a date after row 1's 2026-02-02",
        ),
        (
            dates("2026-01-05", "2026-01-06", "2026-04-01"),
            PRICES[:3],
            SCHEDULED,
            "publication_date row 2 is 2026-01-06, "
            "expected one of the schedule's publication dates",
        ),
        (
            DATES,
            PRICES[:3],
            None,
            "expiry_schedule has no publication dates, expected a schedule with one per contract",
        ),
    ],
    ids=[
        "a schedule without publication dates",
        "a price column one row short",
        "four prices for one date",
        "two dates swapped",
        "a date twice",
        "newest first",
        "the first of the month in place of the publication day",
        "the day after a publication",
        "a date before the schedule's first publication",
        "a date after the schedule's last publication",
        "a publication skipped",
        "three publications skipped, the first named",
        "the order is checked before the schedule",
        "the schedule is checked before the gaps",
        "the schedule's publication dates are checked before the prices",
    ],
)
def test_a_series_that_breaks_a_rule_is_rejected_naming_the_row(
    given_dates: NDArray[np.datetime64],
    given_prices: NDArray[np.float64],
    scheduled: NDArray[np.datetime64] | None,
    message: str,
) -> None:
    with pytest.raises(ValueError) as failure:
        monthly_fixings(given_dates, given_prices, scheduled)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


def a_schedule_and_a_run(data: st.DataObject) -> tuple[NDArray[np.datetime64], int, int]:
    """Any schedule of distinct publication days, in any order, and the ends of a run within it."""
    count = data.draw(st.integers(1, 200))
    gaps = data.draw(st.lists(st.integers(1, 40), min_size=count, max_size=count))
    offsets = np.cumsum(gaps, dtype=np.int64)
    scheduled = np.datetime64("2000-01-01") + offsets.astype("timedelta64[D]")
    scheduled = scheduled[data.draw(st.permutations(range(count)))]
    first = data.draw(st.integers(0, count - 1))
    last = data.draw(st.integers(first, count - 1))
    return scheduled, first, last


@settings(deadline=None)
@given(data=st.data())
def test_any_run_of_scheduled_publications_and_their_prices_are_kept(
    data: st.DataObject,
) -> None:
    scheduled, first, last = a_schedule_and_a_run(data)
    run = np.sort(scheduled)[first : last + 1]
    given_prices = np.array(
        data.draw(st.lists(st.floats(-1e6, 1e6), min_size=run.size, max_size=run.size)),
        dtype=np.float64,
    )
    fixings = monthly_fixings(run, given_prices, scheduled)
    assert np.array_equal(fixings.publication_dates, run)
    assert np.array_equal(fixings.prices, given_prices)


@settings(deadline=None)
@given(data=st.data())
def test_a_run_with_one_publication_left_out_names_it(data: st.DataObject) -> None:
    scheduled, first, last = a_schedule_and_a_run(data)
    run = np.sort(scheduled)[first : last + 1]
    if run.size < 3:
        run = np.sort(scheduled)[:3]
        if run.size < 3:
            return
    left_out = data.draw(st.integers(1, run.size - 2))
    given = np.delete(run, left_out)
    with pytest.raises(ValueError) as failure:
        monthly_fixings(given, np.zeros(given.size), scheduled)
    assert str(failure.value) == (
        f"publication_date row {left_out + 1} is {run[left_out + 1]}, expected {run[left_out]}, "
        f"the schedule's publication after row {left_out}'s {run[left_out - 1]}"
    )


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_columns() -> None:
    given_dates, given_prices, scheduled = DATES.copy(), PRICES.copy(), SCHEDULED.copy()
    fixings = monthly_fixings(given_dates, given_prices, scheduled)
    given_dates[0] = np.datetime64("2030-01-01")
    given_prices[0] = 0.0
    scheduled[2] = np.datetime64("2030-01-01")
    assert fixings.publication_dates[0] == np.datetime64("2026-01-05")
    assert fixings.prices[0] == 1.85
    assert not fixings.publication_dates.flags.writeable
    assert not fixings.prices.flags.writeable
    with pytest.raises(ValueError):
        fixings.prices[0] = 0.0
    with pytest.raises(ValueError):
        fixings.publication_dates[0] = np.datetime64("2030-01-01")
