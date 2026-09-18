"""A calendar: every day of one index from the day after its first contract expires to the day
its last expires, the contract prompt on each day, whether the market is open that day and
whether the day is before the valuation date. docs/library/calendar/calendar.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.expiry_schedule import ExpirySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar


@dataclass(frozen=True, slots=True)
class Calendar:
    """The three objects the calendar was built from, kept by reference, and four columns
    aligned by position, all read-only: dates[i] is one calendar day, prompt[i] the row of the
    schedule whose contract is prompt on it, never row 0, is_business_day[i] whether the
    market is open on it, Monday to Friday and not a holiday, and is_past[i] whether it is
    before the valuation date's day. The dates run from the day after the schedule's first
    future expires to the day its last expires, every calendar day between, weekends and
    holidays included. The prompt contract's code is the schedule's, read through the row."""

    valuation_date: ValuationDate
    expiry_schedule: ExpirySchedule
    holiday_calendar: HolidayCalendar
    dates: NDArray[np.datetime64]
    prompt: NDArray[np.intp]
    is_business_day: NDArray[np.bool_]
    is_past: NDArray[np.bool_]


def calendar(
    valuation_date: ValuationDate,
    expiry_schedule: ExpirySchedule,
    holiday_calendar: HolidayCalendar,
) -> Calendar:
    """The one way to make a Calendar: three rules of meaning on the schedule, checked once, in
    this order, the first failure being the message; then the four columns, made once here and
    never again.

    The schedule has two contracts or more, since its first only bounds the calendar: nothing
    says when that contract became prompt, so it is never prompt here, and the calendar starts
    the day after it expires. Each code is given once, spelling and case as typed, since the
    code is the label a day's prompt contract is read by. And each future expires after the
    one above, in the order given, since the days between two expiries are the later contract's:
    the expiry day belongs to the contract expiring on it, and the day after to the next
    contract in the schedule, weekends and holidays moving nothing. Nothing is sorted and no
    code is read for its month; the schedule is the whole prompt sequence, as supplied.

    The columns: every calendar day from the day after the first expiry to the last expiry,
    one np.arange; the row prompt on each day, one np.searchsorted over the expiries, each day
    finding the first expiry on or after it; whether the market is open, np.is_busday over the
    days with the holiday calendar's list, Monday to Friday, a day listed twice or on a weekend
    or outside the calendar changing nothing; and whether the day is before the valuation
    date's day, one comparison, the day itself not past whatever fraction of it has elapsed,
    and a valuation date before the calendar making no day past, after it every day. The three
    objects are kept by reference and not copied, and the columns are frozen. Rows count as the
    sheet counts them, the schedule's first row being row 1.
    """
    codes = expiry_schedule.codes
    expiries = expiry_schedule.future_expiry
    if len(codes) < 2:
        have = f"{len(codes)} {'contract' if len(codes) == 1 else 'contracts'}"
        raise ValueError(f"expiry_schedule has {have}, expected at least 2")
    if len(set(codes)) != len(codes):
        seen: dict[str, int] = {}
        for row, code in enumerate(codes, start=1):
            if code in seen:
                raise ValueError(
                    f"future_code row {row} is {code!r}, already given at row {seen[code]}"
                )
            seen[code] = row
    unordered = expiries[1:] <= expiries[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # expiries[k + 1] is the first expiry not after the one before
        raise ValueError(
            f"future_expiry row {k + 2} is {expiries[k + 1]}, "
            f"expected a date after row {k + 1}'s {expiries[k]}"
        )
    day = np.timedelta64(1, "D")
    dates: NDArray[np.datetime64] = np.arange(expiries[0] + day, expiries[-1] + day)
    prompt = np.searchsorted(expiries, dates, side="left")
    is_business_day = np.is_busday(dates, holidays=holiday_calendar.holiday)
    is_past = dates < valuation_date.as_of
    for column in (dates, prompt, is_business_day, is_past):
        column.setflags(write=False)
    return Calendar(
        valuation_date, expiry_schedule, holiday_calendar, dates, prompt, is_business_day, is_past
    )
