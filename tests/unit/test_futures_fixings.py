"""The futures fixings: a series given newest first and kept oldest first, the five rules of
meaning on the rows as the sheet gave them, the index kept, and the columns retained and
aligned."""

import numpy as np
import pytest
from holiday_fixtures import closed_on, index_on
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.globals.unit_conversions import UNITS
from catalyst.index_definitions.contract_specifications import contract_specifications
from catalyst.index_definitions.futures_schedule import futures_schedule
from catalyst.index_definitions.gas_daily_schedule import gas_daily_schedule
from catalyst.index_definitions.iferc_schedule import iferc_schedule
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.index_conventions import index_conventions
from catalyst.market_data.futures_fixings import futures_fixings

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


def settles(*values: float) -> NDArray[np.float64]:
    """A series of the prompt alone: one column of settles, a row per day."""
    return np.array(values, dtype=np.float64).reshape(-1, 1)


# The page's sample as the desk keeps it, the newest day in the first row: four days of May
# 2026, a weekend between the last two rows, and their settles, each beside its day.
DATES = dates("2026-05-06", "2026-05-05", "2026-05-04", "2026-05-01")
SETTLES = settles(95.08, 102.27, 106.42, 101.94)

# The holiday calendar page's sample, the ten days one market is closed in 2026; the one in
# May is the 25th, a Monday.
HOLIDAYS = dates(
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-06-19",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
)

# A calendar whose only day is outside May: the series is then checked against Monday to
# Friday alone.
ELSEWHERE = dates("2026-01-01")

# The index the fixings are of: a futures schedule of two contracts, one set of conventions and
# specifications, and whatever holiday calendar a test names.
SCHEDULE = futures_schedule(("m26", "n26"), dates("2026-05-19", "2026-06-22"), None)
CONVENTIONS = index_conventions("DOLLAR", "BBL", "DOLLAR", "VOLUME", "BBL", UNITS)
SPECIFICATIONS = contract_specifications(
    ("NYMEX",), np.array([1000.0]), ("BBL",), np.array([0.0]), np.array([0.0]), UNITS
)


def an_index(holidays: NDArray[np.datetime64]) -> Index:
    """A futures index whose holiday calendar lists those days."""
    return index_on(
        "sample",
        "Sample futures index",
        SCHEDULE,
        CONVENTIONS,
        SPECIFICATIONS,
        closed_on(holidays),
        None,
        UNITS,
    )


# --- what is kept -------------------------------------------------------------


# The series is given newest first and kept oldest first, each settle still beside its own day:
# the first row given is the last one kept.
def test_the_sample_is_kept_oldest_first_with_every_settle_beside_its_date() -> None:
    fixings = futures_fixings(DATES, SETTLES, an_index(HOLIDAYS))
    assert (
        fixings.dates.tolist()
        == dates("2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06").tolist()
    )
    assert fixings.settles.shape == (4, 1)  # one column, the prompt's
    assert fixings.settles[:, 0].tolist() == [101.94, 106.42, 102.27, 95.08]
    assert dict(zip(fixings.dates.tolist(), fixings.settles.tolist(), strict=True)) == dict(
        zip(DATES.tolist(), SETTLES.tolist(), strict=True)
    )
    assert fixings.dates.dtype == np.dtype("datetime64[D]")
    assert fixings.settles.dtype == np.dtype("float64")


# One row is a series, with nothing above or below it to be ordered against.
def test_one_fixing_is_a_series() -> None:
    fixings = futures_fixings(DATES[:1], SETTLES[:1], an_index(HOLIDAYS))
    assert np.array_equal(fixings.dates, DATES[:1])
    assert fixings.settles.tolist() == [[95.08]]
    oldest = futures_fixings(DATES[-1:], SETTLES[-1:], an_index(HOLIDAYS))
    assert oldest.dates.tolist() == dates("2026-05-01").tolist()
    assert oldest.settles.tolist() == [[101.94]]


# Tuesday 26 May back to Friday 22 May 2026: the holiday on the Monday and the weekend are the
# days without a fixing, and the series is whole without them.
def test_a_weekend_and_a_listed_holiday_are_the_days_without_a_fixing() -> None:
    newest_first = dates("2026-05-26", "2026-05-22")
    fixings = futures_fixings(newest_first, SETTLES[:2], an_index(HOLIDAYS))
    assert np.array_equal(fixings.dates, newest_first[::-1])


