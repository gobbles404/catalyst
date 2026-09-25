"""A calendar: the periods one index prices, made once from its schedule, each with the contract
it belongs to, whether it prices and whether it is on the fixed side of the valuation date. A
futures schedule gives every day from the day after its first contract expires to the day its
last expires, the prompt future on each; a Gas Daily schedule every flow day from its first
month's first day to its last month's last, the month on each; and an IFERC schedule one row per
month, dated by the day its index is published. docs/library/calendar/calendar.md is the page."""

import re
from dataclasses import dataclass
from enum import Enum
from functools import singledispatch
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import MAX_DAYS
from goosedove.globals.valuation_date import ValuationDate
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.gas_daily_schedule import GasDailySchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule


class Kind(Enum):
    """The market a calendar is the calendar of, read off the schedule it was made from."""

    FUTURES = "futures"
    IFERC = "IFERC"
    GAS_DAILY = "Gas Daily"


def described(kind: Kind) -> str:
    """A calendar of that kind named in a message: a futures calendar, an IFERC calendar."""
    match kind:
        case Kind.FUTURES:
            return "a futures calendar"
        case Kind.IFERC:
            return "an IFERC calendar"
        case Kind.GAS_DAILY:
            return "a Gas Daily calendar"
        case _:
            assert_never(kind)


def named(obj: object) -> str:
    """An object of no expected kind named in a message by its class, in the words the seam gives
    a handle's kind: a holiday calendar, futures fixings, an iferc schedule."""
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", type(obj).__name__).lower()
    if words.endswith("s"):
        return words
    return f"{'an' if words[0] in 'aeiou' else 'a'} {words}"


@dataclass(frozen=True, slots=True)
class Calendar:
    """The objects the calendar was built from, kept by reference, its kind, and four columns
    aligned by position, all read-only: dates[i] is one period's day, the calendar day itself
    on a futures or a Gas Daily calendar and the publication day on an IFERC one; contract[i]
    the row of the schedule whose contract the period belongs to, the prompt future, never row
    0, on a futures calendar and the month otherwise; is_priced[i] whether the period has a
    price of its own, Monday to Friday and not a holiday on a futures calendar and every row on
    the other two; and is_fixed[i] whether the period is on the fixed side of the valuation
    date, a futures day before it, a Gas Daily flow day on or before it, an IFERC month
    published before it. The contract's code is the schedule's, read through the row. And one
    number, first_unfixed: the row of the first period not yet fixed, which is the count of
    the fixed periods, since the periods are in date order and the fixed side is the earlier
    one, and the calendar's length when every period has fixed; the market reads it, so that
    a market is made with no look along the calendar."""

    valuation_date: ValuationDate
    schedule: FuturesSchedule | IfercSchedule | GasDailySchedule
    holiday_calendar: HolidayCalendar | None
    kind: Kind
    dates: NDArray[np.datetime64]
    contract: NDArray[np.intp]
    is_priced: NDArray[np.bool_]
    is_fixed: NDArray[np.bool_]
    first_unfixed: int


def calendar(
    valuation_date: ValuationDate, schedule: object, holiday_calendar: HolidayCalendar | None
) -> Calendar:
    """The one way to make a Calendar: the schedule's kind chooses which calendar is made, the
    holiday calendar is checked against it, then that kind's rules run, in order, the first
    failure being the message, and its four columns and the row of its first unfixed period
    are made once, here and never again.

    The kind is read off the object the seam hands over, the one way the library tells kinds
    apart, as util_ReadHandle chooses a table for a handle; an object of no schedule kind is
    refused here in the library's words, since the seam names no kind for it. A futures
    schedule brings the holiday calendar, and the other two leave it out, since nothing reads
    it there. The sources are kept by reference and not copied, the record holds which kind it
    is, and the columns are frozen. Rows count as the sheet counts them, the schedule's first
    row being row 1.
    """
    return _of(schedule, valuation_date, holiday_calendar)


@singledispatch
def _of(
    schedule: object, valuation_date: ValuationDate, holiday_calendar: HolidayCalendar | None
) -> Calendar:
    raise ValueError(
        f"schedule is {named(schedule)}, expected a futures, IFERC or Gas Daily schedule"
    )


