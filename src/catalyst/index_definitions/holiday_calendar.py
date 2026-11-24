"""A holiday calendar: the days one market is closed, listed one by one as the desk keeps them,
since #183 the combination of calendars, closed on every day any of them is closed, and since
payment-calendar-keys.md the name a calendar may carry, the word a trade's payment calendar
key selects it by. docs/library/index-definitions/holiday-calendar.md and
combine-holiday-calendars.md are the pages."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from catalyst.globals.discount_curve import curve_name
from catalyst.instrumentation.work_counts import WorkCounter

# The work a combination reports, combine-holiday-calendars.md: the calendars taken, the listed
# days read from them and the distinct days kept.
CALENDARS_COMBINED: Final = "calendars_combined"
HOLIDAYS_READ: Final = "holidays_read"
HOLIDAYS_KEPT: Final = "holidays_kept"


@dataclass(frozen=True, slots=True)
class HolidayCalendar:
    """The holidays, read-only: one calendar day per row, as the desk listed them, in the order
    given. A day listed twice is listed twice, and a weekend day listed is kept. And the name,
    since payment-calendar-keys.md: the word a payment calendar key selects the calendar by,
    NYFED, or None for a calendar nobody selects by name, an index's pricing calendar or a
    combination."""

    holiday: NDArray[np.datetime64]
    name: str | None


# The mark that joins calendar names in a payment calendar key, NYFED+LON, so no name holds it.
JOIN: Final = "+"


def calendar_name(where: str, text: str) -> str:
    """The rule on a calendar's name, payment-calendar-keys.md: the curve name's rule, text with
    no whitespace around it and not whitespace alone, since a key matches a name exactly, case
    and all; and no plus sign, which joins names in a key, so a name holding one could be
    selected by no key. Refused in the words of where it stands; the text itself otherwise."""
    curve_name(where, text)
    if JOIN in text:
        raise ValueError(
            f"{where} is {text!r}, expected a name without '+', which joins names in a key"
        )
    return text


def holiday_calendar(holiday: NDArray[np.datetime64], name: str | None = None) -> HolidayCalendar:
    """The one way to make a HolidayCalendar. The days have no rule of meaning: a calendar is the
    days the desk listed, and what a reader needs of them, whether they repeat or increase, is
    that reader's rule, written when the reader is. A name, where one is given, is held to
    calendar_name; none is no name, the calendar an index prices on or a date utility counts on.

    The column is copied and then frozen, so the calendar owns its data: a Python caller keeps
    whatever it passed, and a later change to an input never changes a calendar.
    """
    if name is not None:
        calendar_name("name", name)
    days = np.array(holiday, dtype="datetime64[D]")
    days.setflags(write=False)
    return HolidayCalendar(days, name)


def combine_holiday_calendars(
    calendars: Sequence[HolidayCalendar], counter: WorkCounter
) -> HolidayCalendar:
    """One calendar closed on every day any of the given calendars is closed, since #183,
    combine-holiday-calendars.md: their listed days taken together and the distinct days kept
    in chronological order, once each, a day two calendars list or one lists twice kept once
    and a weekend day listed kept as any other, since a reader's business days leave the
    weekend out already. The sources are read and left as they are, their order and repeats
    with them; the result is an ordinary calendar owning its days through holiday_calendar,
    so a combination is itself an input to another, and has no name, whatever its sources'.
    One calendar follows the same path as many. Counts the calendars taken, the listed days
    read and the distinct days kept.
    """
    counter.hit(CALENDARS_COMBINED, len(calendars))
    listed = np.concatenate([calendar.holiday for calendar in calendars])
    counter.hit(HOLIDAYS_READ, int(listed.size))
    kept = np.unique(listed)
    counter.hit(HOLIDAYS_KEPT, int(kept.size))
    return holiday_calendar(kept)
