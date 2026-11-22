"""A date shifted by a text offset, as the desk writes one: `+1bd`, the next business day; `-1bd`,
the one before; `+7cd`, a week of calendar days on; `+0em`, the last day of the date's month and
`+1em` the next month's; and since #181 a chain of them, `+3em+25cd-1bd+1bd`, each instruction
applied to the result of the one before, left to right. One date and one offset in, one date out,
no object and no handle; the business days are Monday to Friday less the holidays of a calendar
the desk may choose by key, and nothing else of the library is read. The same reading and the same
arithmetic serve a trade's payment rule, over every component's anchor at once.
docs/library/utilities/shift-date.md is the page."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.holiday_calendars import HolidayCalendars, calendar_of
from catalyst.index_definitions.sheet_days import SHEET_FIRST_DAY, SHEET_LAST_DAY
from catalyst.instrumentation.work_counts import WorkCounter

# The form an offset takes, in the words a message offers.
FORMS: Final = (
    "one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or "
    "+3em+25cd-1bd+1bd"
)
# One instruction: a sign, ASCII digits and two letters, matched where the reading stands, so a
# space, a decimal or a second sign is where the next instruction should begin and is not one.
_INSTRUCTION: Final = re.compile(r"([+-])([0-9]+)([A-Za-z]{2})")
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


@dataclass(frozen=True, slots=True)
class Instruction:
    """One instruction of an offset: its text as written, its unit and its signed count."""

    text: str
    unit: Unit
    count: int


@dataclass(frozen=True, slots=True)
class Shifted:
    """Days shifted by every instruction of an offset: the days reached and, per day, the first
    instruction whose result left the sheet's calendar, -1 where none did, with the day it made,
    so that a caller names the instruction and the day in its own words."""

    days: NDArray[np.datetime64]
    strayed_at: NDArray[np.intp]
    strayed_to: NDArray[np.datetime64]


def read_offset(where: str, offset: str) -> tuple[Instruction, ...]:
    """The instructions of an offset, every one read before any is applied, since #181.

    An offset is one or more instructions, each one sign, one whole count in ASCII digits,
    leading zeros allowed, and `bd`, `cd` or `em` in either case, one after another with nothing
    before, between or after: `+1bd`, `-01BD`, `+3em+25cd-1bd+1bd`. The reading stands at the
    start and takes one instruction at a time; where no instruction begins, the offset is refused
    naming what arrived and the form wanted, and, past the first instruction, the character it
    reached and the text from there, so that a chain malformed late fails whole and names where.
    A count of more than seven significant digits is refused by its digits, before any arithmetic,
    since no such day exists, the instruction named when the offset has more than one. The empty
    text is no offset; the seam refuses it before this. `where` is the words the message begins
    with, `offset` for the utility and the field for a payment rule.
    """
    steps: list[Instruction] = []
    at = 0
    while at < len(offset):
        found = _INSTRUCTION.match(offset, at)
        if found is None:
            raise ValueError(_no_instruction(where, offset, at))
        sign, digits, suffix = found.groups()
        try:
            unit = Unit(suffix.lower())
        except ValueError:
            raise ValueError(_no_instruction(where, offset, at)) from None
        significant = digits.lstrip("0")
        if len(significant) > MOST_DIGITS:
            whole = at == 0 and found.end() == len(offset)
            named = "" if whole else f" in instruction {len(steps) + 1}, {found.group(0)!r}"
            raise ValueError(
                f"{where} has a count of {len(significant)} digits{named}, expected at most "
                f"{MOST_DIGITS}; the sheet's calendar runs {SHEET_FIRST_DAY} to {SHEET_LAST_DAY}"
            )
        magnitude = int(significant or "0")
        steps.append(Instruction(found.group(0), unit, magnitude if sign == "+" else -magnitude))
        at = found.end()
    if not steps:
        raise ValueError(f"{where} is {offset!r}, expected {FORMS}")
    return tuple(steps)


def _no_instruction(where: str, offset: str, at: int) -> str:
    message = f"{where} is {offset!r}, expected {FORMS}"
    if at:
        message += f"; from character {at + 1}, {offset[at:]!r} begins with no instruction"
    return message


def shift_days(
    days: NDArray[np.datetime64], steps: tuple[Instruction, ...], holidays: HolidayCalendar | None
) -> Shifted:
    """Every day shifted by the instructions in turn, each applied to what the one before made,
    as arrays, since #181: the days are a column of anchors or the one date of the utility, and
    each instruction is one numpy operation over all of them. Business days are counted strictly
    from each day without including it, on the calendar's days, Monday to Friday less the
    holidays given, or less none when no calendar is: a day that is itself closed steps back to
    the last open day before counting forward and on to the first open day before counting back,
    so Saturday `+1bd` is Monday and Sunday `-1bd` is Friday, and a zero count is the day itself,
    closed or not. Calendar days count weekends and holidays alike. Month ends move each day's
    month by the count and take that month's last day, `+0em` the day's own month's, through the
    first day of the month after, less one day, so February's length falls out of numpy. The
    holidays serve the business days alone; nothing is netted, reordered or rolled at the end,
    so a chain ending in `cd` or `em` may land on a closed day. After each instruction one look
    says whether any day left the sheet's calendar, 1 March 1900 to 31 December 9999; the first
    such instruction and the day it made are kept per day, the arithmetic running on, since
    numpy's days run far past the sheet's either way and nothing is clipped.

    Work: per instruction one operation over the days and one look; two small arrays per call.
    """
    current: NDArray[np.datetime64] = days
    strayed_at = np.full(days.shape, -1, dtype=np.intp)
    strayed_to = np.full(days.shape, np.datetime64("NaT", "D"))
    for k, step in enumerate(steps):
        match step.unit:
            case Unit.BUSINESS_DAYS:
                current = _business_days_on(current, step.count, holidays)
            case Unit.CALENDAR_DAYS:
                current = current + np.timedelta64(step.count, "D")
            case Unit.MONTH_ENDS:
                month_after = current.astype("datetime64[M]") + np.timedelta64(step.count + 1, "M")
                current = cast(  # the same: a day less a day is a day
                    NDArray[np.datetime64],
                    month_after.astype("datetime64[D]") - np.timedelta64(1, "D"),
                )
            case _:
                assert_never(step.unit)
        outside = (current < SHEET_FIRST_DAY) | (current > SHEET_LAST_DAY)
        if outside.any():
            fresh = outside & (strayed_at < 0)
            strayed_at[fresh] = k
            strayed_to[fresh] = current[fresh]
    return Shifted(current, strayed_at, strayed_to)


def shift_date(
    date: np.datetime64,
    offset: str,
    holiday_key: str | None,
    holiday_calendars: HolidayCalendars | None,
    counter: WorkCounter,
) -> np.datetime64:
    """The date the offset names from the one given: the offset read whole, `read_offset`; then
    the calendar its business days skip, the one the holiday key selects from the collection,
    bound by the step every reader of a key shares, calendar_of, or none for no key, Monday to
    Friday with no holidays; and the instructions applied to the one day, `shift_days`, in
    their order. The day each instruction makes is held to the sheet's calendar, 1 March 1900
    to 31 December 9999, and the first that leaves it is refused naming the date, the offset
    and the day, with the instruction when the offset has more than one, whatever a later
    instruction would have made of it. Work: `holiday_keys_bound`, one for a key, and a
    union's own counts for a key of several names, on every call."""
    steps = read_offset("offset", offset)
    holidays = calendar_of("holiday_key", holiday_key, holiday_calendars, counter)
    shifted = shift_days(np.array([date], dtype="datetime64[D]"), steps, holidays)
    k = int(shifted.strayed_at[0])
    if k >= 0:
        named = "" if len(steps) == 1 else f" at instruction {k + 1}, {steps[k].text!r}"
        raise ValueError(
            f"date {date} shifted by {offset!r} is {shifted.strayed_to[0]}{named}, outside the "
            f"sheet's calendar, {SHEET_FIRST_DAY} to {SHEET_LAST_DAY}"
        )
    return shifted.days[0]


def _business_days_on(
    days: NDArray[np.datetime64], count: int, holidays: HolidayCalendar | None
) -> NDArray[np.datetime64]:
    """The count-th business day after each day, or before it for a negative count, the days
    themselves for zero: one numpy offset, a closed day rolled back before counting forward and
    forward before counting back, so that the first business day after a closed day is the next
    open day and not the one after it."""
    if count == 0:
        return days
    listed = NO_HOLIDAYS if holidays is None else holidays.holiday
    roll = "backward" if count > 0 else "forward"
    return np.busday_offset(days, count, roll=roll, holidays=listed)
