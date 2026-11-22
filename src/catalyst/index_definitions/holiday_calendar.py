"""A holiday calendar: its name, the word a holiday key selects it by, and the days one market
is closed, listed one by one as the desk keeps them; and the union of calendars, closed on every
day any of them is closed, which a key of several names makes, holiday-keys.md.
docs/library/index-definitions/holiday-calendar.md is the page."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from catalyst.globals.discount_curve import curve_name
from catalyst.instrumentation.work_counts import WorkCounter

# The work a union reports: the calendars taken, the listed days read from them and the distinct
# days kept.
CALENDARS_COMBINED: Final = "calendars_combined"
HOLIDAYS_READ: Final = "holidays_read"
HOLIDAYS_KEPT: Final = "holidays_kept"


@dataclass(frozen=True, slots=True)
class HolidayCalendar:
    """The name, the word a holiday key selects the calendar by, NYFED, or for a union its
    members' names joined by a plus sign, LON+NYFED; and the holidays, read-only: one calendar
    day per row, as the desk listed them, in the order given. A day listed twice is listed
    twice, and a weekend day listed is kept."""

    name: str
    holiday: NDArray[np.datetime64]


# The mark that joins calendar names in a holiday key, NYFED+LON, so no typed name holds it.
JOIN: Final = "+"


def calendar_name(where: str, text: str) -> str:
    """The rule on a calendar's name: the curve name's rule, text with no whitespace around it
    and not whitespace alone, since a key matches a name exactly, case and all; and no plus
    sign, which joins names in a key, so a name holding one could be selected by no key.
    Refused in the words of where it stands; the text itself otherwise."""
    curve_name(where, text)
    if JOIN in text:
        raise ValueError(
            f"{where} is {text!r}, expected a name without '+', which joins names in a key"
        )
    return text


def holiday_calendar(name: str, holiday: NDArray[np.datetime64]) -> HolidayCalendar:
    """The one way to make a HolidayCalendar from the desk's list. The name is held to
    calendar_name. The days have no rule of meaning: a calendar is the days the desk listed,
    and what a reader needs of them, whether they repeat or increase, is that reader's rule,
    written when the reader is.

    The column is copied and then frozen, so the calendar owns its data: a Python caller keeps
    whatever it passed, and a later change to an input never changes a calendar.
    """
    return _owning(calendar_name("name", name), holiday)


def combine_holiday_calendars(
    calendars: Sequence[HolidayCalendar], counter: WorkCounter
) -> HolidayCalendar:
    """One calendar closed on every day any of the given calendars is closed, the union a
    holiday key of several names selects: their listed days taken together and the distinct
    days kept in chronological order, once each, a day two calendars list or one lists twice
    kept once and a weekend day listed kept as any other, since a reader's business days leave
    the weekend out already. The sources are read and left as they are, their order and repeats
    with them; the result owns its days and is named by its sources' names in the order given,
    joined by the plus sign that joined them in the key, LON+NYFED. One calendar follows the
    same path as many. Counts the calendars taken, the listed days read and the distinct days
    kept.
    """
    counter.hit(CALENDARS_COMBINED, len(calendars))
    listed = np.concatenate([calendar.holiday for calendar in calendars])
    counter.hit(HOLIDAYS_READ, int(listed.size))
    kept = np.unique(listed)
    counter.hit(HOLIDAYS_KEPT, int(kept.size))
    return _owning(JOIN.join([calendar.name for calendar in calendars]), kept)


def _owning(name: str, holiday: NDArray[np.datetime64]) -> HolidayCalendar:
    days = np.array(holiday, dtype="datetime64[D]")
    days.setflags(write=False)
    return HolidayCalendar(name, days)
