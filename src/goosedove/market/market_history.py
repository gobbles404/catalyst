"""The market history: an index's calendar, kept by reference, and the price fixed on each of
its periods that has fixed, taken from the fixings of the calendar's market, one price for every
such period and none for any other. docs/library/market/market-history.md is the page."""

from dataclasses import dataclass
from functools import singledispatch
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.calendar.calendar import Calendar
from goosedove.index_definitions.kind import Kind, described, named
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
    object the seam hands over as the calendar reads its schedule's; the fixings must be the
    calendar's market's; then that market's rules on the fixings against the calendar, checked
    once, in this order, the first failure being the message; then the two columns.

    The calendar decides the periods and the fixings supply the prices on them. Every fixing is
    on the fixed side, as the calendar decides it for its market: a futures settle before the
    valuation date's day, a Gas Daily print for a flow day on or before it, an index for a month
    published before it, inside the calendar or out, whatever fraction of the day has elapsed.
    Every fixing inside the calendar lands on a period it prices, or, for IFERC, on a month it
    holds. And every fixed and priced period has its fixing, the first and the last as much as
    the periods between, since a period without one is a row the desk did not paste, never a
    price to carry forward or interpolate. Dated fixings find their rows by one subtraction from
    the calendar's first day, and may run past the calendar on either side, allowed and unused;
    an index finds its row by its code, and a code the calendar does not hold names nothing here.

    The calendar is kept as it is, its periods, contracts and flags neither copied nor changed,
    and the fixings are left as they were; the rows and the prices are the history's own, the
    prices copied out of the fixings' column, and both are frozen. Nothing is sorted but an
    index's place, which is its month's row, and no calendar is rebuilt.
    """
    return _bind(fixings, calendar)


@singledispatch
def _bind(fixings: object, calendar: Calendar) -> MarketHistory:
    raise ValueError(f"fixings is {named(fixings)}, expected futures, IFERC or Gas Daily fixings")


def fixings_of(kind: Kind) -> str:
    """The fixings a calendar of that kind takes, named in a message."""
    match kind:
        case Kind.FUTURES:
            return "futures fixings"
        case Kind.IFERC:
            return "IFERC fixings"
        case Kind.GAS_DAILY:
            return "Gas Daily fixings"
        case _:
            assert_never(kind)


def _of_the_market(calendar: Calendar, kind: Kind, arrived: str) -> None:
    """The fixings are the calendar's market's, else refused naming what arrived and what the
    calendar takes."""
    if calendar.index.kind is not kind:
        raise ValueError(
            f"fixings is {arrived}, expected {fixings_of(calendar.index.kind)} "
            f"with {described(calendar.index.kind)}"
        )


@_bind.register
def futures_history(fixings: FuturesFixings, calendar: Calendar) -> MarketHistory:
    """The three rules of #84: no settle on or after the valuation date's day, no settle on a
    day the calendar closes, and a settle on every fixed business day."""
    _of_the_market(calendar, Kind.FUTURES, "futures fixings")
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
    closed = ~calendar.is_priced[rows]
    if closed.any():
        k = int(closed.argmax())  # rows[k] is the first row the calendar closes with a fixing
        raise ValueError(
            f"fixings date {dates[rows[k]]} is a closed day in calendar, expected no fixing"
        )
    _every_fixed_day(calendar, rows)
    return _frozen(calendar, rows, fixings.settles[inside])


@_bind.register
def gas_daily_history(fixings: GasDailyFixings, calendar: Calendar) -> MarketHistory:
    """Two rules, every flow day being priced: no print for a flow day after the valuation
    date's day, since a print precedes its day and no later one exists yet, and a print on every
    fixed day."""
    _of_the_market(calendar, Kind.GAS_DAILY, "Gas Daily fixings")
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
    """Three rules by code, every month being priced: every index is for a month the calendar
    holds, for a month already fixed, and every fixed month has its index; the rows come out in
    the calendar's order whatever order the indices came in."""
    _of_the_market(calendar, Kind.IFERC, "IFERC fixings")
    codes = calendar.index.schedule.codes
    place = {code: row for row, code in enumerate(codes)}
    found: list[int] = []
    for code in fixings.codes:
        row = place.get(code)
        if row is None:
            raise ValueError(
                f"fixings contract_code {code!r} is not a month of calendar, "
                "expected one of its codes"
            )
        found.append(row)
    rows = np.array(found, dtype=np.intp)
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
