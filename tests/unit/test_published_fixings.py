"""Published fixings: their four rules of meaning, each price found on its print of the index's
schedule, and the series kept oldest first."""

import numpy as np
import pytest
from holiday_fixtures import index_on
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.gas_daily_schedule import gas_daily_schedule
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.index_definitions.published_schedule import published_schedule
from catalyst.market_data.published_fixings import published_fixings

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def numbers(*values: float) -> NDArray[np.float64]:
    return np.array(values, dtype=np.float64)


CONVENTIONS = index_conventions("DOLLAR", "GAL", "DOLLAR", "VOLUME", "GAL", UNITS)
SPECIFICATIONS = contract_specifications(
    ("gal",), np.array([1.0]), ("GAL",), np.array([0.0]), np.array([0.0]), UNITS
)


def an_index(schedule: object, name: str = "DOE Diesel") -> Index:
    return index_on(name, f"{name} index", schedule, CONVENTIONS, SPECIFICATIONS, None, None, UNITS)


# The page's sample: the schedule page's six prints, and the prices of the three dated before
# Wednesday 16 September 2026, as the desk keeps a series, the newest at the top.
PRINTS = dates("2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05")
DIESEL = an_index(published_schedule(("Q26", "U26", "U26", "U26", "U26", "V26"), PRINTS))
DATED = dates("2026-09-14", "2026-09-07", "2026-08-31")
PRICES = numbers(3.20, 3.00, 2.95)


# --- what is kept -------------------------------------------------------------


def test_the_sample_is_kept_oldest_first_each_price_on_its_print() -> None:
    fixings = published_fixings(DATED, PRICES, DIESEL)
    assert fixings.index is DIESEL
    assert fixings.rows.tolist() == [0, 1, 2]
    assert fixings.rows.dtype == np.dtype(np.intp)
    assert fixings.prices.tolist() == [2.95, 3.00, 3.20]
    assert fixings.prices.dtype == np.dtype(np.float64)


def test_one_price_is_a_series() -> None:
    fixings = published_fixings(dates("2026-09-21"), numbers(3.5), DIESEL)
    assert fixings.rows.tolist() == [3] and fixings.prices.tolist() == [3.5]


# Any prints of the schedule may be given, with a gap between them or ending past any day: which
# have fixed, and whether every fixed print has its price, are the history's to say.
def test_any_prints_of_the_schedule_are_taken_whichever_they_are() -> None:
    fixings = published_fixings(
        dates("2026-10-05", "2026-09-14", "2026-08-31"), numbers(1.0, 2.0, 3.0), DIESEL
    )
    assert fixings.rows.tolist() == [0, 2, 5]
    assert fixings.prices.tolist() == [3.0, 2.0, 1.0]


def test_a_price_is_any_number_zero_and_below_included() -> None:
    fixings = published_fixings(DATED, numbers(0.0, -1.5, 1e9), DIESEL)
    assert fixings.prices.tolist() == [1e9, -1.5, 0.0]


def test_no_rows_are_fixings_of_no_print() -> None:
    fixings = published_fixings(dates(), numbers(), DIESEL)
    assert fixings.rows.size == 0 and fixings.prices.size == 0


# --- what is refused, in the order the rules run ------------------------------


def test_an_index_of_another_kind_is_refused_first() -> None:
    daily = an_index(
        gas_daily_schedule(("U26",), dates("2026-09-01"), dates("2026-09-30")),
        "Henry Hub Gas Daily",
    )
    with pytest.raises(ValueError) as failure:
        published_fixings(DATED, PRICES[:2], daily)
    assert str(failure.value) == "index is a Gas Daily index, expected a published index"


