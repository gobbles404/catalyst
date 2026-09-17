"""The holiday calendar: the column retained as typed and as given, and nothing checked."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from goosedove.index_definitions.holiday_calendar import holiday_calendar

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
