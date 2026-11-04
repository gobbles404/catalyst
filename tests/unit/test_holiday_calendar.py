"""The holiday calendar: the column retained as typed and as given, and nothing checked; since
#183 the combination of calendars, the distinct days of all of them in order."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from catalyst.index_definitions.holiday_calendar import (
    CALENDARS_COMBINED,
    HOLIDAYS_KEPT,
    HOLIDAYS_READ,
    HolidayCalendar,
    combine_holiday_calendars,
    holiday_calendar,
)
from catalyst.instrumentation.work_counts import WorkCounter

EPOCH = np.datetime64("1899-12-30")


def dates(*texts: str) -> NDArray[np.datetime64]:
    return np.array(texts, dtype="datetime64[D]")


# The page's sample: the ten days one market is closed in 2026, as the desk listed them.
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


# --- what is kept -------------------------------------------------------------


def test_the_sample_keeps_every_holiday_as_given() -> None:
    calendar = holiday_calendar(HOLIDAYS)
    assert np.array_equal(calendar.holiday, HOLIDAYS)
    assert calendar.holiday.dtype == np.dtype("datetime64[D]")
    assert calendar.holiday.ndim == 1


def test_a_one_row_calendar_is_a_calendar() -> None:
    calendar = holiday_calendar(HOLIDAYS[:1])
    assert np.array_equal(calendar.holiday, dates("2026-01-01"))


# A day listed twice, days out of order, a Saturday among them: a reader's rules, written when
# the reader is. The calendar keeps them as given.
def test_nothing_else_is_checked() -> None:
    listed = dates("2026-12-25", "2026-01-01", "2026-01-01", "2026-01-03")
    calendar = holiday_calendar(listed)
    assert np.array_equal(calendar.holiday, listed)


# --- the general rule ---------------------------------------------------------


@given(serials=st.lists(st.integers(61, 2958465), min_size=1, max_size=400))
def test_any_column_of_dates_is_kept_as_given(serials: list[int]) -> None:
    listed = EPOCH + np.array(serials).astype("timedelta64[D]")
    calendar = holiday_calendar(listed)
    assert calendar.holiday.size == len(serials)
    assert np.array_equal(calendar.holiday, listed)


# --- ownership ----------------------------------------------------------------


def test_the_calendar_owns_its_dates() -> None:
    listed = HOLIDAYS.copy()
    calendar = holiday_calendar(listed)
    listed[0] = np.datetime64("2030-01-01")
    assert calendar.holiday[0] == np.datetime64("2026-01-01")
    assert not calendar.holiday.flags.writeable
    with pytest.raises(ValueError):
        calendar.holiday[0] = np.datetime64("2030-01-01")


# --- the combination, combine-holiday-calendars.md ------------------------------------------------

# The ticket's synthetic calendars: A lists Wednesday 14 October 2026 twice around Monday the 12th,
# B Tuesday the 13th and the 14th. Neither claims any exchange's rules.
A = holiday_calendar(dates("2026-10-14", "2026-10-12", "2026-10-14"))
B = holiday_calendar(dates("2026-10-13", "2026-10-14"))
UNION = dates("2026-10-12", "2026-10-13", "2026-10-14")


def combined(*calendars: HolidayCalendar) -> tuple[HolidayCalendar, dict[str, int]]:
    counter = WorkCounter()
    return combine_holiday_calendars(calendars, counter), counter.freeze().as_dict()


def test_the_tickets_two_calendars_combine_into_their_three_distinct_days_in_order() -> None:
    calendar, counts = combined(A, B)
    assert np.array_equal(calendar.holiday, UNION)
    assert calendar.holiday.dtype == np.dtype("datetime64[D]")
    # Two calendars taken, five listed days read, three distinct days kept.
    assert counts == {CALENDARS_COMBINED: 2, HOLIDAYS_READ: 5, HOLIDAYS_KEPT: 3}
    # The same days as a calendar the desk listed as the union itself.
    assert np.array_equal(calendar.holiday, holiday_calendar(UNION).holiday)


def test_one_calendar_combines_into_its_own_distinct_days_in_order() -> None:
    calendar, counts = combined(A)
    assert np.array_equal(calendar.holiday, dates("2026-10-12", "2026-10-14"))
    assert counts == {CALENDARS_COMBINED: 1, HOLIDAYS_READ: 3, HOLIDAYS_KEPT: 2}


def test_order_repeats_and_overlaps_change_nothing_and_a_combination_combines_again() -> None:
    for calendars in ((B, A), (A, B, A), (B, B, A, B)):
        calendar, counts = combined(*calendars)
        assert np.array_equal(calendar.holiday, UNION)
        assert counts[CALENDARS_COMBINED] == len(calendars)
        assert counts[HOLIDAYS_KEPT] == 3
    # A calendar combined with itself is its own distinct days, read twice and kept once.
    twice, counts = combined(A, A)
    assert np.array_equal(twice.holiday, dates("2026-10-12", "2026-10-14"))
    assert counts == {CALENDARS_COMBINED: 2, HOLIDAYS_READ: 6, HOLIDAYS_KEPT: 2}
    # Nested: the combination of a combination and a third calendar is the combination of all three.
    saturday = holiday_calendar(dates("2026-10-10"))  # a weekend day listed is kept as any other
    first, _ = combined(A, B)
    nested, counts = combined(first, saturday)
    flat, _ = combined(A, B, saturday)
    assert np.array_equal(nested.holiday, flat.holiday)
    assert np.array_equal(
        nested.holiday, dates("2026-10-10", "2026-10-12", "2026-10-13", "2026-10-14")
    )
    assert counts == {CALENDARS_COMBINED: 2, HOLIDAYS_READ: 4, HOLIDAYS_KEPT: 4}


def test_the_sources_are_left_as_they_are_and_the_combination_owns_its_days() -> None:
    calendar, _ = combined(A, B)
    assert np.array_equal(A.holiday, dates("2026-10-14", "2026-10-12", "2026-10-14"))
    assert np.array_equal(B.holiday, dates("2026-10-13", "2026-10-14"))
    assert not calendar.holiday.flags.writeable
    with pytest.raises(ValueError):
        calendar.holiday[0] = np.datetime64("2030-01-01")
    assert not np.shares_memory(calendar.holiday, A.holiday)
    assert not np.shares_memory(calendar.holiday, B.holiday)


@given(
    columns=st.lists(
        st.lists(st.integers(61, 2958465), min_size=1, max_size=40), min_size=1, max_size=6
    )
)
def test_any_calendars_combine_into_the_distinct_days_of_all_of_them_whatever_the_order(
    columns: list[list[int]],
) -> None:
    calendars = [
        holiday_calendar(EPOCH + np.array(serials).astype("timedelta64[D]")) for serials in columns
    ]
    calendar, counts = combined(*calendars)
    every = np.concatenate([c.holiday for c in calendars])
    assert np.array_equal(calendar.holiday, np.unique(every))
    assert np.all(calendar.holiday[1:] > calendar.holiday[:-1])
    reversed_order, _ = combined(*reversed(calendars))
    assert np.array_equal(reversed_order.holiday, calendar.holiday)
    assert counts == {
        CALENDARS_COMBINED: len(calendars),
        HOLIDAYS_READ: int(every.size),
        HOLIDAYS_KEPT: int(calendar.holiday.size),
    }
