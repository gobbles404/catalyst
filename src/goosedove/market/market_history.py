"""The market history: an index's calendar, kept by reference, and the settle fixed on each of
its past business days, taken from the index's futures fixings, one price for every such day and
none for any other. docs/library/market/market-history.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar, Kind, described
from goosedove.market_data.futures_fixings import FuturesFixings


@dataclass(frozen=True, slots=True)
class MarketHistory:
    """The calendar, the object itself and not a copy, and two columns aligned by position,
    both read-only: fixed_rows[k] is the row of the calendar whose day the k-th price was fixed
    on, increasing, and fixing_prices[k] the settle fixed on it, any number, zero and below
    included. The rows are exactly the calendar's past business days, is_fixed and
    is_priced both, every one and no other, so a day absent from fixed_rows has no price,
    a weekend, a holiday, the valuation day or a day to come, and no number stands for
    absence."""

    calendar: Calendar
    fixed_rows: NDArray[np.intp]
    fixing_prices: NDArray[np.float64]


def market_history(calendar: Calendar, futures_fixings: FuturesFixings) -> MarketHistory:
    """The one way to make a MarketHistory: the calendar a futures calendar, until the history
    reads every kind, then three rules on the fixings against it, checked once, in this order,
    the first failure being the message; then the two columns.

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
    and unused, and the ends of the two need not meet.

    The calendar is kept as it is, its days, prompts and flags neither copied nor changed, and
    the fixings are left as they were; the rows and the prices are the history's own, the
    prices copied out of the fixings' column, and both are frozen. Nothing is sorted and no
    calendar is rebuilt.
    """
    match calendar.kind:
        case Kind.FUTURES:
            pass
        case Kind.IFERC | Kind.GAS_DAILY:
            raise ValueError(f"calendar is {described(calendar.kind)}, expected a futures calendar")
        case _:
            assert_never(calendar.kind)
    as_of = calendar.valuation_date.as_of
    fixing_dates = futures_fixings.dates
    late = fixing_dates >= as_of
    if late.any():
        k = int(late.argmax())  # the dates increase, so the first late date is the earliest
        raise ValueError(
            f"futures_fixings date {fixing_dates[k]} is on or after valuation date {as_of}, "
            "expected dates before the valuation date"
        )
    dates = calendar.dates
    offset = (fixing_dates - dates[0]).astype(np.intp)
    inside = (offset >= 0) & (offset < dates.size)
    rows = offset[inside]
    closed = ~calendar.is_priced[rows]
    if closed.any():
        k = int(closed.argmax())  # rows[k] is the first row the calendar closes with a fixing
        raise ValueError(
            f"futures_fixings date {dates[rows[k]]} is a non-business day in calendar, "
            "expected no fixing"
        )
    covered = np.zeros(dates.size, dtype=bool)
    covered[rows] = True
    missing = calendar.is_fixed & calendar.is_priced & ~covered
    if missing.any():
        k = int(missing.argmax())  # dates[k] is the first past business day without a fixing
        raise ValueError(
            f"futures_fixings has no fixing for {dates[k]}, "
            "expected a fixing for every past business day in calendar"
        )
    prices = futures_fixings.settles[inside]
    rows.setflags(write=False)
    prices.setflags(write=False)
    return MarketHistory(calendar, rows, prices)
