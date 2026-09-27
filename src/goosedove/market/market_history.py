"""The market history: an index's calendar, kept by reference, and the price fixed on each of
its periods that has fixed, taken from the fixings of that same index, one price for every such
period and none for any other. docs/library/market/market-history.md is the page."""

from dataclasses import dataclass
from functools import singledispatch

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import named
from goosedove.market_data.futures_fixings import FuturesFixings
from goosedove.market_data.gas_daily_fixings import GasDailyFixings
from goosedove.market_data.iferc_fixings import IfercFixings


@dataclass(frozen=True, slots=True)
class MarketHistory:
    """The calendar, the object itself and not a copy, and two columns aligned by position,
    both read-only: fixed_rows[k] is the row of the calendar whose period the k-th price fixed
    on, increasing, and fixing_prices[k] the price fixed on it, any number, zero and below
    included. The rows are exactly the calendar's fixed and priced periods, is_fixed and
    is_priced both, every one and no other, so a period absent from fixed_rows has no price, a
    futures weekend or holiday or a period not yet fixed, and no number stands for absence."""

    calendar: Calendar
    fixed_rows: NDArray[np.intp]
    fixing_prices: NDArray[np.float64]


def market_history(calendar: Calendar, fixings: object) -> MarketHistory:
    """The one way to make a MarketHistory: the fixings' kind chooses the binder, read off the
    object the seam hands over; the fixings must be over the calendar's index, the one object
    the two were made with, which is the kind rule too, since fixings of a kind are over an
    index of that kind; then that kind's rules on the fixings against the calendar, checked
    once, in this order, the first failure being the message; then the two columns.

    The calendar decides the periods and the fixings supply the prices on them. Every fixing is
    on the fixed side, as the calendar decides it for its market: a futures settle before the
    valuation date's day, a Gas Daily print for a flow day on or before it, an index for a month
    published before it, inside the calendar or out, whatever fraction of the day has elapsed.
    Every fixed and priced period has its fixing, the first and the last as much as the periods
    between, since a period without one is a row the desk did not paste, never a price to carry
    forward or interpolate. No fixing can fall on a day the calendar closes, both having been
    checked against the index's one holiday calendar, and no IFERC index can name a month the
    calendar lacks, the fixings' creator having refused any code that is not the index's. Dated
    fixings find their rows by one subtraction from the calendar's first day, and may run past
    the calendar on either side, allowed and unused; an index finds its row by its code.

    The calendar is kept as it is, its periods, contracts and flags neither copied nor changed,
    and the fixings are left as they were; the rows and the prices are the history's own, the
    prices copied out of the fixings' column, and both are frozen. Nothing is sorted but an
    index's place, which is its month's row, and no calendar is rebuilt.
    """
    return _bind(fixings, calendar)


@singledispatch
def _bind(fixings: object, calendar: Calendar) -> MarketHistory:
    raise ValueError(f"fixings is {named(fixings)}, expected futures, IFERC or Gas Daily fixings")


def _over_the_calendars_index(calendar: Calendar, index: Index) -> None:
    """The fixings are over the calendar's index, the one object _CreateIndex made, else refused
    naming the two: another index of the same name is another index, made by a call with other
    arguments or by an equal call made again after the first index was released, and fixings of
    another kind are over another index. Two equal _CreateIndex cells live at once share one
    index, so a calendar over one and fixings over the other pass."""
    if index is not calendar.index:
        raise ValueError(
            f"fixings is over another index, {index.name!r}, "
            f"expected the calendar's, {calendar.index.name!r}"
        )


@_bind.register
def futures_history(fixings: FuturesFixings, calendar: Calendar) -> MarketHistory:
    """Two of the three rules of #84: no settle on or after the valuation date's day, and a
    settle on every fixed business day; the third, no settle on a day the calendar closes, has
    nothing left to catch once the two are one index's."""
    _over_the_calendars_index(calendar, fixings.index)
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
    _every_fixed_day(calendar, rows)
    return _frozen(calendar, rows, fixings.settles[inside])


@_bind.register
def gas_daily_history(fixings: GasDailyFixings, calendar: Calendar) -> MarketHistory:
    """Two rules, every flow day being priced: no print for a flow day after the valuation
    date's day, since a print precedes its day and no later one exists yet, and a print on every
    fixed day."""
    _over_the_calendars_index(calendar, fixings.index)
    as_of = calendar.valuation_date.as_of
    flow_dates = fixings.dates
    late = flow_dates > as_of
    if late.any():
        k = int(late.argmax())  # the flow days increase, so the first late day is the earliest
        raise ValueError(
            f"fixings flow_date {flow_dates[k]} is after valuation date {as_of}, "
            "expected flow days on or before the valuation date"
        )
    dates = calendar.dates
    offset = (flow_dates - dates[0]).astype(np.intp)
    inside = (offset >= 0) & (offset < dates.size)
    rows = offset[inside]
    _every_fixed_day(calendar, rows)
    return _frozen(calendar, rows, fixings.prices[inside])


@_bind.register
def iferc_history(fixings: IfercFixings, calendar: Calendar) -> MarketHistory:
    """Two rules by code, every month being priced and every code a month of the index, so of
    the calendar: every index is for a month already fixed, and every fixed month has its index;
    the rows come out in the calendar's order whatever order the indices came in."""
    _over_the_calendars_index(calendar, fixings.index)
    codes = calendar.index.schedule.codes
    place = {code: row for row, code in enumerate(codes)}
    rows = np.array([place[code] for code in fixings.codes], dtype=np.intp)
    unfixed = ~calendar.is_fixed[rows]
    if unfixed.any():
        k = int(rows[unfixed].min())  # the earliest month with an index it should not have
        raise ValueError(
            f"fixings contract_code {codes[k]!r} is a month not yet fixed in calendar, "
            "expected an index for fixed months alone"
        )
    covered = np.zeros(calendar.dates.size, dtype=bool)
    covered[rows] = True
    missing = calendar.is_fixed & ~covered
    if missing.any():
        k = int(missing.argmax())  # the first fixed month without an index
        raise ValueError(
            f"fixings has no index for {codes[k]}, "
            "expected an index for every fixed month in calendar"
        )
    order = np.argsort(rows)
    return _frozen(calendar, rows[order], fixings.prices[order])


def _every_fixed_day(calendar: Calendar, rows: NDArray[np.intp]) -> None:
    """Every fixed and priced day of the calendar is among the rows, else the first without a
    fixing is named."""
    covered = np.zeros(calendar.dates.size, dtype=bool)
    covered[rows] = True
    missing = calendar.is_fixed & calendar.is_priced & ~covered
    if missing.any():
        k = int(missing.argmax())  # dates[k] is the first fixed day without a fixing
        raise ValueError(
            f"fixings has no fixing for {calendar.dates[k]}, "
            "expected a fixing for every fixed day in calendar"
        )


def _frozen(
    calendar: Calendar, rows: NDArray[np.intp], prices: NDArray[np.float64]
) -> MarketHistory:
    rows.setflags(write=False)
    prices.setflags(write=False)
    return MarketHistory(calendar, rows, prices)