# Thursday 7 May back to Tuesday 5 May: the Friday after and the Monday before are business
# days, and neither is asked for, since the two end dates bound the check.
def test_nothing_is_asked_for_after_the_first_rows_date_or_before_the_last_rows() -> None:
    newest_first = dates("2026-05-07", "2026-05-06", "2026-05-05")
    fixings = futures_fixings(newest_first, SETTLES[:3], an_index(HOLIDAYS))
    assert np.array_equal(fixings.dates, newest_first[::-1])


# A settle at or below zero is kept as given, beside its own day. WTI's May 2020 contract
# settled at minus 37.63 on Monday 20 April 2020.
def test_a_settle_at_or_below_zero_is_kept() -> None:
    fixings = futures_fixings(
        dates("2020-04-22", "2020-04-21", "2020-04-20"),
        settles(39.27, 0.0, -37.63),
        an_index(HOLIDAYS),
    )
    assert fixings.settles[:, 0].tolist() == [-37.63, 0.0, 39.27]
    assert fixings.dates[0] == np.datetime64("2020-04-20")


# A day listed twice counts once, and a day listed on a weekend adds nothing: the calendar is
# read as numpy reads it, and the series that is whole without those days is whole with them.
def test_a_holiday_listed_twice_or_on_a_weekend_changes_nothing() -> None:
    calendar = dates("2026-05-25", "2026-05-25", "2026-05-02", "2026-05-03")
    fixings = futures_fixings(DATES, SETTLES, an_index(calendar))
    assert np.array_equal(fixings.dates, DATES[::-1])
    fixings = futures_fixings(dates("2026-05-26", "2026-05-22"), SETTLES[:2], an_index(calendar))
    assert fixings.dates.tolist() == [np.datetime64("2026-05-22"), np.datetime64("2026-05-26")]


# --- the index is a futures index, and the fixings keep it ---------------------


def test_an_index_of_another_kind_is_refused_before_the_columns_are_looked_at() -> None:
    gas_daily = index_on(
        "Henry Hub Gas Daily",
        "Henry Hub natural gas - Platts Gas Daily",
        gas_daily_schedule(("U26",), dates("2026-09-01"), dates("2026-09-30")),
        CONVENTIONS,
        SPECIFICATIONS,
        None,
        None,
        UNITS,
    )
    with pytest.raises(ValueError) as failure:
        futures_fixings(DATES, SETTLES[:2], gas_daily)
    assert str(failure.value) == "index is a Gas Daily index, expected a futures index"
    iferc = index_on(
        "Henry Hub IFERC",
        "Henry Hub natural gas - Inside FERC monthly index",
        iferc_schedule(("V26",), dates("2026-10-01")),
        CONVENTIONS,
        SPECIFICATIONS,
        None,
        None,
        UNITS,
    )
    with pytest.raises(ValueError) as failure:
        futures_fixings(DATES, SETTLES, iferc)
    assert str(failure.value) == "index is an IFERC index, expected a futures index"


def test_the_fixings_keep_their_index() -> None:
    made = an_index(HOLIDAYS)
    fixings = futures_fixings(DATES, SETTLES, made)
    assert fixings.index is made
    assert fixings.index.holiday_calendar is not None
    assert np.array_equal(fixings.index.holiday_calendar.holiday, HOLIDAYS)


# A series of no rows reaches the builder only from a Python caller, the seam never sending a
# range of no cells. It has always made fixings of no rows: the count of business days asks
# nothing of it, as the look over the day before each date asks nothing.
def test_a_series_of_no_rows_is_fixings_of_no_rows() -> None:
    fixings = futures_fixings(dates(), settles(), an_index(HOLIDAYS))
    assert fixings.dates.size == 0 and fixings.settles.size == 0
    assert not fixings.dates.flags.writeable and not fixings.settles.flags.writeable


# --- what is rejected, naming the sheet's own row -------------------------------


