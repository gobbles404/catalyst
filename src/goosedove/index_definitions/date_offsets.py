"""A date shifted by a text offset, as the desk writes one: `+1bd`, the next business day; `-1bd`,
the one before; `+7cd`, a week of calendar days on; `+0em`, the last day of the date's month and
`+1em` the next month's. One date and one instruction in, one date out, no object and no handle;
the business days are Monday to Friday less the holidays of a calendar the desk may give, and
nothing else of the library is read. docs/library/utilities/shift-date.md is the page."""

import re
from enum import Enum
from typing import Final, assert_never

import numpy as np

from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.sheet_days import SHEET_FIRST_DAY, SHEET_LAST_DAY

# The one form an offset takes, in the words a message offers.
FORMS: Final = "a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd or +0em"
# A sign, ASCII digits and two letters, read whole: no space, no decimal, no second instruction.
_OFFSET: Final = re.compile(r"([+-])([0-9]+)([A-Za-z]{2})")
# The most digits a count may have once its leading zeros are dropped: the sheet's calendar is
# 2,958,404 days, 2,113,146 business days and 97,197 month ends end to end, each a seven-digit
# count, so an eighth digit names no day a cell can show and is refused before any arithmetic,
# or Python's own conversion, could run over it.
MOST_DIGITS: Final = 7
# No holidays, for the business days of a date shifted without a calendar: numpy takes an array
# of days here and no absence of one.
NO_HOLIDAYS: Final = np.array([], dtype="datetime64[D]")
NO_HOLIDAYS.setflags(write=False)


class Unit(Enum):
    """What the count counts: business days, calendar days or month ends."""

    BUSINESS_DAYS = "bd"
    CALENDAR_DAYS = "cd"
    MONTH_ENDS = "em"


def shift_date(date: np.datetime64, offset: str, holidays: HolidayCalendar | None) -> np.datetime64:
    """The date the offset names from the one given.

    The offset is one sign, one whole count in ASCII digits, leading zeros allowed, and `bd`,
    `cd` or `em` in either case, nothing before, between or after; anything else is refused
    naming what arrived and the form wanted. Business days are counted strictly from the date
    without including it, on the calendar's days, Monday to Friday less the holidays given, or
    less none when no calendar is: a date that is itself closed steps back to the last open day
    before counting forward and on to the first open day before counting back, so Saturday
    `+1bd` is Monday and Sunday `-1bd` is Friday, and a zero count is the date itself, closed or
    not. Calendar days count weekends and holidays alike. Month ends move the date's month by the
    count and take that month's last day, `+0em` the date's own month's, through the first day
    of the month after, less one day, so February's length falls out of numpy. The holidays serve
    the business days alone. The day made is held to the sheet's calendar, 1 March 1900 to 31
    December 9999, and refused naming the date and the offset when it leaves it; a count of more
    than seven digits is refused by its digits, before any arithmetic, since no such day exists.
    """
    found = _OFFSET.fullmatch(offset)
    if found is None:
        raise ValueError(f"offset is {offset!r}, expected {FORMS}")
    sign, digits, suffix = found.groups()
    try:
        unit = Unit(suffix.lower())
    except ValueError:
        raise ValueError(f"offset is {offset!r}, expected {FORMS}") from None
    significant = len(digits.lstrip("0"))
    if significant > MOST_DIGITS:
        raise ValueError(
            f"offset has a count of {significant} digits, expected at most {MOST_DIGITS}; the "
            f"sheet's calendar runs {SHEET_FIRST_DAY} to {SHEET_LAST_DAY}"
        )
    count = int(digits) if sign == "+" else -int(digits)
    match unit:
        case Unit.BUSINESS_DAYS:
            shifted = _business_days_on(date, count, holidays)
        case Unit.CALENDAR_DAYS:
            shifted = date + np.timedelta64(count, "D")
        case Unit.MONTH_ENDS:
            month_after = date.astype("datetime64[M]") + np.timedelta64(count + 1, "M")
            shifted = month_after.astype("datetime64[D]") - np.timedelta64(1, "D")
        case _:
            assert_never(unit)
    if shifted < SHEET_FIRST_DAY or shifted > SHEET_LAST_DAY:
        raise ValueError(
            f"date {date} shifted by {offset!r} is {shifted}, outside the sheet's calendar, "
            f"{SHEET_FIRST_DAY} to {SHEET_LAST_DAY}"
        )
    return shifted


def _business_days_on(
    date: np.datetime64, count: int, holidays: HolidayCalendar | None
) -> np.datetime64:
    """The count-th business day after the date, or before it for a negative count, the date
    itself for zero: one numpy offset, the closed date rolled back before counting forward and
    forward before counting back, so that the first business day after a closed day is the next
    open day and not the one after it."""
    if count == 0:
        return date
    listed = NO_HOLIDAYS if holidays is None else holidays.holiday
    roll = "backward" if count > 0 else "forward"
    return np.busday_offset(date, count, roll=roll, holidays=listed)
