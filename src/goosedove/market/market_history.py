"""The market history: an index's calendar, kept by reference, and the fixing on each of its
days that has fixed, taken from the index's fixings as the calendar's mode says: for a daily
calendar the settle on each past business day, from the daily fixings; for a monthly one the
price supplied for each expired contract, from the monthly fixings, on every day that contract
is prompt. docs/library/market/market-history.md is the page."""

from dataclasses import dataclass
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar, FixingMode
from goosedove.market_data.daily_fixings import DailyFixings
from goosedove.market_data.monthly_fixings import MonthlyFixings


@dataclass(frozen=True, slots=True)
class MarketHistory:
    """The calendar, the object itself and not a copy, and two columns aligned by position,
    both read-only: fixed_rows[k] is a row of the calendar, increasing, and fixing_prices[k]
    the price fixed for its day, any number, zero and below included. For a daily calendar
    the rows are exactly its past business days, is_past and is_business_day both, each with
    the settle fixed on it; for a monthly calendar they are every day whose prompt contract
    expired before the valuation date, weekends and holidays included, each with the price
    supplied for that contract, repeated across its days. A day absent from fixed_rows has no
    price, and no number stands for absence."""

    calendar: Calendar
    fixed_rows: NDArray[np.intp]
    fixing_prices: NDArray[np.float64]


def market_history(calendar: Calendar, fixings: DailyFixings | MonthlyFixings) -> MarketHistory:
    """The one way to make a MarketHistory: the fixings that fit the calendar's mode, checked
    once, then the mode's own rules, the first failure being the message; then the two
    columns, made once.

    The calendar says how the index fixes, and the fixings must be of that kind: daily fixings
    for a daily calendar, monthly for a monthly one, never inferred from what the fixings hold.
    The seam has already established that the fixings are one of the two kinds; which, and
    whether it is the calendar's, is decided here once and nowhere else. The calendar is kept
    as it is, its days, prompts and flags neither copied nor changed, and the fixings are left
    as they were; the rows and the prices are the history's own, frozen. Nothing is sorted and
    no calendar is rebuilt.
    """
    match calendar.fixing_mode:
        case FixingMode.DAILY:
            match fixings:
                case DailyFixings():
                    return _daily_history(calendar, fixings)
                case MonthlyFixings():
                    raise ValueError(
                        "fixings is monthly fixings, expected daily fixings for a daily calendar"
                    )
                case _:
                    assert_never(fixings)
        case FixingMode.MONTHLY:
            match fixings:
                case MonthlyFixings():
                    return _monthly_history(calendar, fixings)
                case DailyFixings():
                    raise ValueError(
                        "fixings is daily fixings, expected monthly fixings for a monthly calendar"
                    )
                case _:
                    assert_never(fixings)
        case _:
            assert_never(calendar.fixing_mode)


def _daily_history(calendar: Calendar, fixings: DailyFixings) -> MarketHistory:
    """A daily calendar's history: three rules on the fixings against the calendar, in this
    order, the first failure being the message.

    The calendar decides the days and the fixings supply the prices on them. Every fixing is
    historical: none is dated on or after the valuation date's day, inside the calendar or out,
    whatever fraction of the day has elapsed, since a price on the valuation day is not history.
    Every fixing inside the calendar's days is on a day the calendar has the market open, since
    a fixing on a day the calendar closes means the two disagree about a holiday, and neither
    is guessed right. And every past business day of the calendar has a fixing on that exact
    day, the first and the last as much as the days between, since a day without one is a row
    the desk did not paste, never a price to carry forward or interpolate. The fixings' dates
    increase and the calendar's days are consecutive, so a fixing's row is its day count from
    the calendar's first day, one subtraction over the fixings, and the earliest offending date
    is the first flagged; a fixing before the calendar's first day or after its last is allowed
    and unused, and the ends of the two need not meet. The prices are copied out of the
    fixings' column.
    """
    as_of = calendar.valuation_date.as_of
    fixing_dates = fixings.dates
    late = fixing_dates >= as_of
    if late.any():
        k = int(late.argmax())  # the dates increase, so the first late date is the earliest
        raise ValueError(
            f"fixings date {fixing_dates[k]} is on or after valuation date {as_of}, "
            "expected dates before the valuation date"
        )
    dates = calendar.dates
    offset = (fixing_dates - dates[0]).astype(np.intp)
    inside = (offset >= 0) & (offset < dates.size)
    rows = offset[inside]
    closed = ~calendar.is_business_day[rows]
    if closed.any():
        k = int(closed.argmax())  # rows[k] is the first row the calendar closes with a fixing
        raise ValueError(
            f"fixings date {dates[rows[k]]} is a non-business day in calendar, expected no fixing"
        )
    covered = np.zeros(dates.size, dtype=bool)
    covered[rows] = True
    missing = calendar.is_past & calendar.is_business_day & ~covered
    if missing.any():
        k = int(missing.argmax())  # dates[k] is the first past business day without a fixing
        raise ValueError(
            f"fixings has no fixing for {dates[k]}, "
            "expected a fixing for every past business day in calendar"
        )
    prices = fixings.settles[inside]
    rows.setflags(write=False)
    prices.setflags(write=False)
    return MarketHistory(calendar, rows, prices)