@_of.register
def futures_calendar(
    schedule: FuturesSchedule,
    valuation_date: ValuationDate,
    holiday_calendar: HolidayCalendar | None,
) -> Calendar:
    """Every day from the day after the first contract expires to the day the last expires.

    The schedule has two contracts or more, since its first only bounds the calendar: nothing
    says when that contract became prompt, so it is never prompt here, and the calendar starts
    the day after it expires. Each code is given once, since the code is the label a day's
    contract is read by. Each future expires after the one above, in the order given, since the
    days between two expiries are the later contract's: the expiry day belongs to the contract
    expiring on it, and the day after to the next contract in the schedule, weekends and
    holidays moving nothing. Nothing is sorted and no code is read for its month; the schedule
    is the whole prompt sequence, as supplied. And the last future expires within a sheet's
    rows of the first, MAX_DAYS days, the same bound the discount curve holds, so that whatever
    calendar is created can be read back in full.

    The columns: every calendar day from the day after the first expiry to the last expiry,
    one np.arange; the row prompt on each day, one np.searchsorted over the expiries, each day
    finding the first expiry on or after it; whether the market is open, np.is_busday over the
    days with the holiday calendar's list, Monday to Friday, a day listed twice or on a weekend
    or outside the calendar changing nothing; and whether the day is before the valuation
    date's day, one comparison, the day itself not fixed whatever fraction of it has elapsed,
    and a valuation date before the calendar fixing no day, after it every day.
    """
    if holiday_calendar is None:
        raise ValueError(
            "holiday_calendar is missing, expected holiday calendar handle with a futures schedule"
        )
    codes = schedule.codes
    expiries = schedule.future_expiry
    if len(codes) < 2:
        have = f"{len(codes)} {'contract' if len(codes) == 1 else 'contracts'}"
        raise ValueError(f"schedule has {have}, expected at least 2")
    _each_code_once(codes)
    unordered = expiries[1:] <= expiries[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # expiries[k + 1] is the first expiry not after the one before
        raise ValueError(
            f"future_expiry row {k + 2} is {expiries[k + 1]}, "
            f"expected a date after row {k + 1}'s {expiries[k]}"
        )
    if expiries[-1] - expiries[0] > np.timedelta64(MAX_DAYS, "D"):
        raise ValueError(
            f"future_expiry row {expiries.size} is {expiries[-1]}, "
            f"expected within {MAX_DAYS} days of row 1's {expiries[0]}"
        )
    day = np.timedelta64(1, "D")
    dates = np.arange(expiries[0] + day, expiries[-1] + day, dtype="datetime64[D]")
    contract = np.searchsorted(expiries, dates, side="left")
    is_priced = np.is_busday(dates, holidays=holiday_calendar.holiday)
    is_fixed = dates < valuation_date.as_of
    return _frozen(
        valuation_date,
        schedule,
        holiday_calendar,
        Kind.FUTURES,
        dates,
        contract,
        is_priced,
        is_fixed,
    )


@_of.register
def gas_daily_calendar(
    schedule: GasDailySchedule,
    valuation_date: ValuationDate,
    holiday_calendar: HolidayCalendar | None,
) -> Calendar:
    """Every flow day from the first month's first day to the last month's last, each on the
    month it flows in; one month is a calendar.

    Each code is given once. Each month's last day is on or after its first, and each month's
    first day is the day after the month above's last, so the flow days run without a gap or an
    overlap and the schedule's order is the days' order; nothing is sorted. And the last month's
    last day is within a sheet's rows of the first month's first day, both ends being rows, so
    the span is one day shorter than a futures calendar's. The columns: every calendar
    day from the first day to the last, one np.arange; the month on each day, one np.searchsorted
    over the months' last days; priced throughout, since Gas Daily prints every flow day; and
    fixed when the flow day is on or before the valuation date's day, since its print preceded
    the day, one comparison.
    """
    _no_holidays(holiday_calendar, "a Gas Daily schedule")
    codes = schedule.codes
    first = schedule.first_date
    last = schedule.last_date
    _at_least_one(codes)
    _each_code_once(codes)
    backwards = last < first
    if backwards.any():
        k = int(backwards.argmax())  # the first month whose last day precedes its first
        raise ValueError(
            f"last_date row {k + 1} is {last[k]}, "
            f"expected a date on or after row {k + 1}'s first_date {first[k]}"
        )
    day = np.timedelta64(1, "D")
    gapped = first[1:] != last[:-1] + day
    if gapped.any():
        k = int(gapped.argmax())  # first[k + 1] is the first month not starting after last[k]
        raise ValueError(
            f"first_date row {k + 2} is {first[k + 1]}, expected {last[k] + day}, "
            f"the day after row {k + 1}'s last_date {last[k]}"
        )
    if last[-1] - first[0] >= np.timedelta64(MAX_DAYS, "D"):
        raise ValueError(
            f"last_date row {last.size} is {last[-1]}, "
            f"expected within {MAX_DAYS - 1} days of row 1's first_date {first[0]}"
        )
    dates = np.arange(first[0], last[-1] + day, dtype="datetime64[D]")
    contract = np.searchsorted(last, dates, side="left")
    is_priced = np.ones(dates.size, dtype=bool)
    is_fixed = dates <= valuation_date.as_of
    return _frozen(
        valuation_date, schedule, None, Kind.GAS_DAILY, dates, contract, is_priced, is_fixed
    )


@_of.register
def iferc_calendar(
    schedule: IfercSchedule,
    valuation_date: ValuationDate,
    holiday_calendar: HolidayCalendar | None,
) -> Calendar:
    """One row per contract month, dated by the day its index is published; one month is a
    calendar.

    Each code is given once, and each month's index is published after the month above's, in
    the order given; nothing is sorted. The columns: the publication days as given, copied so
    the calendar owns them; the contract each month's own row; priced throughout, since an
    index is a price for its whole month; and fixed when the publication day is before the
    valuation date's day, since the index prints during that day, one comparison.
    """
    _no_holidays(holiday_calendar, "an IFERC schedule")
    codes = schedule.codes
    published = schedule.publication_date
    _at_least_one(codes)
    _each_code_once(codes)
    unordered = published[1:] <= published[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # published[k + 1] is the first day not after the one before
        raise ValueError(
            f"publication_date row {k + 2} is {published[k + 1]}, "
            f"expected a date after row {k + 1}'s {published[k]}"
        )
    dates = np.array(published, dtype="datetime64[D]")
    contract = np.arange(dates.size, dtype=np.intp)
    is_priced = np.ones(dates.size, dtype=bool)
    is_fixed = dates < valuation_date.as_of
    return _frozen(valuation_date, schedule, None, Kind.IFERC, dates, contract, is_priced, is_fixed)


def _no_holidays(holiday_calendar: HolidayCalendar | None, with_what: str) -> None:
    """A holiday calendar given with a schedule whose every period prices is refused, since
    nothing reads it: fail loudly rather than ignore."""
    if holiday_calendar is not None:
        raise ValueError(f"holiday_calendar is a holiday calendar, expected none with {with_what}")


def _at_least_one(codes: tuple[str, ...]) -> None:
    if not codes:
        raise ValueError("schedule has 0 contracts, expected at least 1")


def _each_code_once(codes: tuple[str, ...]) -> None:
    """Each code given once, spelling and case as typed, the first repeat named with the row it
    was first given at."""
    if len(set(codes)) != len(codes):
        seen: dict[str, int] = {}
        for row, code in enumerate(codes, start=1):
            if code in seen:
                raise ValueError(
                    f"contract_code row {row} is {code!r}, already given at row {seen[code]}"
                )
            seen[code] = row


def _frozen(
    valuation_date: ValuationDate,
    schedule: FuturesSchedule | IfercSchedule | GasDailySchedule,
    holiday_calendar: HolidayCalendar | None,
    kind: Kind,
    dates: NDArray[np.datetime64],
    contract: NDArray[np.intp],
    is_priced: NDArray[np.bool_],
    is_fixed: NDArray[np.bool_],
) -> Calendar:
    for column in (dates, contract, is_priced, is_fixed):
        column.setflags(write=False)
    first_unfixed = int(np.count_nonzero(is_fixed))  # the fixed periods come first
    return Calendar(
        valuation_date,
        schedule,
        holiday_calendar,
        kind,
        dates,
        contract,
        is_priced,
        is_fixed,
        first_unfixed,
    )