@pytest.mark.parametrize(
    ("prices", "message"),
    [
        (PRICES[:2], "price has 2 prices, expected 3, one per publication_date"),
        (PRICES[:1], "price has 1 price, expected 3, one per publication_date"),
        (numbers(1.0, 2.0, 3.0, 4.0), "price has 4 prices, expected 3, one per publication_date"),
    ],
    ids=["a price column one row short", "one price for three dates", "one row long"],
)
def test_a_price_column_without_one_price_per_date_is_refused(
    prices: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        published_fixings(DATED, prices, DIESEL)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("dated", "message"),
    [
        (
            dates("2026-08-31", "2026-09-07", "2026-09-14"),
            "publication_date row 2 is 2026-09-07, expected a date before row 1's 2026-08-31",
        ),
        (
            dates("2026-09-14", "2026-09-14", "2026-09-07"),
            "publication_date row 2 is 2026-09-14, expected a date before row 1's 2026-09-14",
        ),
        (
            dates("2026-09-14", "2026-08-31", "2026-09-07"),
            "publication_date row 3 is 2026-09-07, expected a date before row 2's 2026-08-31",
        ),
    ],
    ids=[
        "a series pasted oldest first fails at its second row",
        "a date given twice",
        "a date after the row above, further down",
    ],
)
def test_a_date_that_is_not_before_the_row_above_is_refused(
    dated: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        published_fixings(dated, PRICES, DIESEL)
    assert str(failure.value) == message


@pytest.mark.parametrize(
    ("dated", "message"),
    [
        (
            dates("2026-09-15", "2026-09-07", "2026-08-31"),
            "publication_date row 1 is 2026-09-15, expected the publication date of one of the "
            "index's prints",
        ),
        (
            dates("2026-09-14", "2026-09-07", "2026-08-24"),
            "publication_date row 3 is 2026-08-24, expected the publication date of one of the "
            "index's prints",
        ),
        (
            dates("2026-10-12", "2026-10-05", "2026-09-28"),
            "publication_date row 1 is 2026-10-12, expected the publication date of one of the "
            "index's prints",
        ),
        (
            dates("2026-09-15", "2026-09-08", "2026-08-31"),
            "publication_date row 1 is 2026-09-15, expected the publication date of one of the "
            "index's prints",
        ),
    ],
    ids=[
        "the day a price was released, not the date it carries",
        "history from before the schedule's first print",
        "a date after the schedule's last print",
        "two dates the schedule does not list: the first from the top is named",
    ],
)
def test_a_date_that_is_no_print_of_the_schedule_is_refused(
    dated: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        published_fixings(dated, PRICES, DIESEL)
    assert str(failure.value) == message


# The rules run in one order: the index's kind, the count, the order, then the schedule's dates.
def test_the_rules_run_in_one_order() -> None:
    unlisted_and_backwards = dates("2026-09-08", "2026-09-15", "2026-09-22")
    with pytest.raises(ValueError) as order:
        published_fixings(unlisted_and_backwards, PRICES, DIESEL)
    assert str(order.value).startswith(
        "publication_date row 2 is 2026-09-15, expected a date before"
    )
    with pytest.raises(ValueError) as count:
        published_fixings(unlisted_and_backwards, PRICES[:2], DIESEL)
    assert str(count.value) == "price has 2 prices, expected 3, one per publication_date"


# --- the general rules --------------------------------------------------------


@given(data=st.data())
def test_any_prints_given_newest_first_are_kept_oldest_first_on_their_rows(
    data: st.DataObject,
) -> None:
    count = data.draw(st.integers(1, 60))
    gaps = data.draw(st.lists(st.integers(1, 30), min_size=count, max_size=count))
    listed = EPOCH + np.cumsum(np.array(gaps) + 60).astype("timedelta64[D]")
    index = an_index(published_schedule(tuple(f"c{i // 4}" for i in range(count)), listed))
    chosen = sorted(data.draw(st.sets(st.integers(0, count - 1), min_size=1)))
    prices = np.array(
        data.draw(
            st.lists(
                st.floats(-1e6, 1e6, allow_nan=False),
                min_size=len(chosen),
                max_size=len(chosen),
            )
        )
    )
    fixings = published_fixings(listed[chosen][::-1], prices[::-1], index)
    assert fixings.rows.tolist() == chosen
    assert np.array_equal(fixings.prices, prices)


@given(data=st.data())
def test_any_date_between_two_prints_is_refused_at_its_row(data: st.DataObject) -> None:
    count = data.draw(st.integers(2, 30))
    listed = EPOCH + (40_000 + 7 * np.arange(count)).astype("timedelta64[D]")
    index = an_index(published_schedule(("c0",) * count, listed))
    at = data.draw(st.integers(0, count - 2))
    stray = listed[at] + np.timedelta64(data.draw(st.integers(1, 6)), "D")
    dated = np.concatenate((listed[at + 1 :][::-1], [stray], listed[:at][::-1]))
    with pytest.raises(ValueError) as failure:
        published_fixings(dated, np.zeros(dated.size), index)
    assert str(failure.value) == (
        f"publication_date row {count - at} is {stray}, expected the publication date of one of "
        "the index's prints"
    )


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_prices_and_keep_the_index_by_reference() -> None:
    prices = PRICES.copy()
    fixings = published_fixings(DATED, prices, DIESEL)
    prices[0] = 99.0
    assert fixings.prices.tolist() == [2.95, 3.00, 3.20]
    for column in (fixings.rows, fixings.prices):
        assert not column.flags.writeable
    with pytest.raises(ValueError):
        fixings.prices[0] = 1.0
    assert fixings.index is DIESEL
