"""A holiday calendar: the days one market is closed, listed one by one as the desk keeps them,
and since #NN the combination of calendars, closed on every day any of them is closed.
docs/library/index-definitions/holiday-calendar.md and combine-holiday-calendars.md are the
pages."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from goosedove.instrumentation.work_counts import WorkCounter

# The work a combination reports, combine-holiday-calendars.md: the calendars taken, the listed
# days read from them and the distinct days kept.
CALENDARS_COMBINED: Final = "calendars_combined"
HOLIDAYS_READ: Final = "holidays_read"
HOLIDAYS_KEPT: Final = "holidays_kept"


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


def combine_holiday_calendars(
    calendars: Sequence[HolidayCalendar], counter: WorkCounter
) -> HolidayCalendar:
    """One calendar closed on every day any of the given calendars is closed, since #NN,
    combine-holiday-calendars.md: their listed days taken together and the distinct days kept
    in chronological order, once each, a day two calendars list or one lists twice kept once
    and a weekend day listed kept as any other, since a reader's business days leave the
    weekend out already. The sources are read and left as they are, their order and repeats
    with them; the result is an ordinary calendar owning its days through holiday_calendar,
    so a combination is itself an input to another. One calendar follows the same path as
    many. Counts the calendars taken, the listed days read and the distinct days kept.
    """
    counter.hit(CALENDARS_COMBINED, len(calendars))
    listed = np.concatenate([calendar.holiday for calendar in calendars])
    counter.hit(HOLIDAYS_READ, int(listed.size))
    kept = np.unique(listed)
    counter.hit(HOLIDAYS_KEPT, int(kept.size))
    return holiday_calendar(kept)
