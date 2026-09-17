"""The daily fixings: the three rules of meaning, and the columns retained and aligned."""

import numpy as np
import pytest
from hypothesis import given, settings
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


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_date_and_settle_aligned() -> None:
    fixings = daily_fixings(DATES, SETTLES, HOLIDAYS)
    assert np.array_equal(fixings.dates, DATES)
    assert fixings.settles.tolist() == [101.94, 106.42, 102.27, 95.08]
    assert fixings.dates.dtype == np.dtype("datetime64[D]")
    assert fixings.settles.dtype == np.dtype("float64")


def test_one_fixing_is_a_series() -> None:
    fixings = daily_fixings(DATES[:1], SETTLES[:1], HOLIDAYS)
    assert np.array_equal(fixings.dates, DATES[:1])
    assert fixings.settles.tolist() == [101.94]


# Friday 22 May to Tuesday 26 May 2026: the weekend and the holiday on the Monday are the days
# without a fixing, and the series is whole without them.
def test_a_weekend_and_a_listed_holiday_are_the_days_without_a_fixing() -> None:
    given = dates("2026-05-22", "2026-05-26")
    fixings = daily_fixings(given, SETTLES[:2], HOLIDAYS)
    assert np.array_equal(fixings.dates, given)


# Tuesday 5 May to Thursday 7 May: the Monday before and the Friday after are business days,
# and neither is asked for, since the first and last dates bound the check.
def test_nothing_is_asked_for_before_the_first_date_or_after_the_last() -> None:
    given = dates("2026-05-05", "2026-05-06", "2026-05-07")
    fixings = daily_fixings(given, SETTLES[:3], HOLIDAYS)
    assert np.array_equal(fixings.dates, given)


# A settle at or below zero is kept as given. WTI's May 2020 contract settled at minus 37.63
# on Monday 20 April 2020.
def test_a_settle_at_or_below_zero_is_kept() -> None:
    fixings = daily_fixings(
        dates("2020-04-20", "2020-04-21", "2020-04-22"), settles(-37.63, 0.0, 39.27), HOLIDAYS
    )
    assert fixings.settles.tolist() == [-37.63, 0.0, 39.27]


# A day listed twice counts once, and a day listed on a weekend adds nothing: the calendar is
# read as numpy reads it, and the series that is whole without those days is whole with them.
def test_a_holiday_listed_twice_or_on_a_weekend_changes_nothing() -> None:
    calendar = dates("2026-05-25", "2026-05-25", "2026-05-02", "2026-05-03")
    fixings = daily_fixings(DATES, SETTLES, calendar)
    assert np.array_equal(fixings.dates, DATES)
    fixings = daily_fixings(dates("2026-05-22", "2026-05-26"), SETTLES[:2], calendar)
    assert fixings.dates.tolist() == [np.datetime64("2026-05-22"), np.datetime64("2026-05-26")]


# --- what is rejected, naming the row -----------------------------------------