@pytest.mark.parametrize(
    ("given", "calendar", "message"),
    [
        (
            dates("2026-05-05", "2026-05-06", "2026-05-04", "2026-05-01"),
            HOLIDAYS,
            "date row 2 is 2026-05-06, expected a date before row 1's 2026-05-05",
        ),
        (
            dates("2026-05-06", "2026-05-04", "2026-05-04", "2026-05-01"),
            HOLIDAYS,
            "date row 3 is 2026-05-04, expected a date before row 2's 2026-05-04",
        ),
        (
            dates("2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06"),
            HOLIDAYS,
            "date row 2 is 2026-05-04, expected a date before row 1's 2026-05-01",
        ),
        (
            dates("2026-05-06", "2026-05-05", "2026-05-01", "2026-05-04"),
            HOLIDAYS,
            "date row 4 is 2026-05-04, expected a date before row 3's 2026-05-01",
        ),
        (
            dates("2026-05-09", "2026-05-08"),
            HOLIDAYS,
            "date row 1 is 2026-05-09, a Saturday, expected a business day",
        ),
        (
            dates("2026-05-04", "2026-05-03"),
            HOLIDAYS,
            "date row 2 is 2026-05-03, a Sunday, expected a business day",
        ),
        (
            dates("2026-05-26", "2026-05-25", "2026-05-22"),
            HOLIDAYS,
            "date row 2 is 2026-05-25, a holiday, expected a business day",
        ),
        (
            dates("2026-05-25"),
            HOLIDAYS,
            "date row 1 is 2026-05-25, a holiday, expected a business day",
        ),
        (
            dates("2026-05-06", "2026-05-04", "2026-05-01"),
            HOLIDAYS,
            "date row 2 is 2026-05-04, expected 2026-05-05, "
            "the business day before row 1's 2026-05-06",
        ),
        (
            dates("2026-05-05", "2026-05-01"),
            HOLIDAYS,
            "date row 2 is 2026-05-01, expected 2026-05-04, "
            "the business day before row 1's 2026-05-05",
        ),
        (
            dates("2026-05-27", "2026-05-22"),
            HOLIDAYS,
            "date row 2 is 2026-05-22, expected 2026-05-26, "
            "the business day before row 1's 2026-05-27",
        ),
        (
            dates("2026-05-07", "2026-05-05", "2026-05-01"),
            HOLIDAYS,
            "date row 2 is 2026-05-05, expected 2026-05-06, "
            "the business day before row 1's 2026-05-07",
        ),
        (
            dates("2026-05-06", "2026-05-04", "2026-05-01"),
            ELSEWHERE,
            "date row 2 is 2026-05-04, expected 2026-05-05, "
            "the business day before row 1's 2026-05-06",
        ),
        (
            dates("2026-05-02", "2026-05-01"),
            ELSEWHERE,
            "date row 1 is 2026-05-02, a Saturday, expected a business day",
        ),
        (
            dates("2026-05-26", "2026-05-22"),
            ELSEWHERE,
            "date row 2 is 2026-05-22, expected 2026-05-25, "
            "the business day before row 1's 2026-05-26",
        ),
        (
            dates("2026-05-02", "2026-05-01"),
            dates("2026-05-02"),
            "date row 1 is 2026-05-02, a Saturday, expected a business day",
        ),
        (
            dates("2026-05-01", "2026-05-02"),
            HOLIDAYS,
            "date row 2 is 2026-05-02, expected a date before row 1's 2026-05-01",
        ),
        (
            dates("2026-05-25", "2026-05-22", "2026-05-26"),
            HOLIDAYS,
            "date row 3 is 2026-05-26, expected a date before row 2's 2026-05-22",
        ),
        (
            dates("2026-05-06", "2026-05-02", "2026-05-01"),
            HOLIDAYS,
            "date row 2 is 2026-05-02, a Saturday, expected a business day",
        ),
        (
            dates("2026-05-07", "2026-05-05", "2026-05-02"),
            HOLIDAYS,
            "date row 3 is 2026-05-02, a Saturday, expected a business day",
        ),
    ],
    ids=[
        "two dates swapped at the top",
        "a date twice",
        "oldest first, as the series was once given",
        "two dates swapped at the bottom",
        "a Saturday first",
        "a Sunday last",
        "a holiday between",
        "a holiday alone",
        "a weekday missing",
        "the Monday after a weekend missing",
        "the day after a holiday missing",
        "two days missing, the first from the top named",
        "a weekday missing with the calendar's day elsewhere",
        "a Saturday with the calendar's day elsewhere",
        "the 25th of May is a business day when the calendar does not list it",
        "a Saturday listed as a holiday is a Saturday",
        "the order is checked before the calendar, on one row",
        "an order failure lower down is reported before a holiday in the first row",
        "the calendar is checked before the gaps",
        "a Saturday lower down is reported before a gap nearer the top",
    ],
)
def test_a_series_that_cannot_be_made_says_why(
    given: NDArray[np.datetime64], calendar: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        futures_fixings(given, SETTLES[: len(given)], an_index(calendar))
    assert str(failure.value) == message


# --- what is rejected, naming the count ---------------------------------------


@pytest.mark.parametrize(
    ("given", "given_settles", "message"),
    [
        (DATES, SETTLES[:3], "settle has 3 rows, expected 4, one per date"),
        (
            DATES,
            np.vstack([SETTLES, [[90.0]]]),
            "settle has 5 rows, expected 4, one per date",
        ),
        (DATES, SETTLES[:1], "settle has 1 row, expected 4, one per date"),
        (DATES[:1], SETTLES, "settle has 4 rows, expected 1, one per date"),
        (
            dates("2026-05-01", "2026-05-04"),
            SETTLES[:1],
            "settle has 1 row, expected 2, one per date",
        ),
    ],
    ids=[
        "a settle column one row short",
        "a settle column one row long",
        "one settle for four dates",
        "four settles for one date",
        "the count is checked before the order",
    ],
)
def test_a_settle_column_that_does_not_match_the_dates_says_why(
    given: NDArray[np.datetime64], given_settles: NDArray[np.float64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        futures_fixings(given, given_settles, an_index(HOLIDAYS))
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


# Any run of business days under any calendar, given newest first: from a start rolled forward
# to a business day, the count of business days after it, none skipped, read from the last back
# to the first, is a series that is kept whole, oldest first, each settle beside its own day.
@settings(deadline=None)
@given(count=st.integers(1, 300), data=st.data())
def test_any_run_of_business_days_and_their_settles_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    start = np.datetime64("2000-01-01") + np.timedelta64(data.draw(st.integers(0, 36_000)), "D")
    listed = data.draw(st.lists(st.integers(-30, 500), max_size=40))
    holidays = start + np.array(listed, dtype="timedelta64[D]")
    calendar = np.busdaycalendar(holidays=holidays)
    run = np.busday_offset(start, np.arange(count), roll="forward", busdaycal=calendar)
    run_settles = np.array(
        data.draw(st.lists(st.floats(-1e6, 1e6), min_size=count, max_size=count)), dtype=np.float64
    )
    fixings = futures_fixings(run[::-1], run_settles[::-1, None], an_index(holidays))
    assert np.array_equal(fixings.dates, run)
    assert np.array_equal(fixings.settles[:, 0], run_settles)


# Any such run given oldest first, of two rows or more, is refused at its second row: one
# direction is taken, and the other is never sorted into it.
@settings(deadline=None)
@given(count=st.integers(2, 300), data=st.data())
def test_any_run_given_oldest_first_is_refused_at_its_second_row(
    count: int, data: st.DataObject
) -> None:
    start = np.datetime64("2000-01-01") + np.timedelta64(data.draw(st.integers(0, 36_000)), "D")
    listed = data.draw(st.lists(st.integers(-30, 500), max_size=40))
    holidays = start + np.array(listed, dtype="timedelta64[D]")
    calendar = np.busdaycalendar(holidays=holidays)
    run = np.busday_offset(start, np.arange(count), roll="forward", busdaycal=calendar)
    with pytest.raises(ValueError) as failure:
        futures_fixings(run, np.zeros((count, 1)), an_index(holidays))
    assert str(failure.value) == (
        f"date row 2 is {run[1]}, expected a date before row 1's {run[0]}"
    )


# Any such run with one day left out fails at the row below the gap, as the sheet counts its
# rows from the newest down, naming the missing day.
@settings(deadline=None)
@given(count=st.integers(3, 300), data=st.data())
def test_a_run_of_business_days_with_one_left_out_names_the_missing_day(
    count: int, data: st.DataObject
) -> None:
    start = np.datetime64("2000-01-01") + np.timedelta64(data.draw(st.integers(0, 36_000)), "D")
    listed = data.draw(st.lists(st.integers(-30, 500), max_size=40))
    holidays = start + np.array(listed, dtype="timedelta64[D]")
    calendar = np.busdaycalendar(holidays=holidays)
    run = np.busday_offset(start, np.arange(count), roll="forward", busdaycal=calendar)
    left_out = data.draw(st.integers(1, count - 2))
    newest_first = np.delete(run, left_out)[::-1]
    with pytest.raises(ValueError) as failure:
        futures_fixings(newest_first, np.zeros((count - 1, 1)), an_index(holidays))
    assert str(failure.value) == (
        f"date row {count - left_out} is {run[left_out - 1]}, expected {run[left_out]}, "
        f"the business day before row {count - left_out - 1}'s {run[left_out + 1]}"
    )


# --- ownership ----------------------------------------------------------------


# The builder leaves what it was given as it was, in its order and writable, and keeps columns
# of its own: a later change to an input changes no fixing, and what is kept refuses writes.
def test_the_fixings_own_their_columns_and_leave_the_inputs_as_given() -> None:
    given_dates, given_settles = DATES.copy(), SETTLES.copy()
    fixings = futures_fixings(given_dates, given_settles, an_index(HOLIDAYS))
    assert np.array_equal(given_dates, DATES) and np.array_equal(given_settles, SETTLES)
    assert given_dates.flags.writeable and given_settles.flags.writeable
    assert not np.shares_memory(fixings.dates, given_dates)
    assert not np.shares_memory(fixings.settles, given_settles)
    given_dates[-1] = np.datetime64("2030-01-01")
    given_settles[-1] = 0.0
    assert fixings.dates[0] == np.datetime64("2026-05-01")
    assert fixings.settles[0, 0] == 101.94
    assert fixings.dates.flags.owndata and fixings.dates.flags.c_contiguous
    assert fixings.settles.flags.owndata and fixings.settles.flags.c_contiguous
    assert not fixings.dates.flags.writeable
    assert not fixings.settles.flags.writeable
    with pytest.raises(ValueError):
        fixings.settles[0] = 0.0


# --- a column for each nearby, nearby-selection.md ------------------------------


# The settles as a grid, a row per day and a column per nearby, the prompt's first: kept oldest
# first as a series of one column is, each row of settles still beside its own day.
def test_a_wider_grid_keeps_a_column_for_each_nearby_beside_its_day() -> None:
    grid = np.array([[95.08, 96.0], [102.27, 103.0], [106.42, 107.0], [101.94, 102.5]])
    fixings = futures_fixings(DATES, grid, an_index(HOLIDAYS))
    assert fixings.settles.shape == (4, 2)
    assert fixings.settles[:, 0].tolist() == [101.94, 106.42, 102.27, 95.08]
    assert fixings.settles[:, 1].tolist() == [102.5, 107.0, 103.0, 96.0]
    assert fixings.settles.flags.owndata and fixings.settles.flags.c_contiguous
    assert not fixings.settles.flags.writeable and not np.shares_memory(fixings.settles, grid)
    one_day = futures_fixings(DATES[:1], grid[:1], an_index(HOLIDAYS))
    assert one_day.settles.tolist() == [[95.08, 96.0]]


# The rows are counted against the dates whatever the width: a row of settles where a column of
# them should be is one row, refused by the count.
def test_a_grids_rows_are_counted_against_the_dates_whatever_its_width() -> None:
    across = np.array([[95.08, 102.27, 106.42, 101.94]])
    with pytest.raises(ValueError) as failure:
        futures_fixings(DATES, across, an_index(HOLIDAYS))
    assert str(failure.value) == "settle has 1 row, expected 4, one per date"
    with pytest.raises(ValueError) as failure:
        futures_fixings(DATES, np.ones((3, 2)), an_index(HOLIDAYS))
    assert str(failure.value) == "settle has 3 rows, expected 4, one per date"


# Any run of the index's business days with any number of nearbys beside it, given newest first:
# kept oldest first, every row of settles beside its own day and every column in its place. The
# run skips the one day the index is closed, as the calendar it is checked against does.
@settings(deadline=None)
@given(count=st.integers(1, 120), nearbys=st.integers(1, 5), data=st.data())
def test_any_grid_of_settles_is_kept_row_for_row_and_column_for_column(
    count: int, nearbys: int, data: st.DataObject
) -> None:
    start = np.datetime64("2000-01-01") + np.timedelta64(data.draw(st.integers(0, 36_000)), "D")
    run = np.busday_offset(start, np.arange(count), roll="forward", holidays=ELSEWHERE)
    grid = np.array(
        data.draw(
            st.lists(
                st.lists(st.floats(-1e6, 1e6), min_size=nearbys, max_size=nearbys),
                min_size=count,
                max_size=count,
            )
        ),
        dtype=np.float64,
    )
    fixings = futures_fixings(run[::-1], grid[::-1], an_index(ELSEWHERE))
    assert np.array_equal(fixings.dates, run)
    assert np.array_equal(fixings.settles, grid)
