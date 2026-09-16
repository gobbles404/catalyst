"""A holiday calendar: the days one market is closed, listed one by one as the desk keeps them.
docs/library/market-definitions/holiday-calendar.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class HolidayCalendar:
    """The holidays, read-only: one calendar day per row, as the desk listed them, in the order
    given. A day listed twice is listed twice, and a weekend day listed is kept."""

    holiday: NDArray[np.datetime64]


def holiday_calendar(holiday: NDArray[np.datetime64]) -> HolidayCalendar:
    """The one way to make a HolidayCalendar. It has no rule of meaning: a calendar is the days
    the desk listed, and what a reader needs of them, whether they repeat or increase, is that
    reader's rule, written when the reader is.

    The column is copied and then frozen, so the calendar owns its data: a Python caller keeps
    whatever it passed, and a later change to an input never changes a calendar.
    """
    days = np.array(holiday, dtype="datetime64[D]")
    days.setflags(write=False)
    return HolidayCalendar(days)