@pytest.mark.parametrize(
    ("given", "calendar", "message"),
    [
        (
            dates("2026-05-04", "2026-05-01", "2026-05-05", "2026-05-06"),
            HOLIDAYS,
            "date row 2 is 2026-05-01, expected a date after row 1's 2026-05-04",
        ),
        (
            dates("2026-05-01", "2026-05-04", "2026-05-04", "2026-05-06"),
            HOLIDAYS,
            "date row 3 is 2026-05-04, expected a date after row 2's 2026-05-04",
        ),
        (
            dates("2026-05-06", "2026-05-05", "2026-05-04", "2026-05-01"),
            HOLIDAYS,
            "date row 2 is 2026-05-05, expected a date after row 1's 2026-05-06",
        ),
        (
            dates("2026-05-02", "2026-05-04"),
            HOLIDAYS,
            "date row 1 is 2026-05-02, a Saturday, expected a business day",
        ),
        (
            dates("2026-05-08", "2026-05-10"),
            HOLIDAYS,
            "date row 2 is 2026-05-10, a Sunday, expected a business day",
        ),
        (
            dates("2026-05-22", "2026-05-25", "2026-05-26"),
            HOLIDAYS,
            "date row 2 is 2026-05-25, a holiday, expected a business day",
        ),
        (
            dates("2026-05-25"),
            HOLIDAYS,
            "date row 1 is 2026-05-25, a holiday, expected a business day",
        ),
        (
            dates("2026-05-01", "2026-05-04", "2026-05-06"),
            HOLIDAYS,
            "date row 3 is 2026-05-06, expected 2026-05-05, "
            "the business day after row 2's 2026-05-04",
        ),
        (
            dates("2026-05-01", "2026-05-05"),
            HOLIDAYS,
            "date row 2 is 2026-05-05, expected 2026-05-04, "
            "the business day after row 1's 2026-05-01",
        ),
        (
            dates("2026-05-22", "2026-05-27"),
            HOLIDAYS,
            "date row 2 is 2026-05-27, expected 2026-05-26, "
            "the business day after row 1's 2026-05-22",
        ),
        (
            dates("2026-05-01", "2026-05-04", "2026-05-06"),
            ELSEWHERE,
            "date row 3 is 2026-05-06, expected 2026-05-05, "
            "the business day after row 2's 2026-05-04",
        ),
        (
            dates("2026-05-01", "2026-05-02"),
            ELSEWHERE,
            "date row 2 is 2026-05-02, a Saturday, expected a business day",
        ),
        (
            dates("2026-05-22", "2026-05-26"),
            ELSEWHERE,
            "date row 2 is 2026-05-26, expected 2026-05-25, "
            "the business day after row 1's 2026-05-22",
        ),
        (
            dates("2026-05-01", "2026-05-02"),
            dates("2026-05-02"),
            "date row 2 is 2026-05-02, a Saturday, expected a business day",
        ),
        (
            dates("2026-05-02", "2026-05-01"),
            HOLIDAYS,
            "date row 2 is 2026-05-01, expected a date after row 1's 2026-05-02",
        ),
        (
            dates("2026-05-01", "2026-05-02", "2026-05-06"),
            HOLIDAYS,
            "date row 2 is 2026-05-02, a Saturday, expected a business day",
        ),
    ],
    ids=[
        "two dates swapped",
        "a date twice",
        "newest first",
        "a Saturday first",
        "a Sunday last",
        "a holiday between",
        "a holiday alone",
        "a weekday missing",
        "the Monday after a weekend missing",
        "the day after a holiday missing",
        "a weekday missing with the calendar's day elsewhere",
        "a Saturday with the calendar's day elsewhere",
        "the 25th of May is a business day when the calendar does not list it",
        "a Saturday listed as a holiday is a Saturday",
        "the order is checked before the calendar",
        "the calendar is checked before the gaps",
    ],
)
def test_a_series_that_cannot_be_made_says_why(
    given: NDArray[np.datetime64], calendar: NDArray[np.datetime64], message: str
) -> None:
    with pytest.raises(ValueError) as failure:
        daily_fixings(given, SETTLES[: len(given)], calendar)
    assert str(failure.value) == message


# --- the general rule ---------------------------------------------------------


# Any run of business days under any calendar: from a start rolled forward to a business day,
# the count of business days after it, none skipped, is a series that is kept whole.
@settings(deadline=None)
@given(count=st.integers(1, 300), data=st.data())
def test_any_run_of_business_days_and_their_settles_are_kept_aligned(
    count: int, data: st.DataObject
) -> None:
    start = np.datetime64("2000-01-01") + np.timedelta64(data.draw(st.integers(0, 36_000)), "D")
    listed = data.draw(st.lists(st.integers(-30, 500), max_size=40))
    holidays = start + np.array(listed, dtype="timedelta64[D]")
    calendar = np.busdaycalendar(holidays=holidays)
    given_dates = np.busday_offset(start, np.arange(count), roll="forward", busdaycal=calendar)
    given_settles = np.array(
        data.draw(st.lists(st.floats(-1e6, 1e6), min_size=count, max_size=count)), dtype=np.float64
    )
    fixings = daily_fixings(given_dates, given_settles, holidays)
    assert np.array_equal(fixings.dates, given_dates)
    assert np.array_equal(fixings.settles, given_settles)


# Any such run with one day left out fails at the row after the gap, naming the missing day.
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
    given = np.delete(run, left_out)
    with pytest.raises(ValueError) as failure:
        daily_fixings(given, np.zeros(count - 1), holidays)
    assert str(failure.value) == (
        f"date row {left_out + 1} is {run[left_out + 1]}, expected {run[left_out]}, "
        f"the business day after row {left_out}'s {run[left_out - 1]}"
    )


# --- ownership ----------------------------------------------------------------


def test_the_fixings_own_their_columns() -> None:
    given_dates, given_settles = DATES.copy(), SETTLES.copy()
    fixings = daily_fixings(given_dates, given_settles, HOLIDAYS)
    given_dates[0] = np.datetime64("2030-01-01")
    given_settles[0] = 0.0
    assert fixings.dates[0] == np.datetime64("2026-05-01")
    assert fixings.settles[0] == 101.94
    assert not fixings.dates.flags.writeable
    assert not fixings.settles.flags.writeable
    with pytest.raises(ValueError):
        fixings.settles[0] = 0.0