def _monthly_history(calendar: Calendar, fixings: MonthlyFixings) -> MarketHistory:
    """A monthly calendar's history: three rules, in this order, the first failure being the
    message; then the price of each expired contract on every day it is prompt.

    A contract has expired when its future expires before the valuation date's day, the expiry
    day itself still live whatever fraction of the day has elapsed; the expiries increase, so
    the expired contracts are the schedule's first rows, and the schedule's first contract,
    which only bounds the calendar and is never prompt, needs no fixing. Each other expired
    contract needs the fixing dated its publication date, the day the schedule says its price
    is published: a fixing supplied is a value, provisional or published, and a value is
    never invented here. The rules: the schedule's publication dates increase with its
    contracts, each after the one before in the schedule's order, so that a fixing keyed by
    date alone names one contract and the fixings the expired contracts need are one run of
    the schedule's publications with no live contract's between, the series their own creator
    accepts whole, a schedule publishing a later contract before an earlier one being refused
    here, both rows named, before any fixing is looked at; no fixing is supplied for a
    contract of the schedule that has not expired, since its price is the live quote's and
    never taken from history; and every expired contract's fixing is there, named with its
    publication date when it is not. A fixing dated no contract's publication date, or the
    first contract's, is allowed and unused, and a publication date may fall after the
    valuation date or after the calendar's last day. The days are then assigned once: the
    calendar's prompt rows increase, so the days of the expired contracts are the first rows
    of the calendar, weekends and holidays among them, and each takes its contract's price
    through the prompt row, one gather; the days of the contracts still live take nothing.
    """
    schedule = calendar.expiry_schedule
    codes = schedule.codes
    published = cast(NDArray[np.datetime64], schedule.publication_date)  # a monthly calendar's
    as_of = calendar.valuation_date.as_of
    unordered = published[1:] <= published[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # published[k + 1] is the first date not after the one before
        raise ValueError(
            f"calendar publication date row {k + 2} is {published[k + 1]} for {codes[k + 1]!r}, "
            f"expected a date after row {k + 1}'s {published[k]} for {codes[k]!r}"
        )
    expired = int(np.searchsorted(schedule.future_expiry, as_of, side="left"))
    supplied = fixings.publication_dates
    live_dates = published[max(expired, 1) :]
    places = np.searchsorted(supplied, live_dates)
    found = places < supplied.size
    found[found] = supplied[places[found]] == live_dates[found]
    if found.any():
        row = max(expired, 1) + int(found.argmax())
        raise ValueError(
            f"fixings date {published[row]} is {codes[row]!r}, not expired on {as_of}, "
            "expected fixings of expired contracts only"
        )
    wanted = published[1:expired]
    places = np.searchsorted(supplied, wanted)
    found = places < supplied.size
    found[found] = supplied[places[found]] == wanted[found]
    if not found.all():
        row = 1 + int((~found).argmax())
        raise ValueError(
            f"fixings has no fixing for {codes[row]!r} published {published[row]}, "
            "expected a fixing for every expired contract in calendar"
        )
    count = int(np.searchsorted(calendar.prompt, expired, side="left"))
    rows = np.arange(count, dtype=np.intp)
    prices = fixings.prices[places][calendar.prompt[:count] - 1]
    rows.setflags(write=False)
    prices.setflags(write=False)
    return MarketHistory(calendar, rows, prices)
