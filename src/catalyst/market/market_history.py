"""The market history: an index's calendar, kept by reference, and the prices fixed on each of
its periods that has fixed, taken from the fixings of that same index, a price for every such
period and none for any other, and on a futures calendar, since nearby-selection.md, one for
each nearby contract the fixings carry a settle of.
docs/library/market/market-history.md is the page."""

from dataclasses import dataclass
from functools import singledispatch

import numpy as np
from numpy.typing import NDArray

from catalyst.calendar.calendar import Calendar
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.kind import named
from catalyst.market_data.futures_fixings import FuturesFixings
from catalyst.market_data.gas_daily_fixings import GasDailyFixings
from catalyst.market_data.iferc_fixings import IfercFixings
from catalyst.market_data.published_fixings import PublishedFixings


@dataclass(frozen=True, slots=True)
class MarketHistory:
    """The calendar, the object itself and not a copy, and the fixings aligned by row, both
    read-only: fixed_rows[k] is the row of the calendar whose period the k-th row of prices
    fixed on, increasing, and fixing_prices[k, n] the price fixed on it for the contract n
    places after the one the calendar gives the period, any number, zero and below included.
    Column 0 is the calendar's own contract's price, the prompt future's settle on a futures
    day, a month's index, a flow day's print, a published print's price; since
    nearby-selection.md a futures history has a column more for each further nearby its
    fixings carry, the second nearby's settle in column 1, every one of a contract the schedule
    lists, and an IFERC, a Gas Daily or a published history is the same record one column wide.
    The rows are exactly the calendar's fixed and priced periods, is_fixed and is_priced both,
    every one and no other, so a period absent from fixed_rows has no price, a futures weekend
    or holiday or a period not yet fixed, and no number stands for absence."""

    calendar: Calendar
    fixed_rows: NDArray[np.intp]
    fixing_prices: NDArray[np.float64]

    def fixed_prices(
        self, rows: NDArray[np.intp], contracts: NDArray[np.intp]
    ) -> NDArray[np.float64]:
        """The price fixed on each calendar row asked for, of the contract asked for beside it,
        a row of the schedule as the calendar's contract column holds it, in the order asked:
        the one place a fixing is read, as the market's live_prices is the one place a quote
        is, so the rule is every reader's, a batch's preparation and a quote's pricing alike.
        The rows are fixed and priced periods, the caller having told the fixed from the
        live by the calendar's own flag. A fixing is held by its period and its position, the
        contract's row less the row of the contract the calendar gives the period: nothing
        for the calendar's own contract, the prompt on a futures day, one for the second
        nearby. A contract before the calendar's, or further on than the fixings carry a
        settle of, is refused, the first such fixing asked for being named by its contract,
        its day and that day's own contract, and never answered with another nearby's settle,
        another day's or a quote: a position past the columns would stop in NumPy's words,
        and one before them would count back from the last column and return a wrong price
        with no failure at all.

        Work: one gather of the calendar's contracts and one search of the fixed rows, the
        positions and the places made in those two arrays in place, two reductions for the
        rule, and one gather of the prices through a flat view; nothing else is allocated,
        so the peak is the two arrays and the prices, as a read by day alone was."""
        calendar = self.calendar
        position = calendar.contract[rows]  # each row's own contract, then the distance
        np.subtract(contracts, position, out=position)
        held = self.fixing_prices.shape[1]
        if position.min(initial=0) < 0 or position.max(initial=0) >= held:
            outside = (position < 0) | (position >= held)
            j = int(outside.argmax())  # the first asked for outside the settles held
            codes = calendar.index.schedule.codes
            day = calendar.dates[int(rows[j])]
            asked = codes[int(contracts[j])]
            prompt = codes[int(calendar.contract[int(rows[j])])]
            if position[j] < 0:
                raise ValueError(
                    f"requested fixing of {asked!r} on {day} is of a contract before {prompt!r}, "
                    "the contract the calendar gives that day; a history holds the settle of that "
                    "contract and of those after it"
                )
            raise ValueError(
                f"requested fixing of {asked!r} on {day} is the {nth(int(position[j]) + 1)} "
                f"nearby's, {prompt!r} being prompt that day, beyond the {held} "
                f"{'settle' if held == 1 else 'settles'} a day the history holds; expected "
                "fixings with a settle column for it"
            )
        place = np.searchsorted(self.fixed_rows, rows)  # each row's row of prices
        place *= held
        place += position  # its cell, counted along the rows of prices
        return self.fixing_prices.ravel()[place]


def nth(position: int) -> str:
    """A position in words a message reads, 1st, 2nd, 3rd, 4th, 11th, 22nd: the nearby a
    refusal names, counted from one as the sheet counts it."""
    if 10 <= position % 100 <= 20:
        return f"{position}th"
    return f"{position}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(position % 10, 'th') }"


def market_history(calendar: Calendar, fixings: object) -> MarketHistory:
    """The one way to make a MarketHistory: the fixings' kind chooses the binder, read off the
    object the seam hands over; the fixings must be over the calendar's index, the one object
    the two were made with, which is the kind rule too, since fixings of a kind are over an
    index of that kind; then that kind's rules on the fixings against the calendar, checked
    once, in this order, the first failure being the message; then the two columns.

    The calendar decides the periods and the fixings supply the prices on them. Every fixing is
    on the fixed side, as the calendar decides it for its market: a futures settle before the
    valuation date's day, a Gas Daily print for a flow day on or before it, an index for a month
    published before it, a published print dated before it, inside the calendar or out,
    whatever fraction of the day has elapsed.
    Every fixed and priced period has its fixing, the first and the last as much as the periods
    between, since a period without one is a row the desk did not paste, never a price to carry
    forward or interpolate. No fixing can fall on a day the calendar closes, both having been
    checked against the index's one holiday calendar, and no IFERC index can name a month the
    calendar lacks, the fixings' creator having refused any code that is not the index's. A
    futures day's settles are of the contracts the schedule lists from that day's prompt on,
    since nearby-selection.md, a settle for a nearby past the schedule's last contract having
    no contract to be the settle of, so the first fixed day with one is refused. Dated
    fixings find their rows by one subtraction from the calendar's first day, and may run past
    the calendar on either side, allowed and unused; an index finds its row by its code.

    The calendar is kept as it is, its periods, contracts and flags neither copied nor changed,
    and the fixings are left as they were; the rows and the prices are the history's own, the
    prices copied out of the fixings' rows, a column for each nearby a futures series carries
    and one for a month's index or a day's print, and both are frozen. Nothing is sorted but an
    index's place, which is its month's row, and no calendar is rebuilt.
    """
    return _bind(fixings, calendar)


@singledispatch
def _bind(fixings: object, calendar: Calendar) -> MarketHistory:
    raise ValueError(
        f"fixings is {named(fixings)}, expected futures, IFERC, Gas Daily or published fixings"
    )


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
    nothing left to catch once the two are one index's. And since nearby-selection.md every
    nearby the fixings carry is of a listed contract on every fixed day."""
    _over_the_calendars_index(calendar, fixings.index)
    as_of = calendar.valuation_date.as_of
    fixing_dates = fixings.dates
    late = fixing_dates >= as_of
    if late.any():
        k = int(late.argmax())  # kept oldest first, so the first late date is the earliest
        raise ValueError(
            f"fixings date {fixing_dates[k]} is on or after valuation date {as_of}, "
            "expected dates before the valuation date"
        )
    dates = calendar.dates
    offset = (fixing_dates - dates[0]).astype(np.intp)
    inside = (offset >= 0) & (offset < dates.size)
    rows = offset[inside]
    _every_fixed_day(calendar, rows)
    _every_nearby_listed(calendar, rows, fixings.settles.shape[1])
    # The fixings' days increase, so those inside the calendar are one run of the series, from
    # the count of the days before the calendar's first on: the grid's rows are copied as that
    # one slice, a row of settles beside its day, and nothing is gathered row by row; a series
    # of no rows is a slice of none.
    first = int(np.count_nonzero(offset < 0))
    return _frozen(calendar, rows, np.array(fixings.settles[first : first + rows.size]))


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
        k = int(late.argmax())  # kept oldest first, so the first late day is the earliest
        raise ValueError(
            f"fixings flow_date {flow_dates[k]} is after valuation date {as_of}, "
            "expected flow days on or before the valuation date"
        )
    dates = calendar.dates
    offset = (flow_dates - dates[0]).astype(np.intp)
    inside = (offset >= 0) & (offset < dates.size)
    rows = offset[inside]
    _every_fixed_day(calendar, rows)
    return _frozen(calendar, rows, fixings.prices[inside][:, None])


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
    return _frozen(calendar, rows[order], fixings.prices[order][:, None])


@_bind.register
def published_history(fixings: PublishedFixings, calendar: Calendar) -> MarketHistory:
    """Two rules by print, every print being priced and every price a print of the index, so of
    the calendar: every price is of a print already fixed, and every fixed print has its price.

    A published calendar's rows are its schedule's prints, row for row, so the row the fixings
    found each price's print at when they were made is its row here and nothing is searched
    again. The fixed prints are the calendar's first rows, counted when the calendar was made,
    and the fixings' prints increase, each once: so a price for a print not yet fixed is a row at
    or past that count, the earliest named, and with none of those the fixed prints all have a
    price when there are as many prices as fixed prints, the first without one named otherwise.
    A print is fixed from the day after its date whether or not its publisher has released its
    price, so on a day before the release the sheet supplies a stand-in, as the page says; a
    stand-in is a price like any other here, and the refusal of a fixed print without one says
    so. The rows and the prices are the fixings' own two read-only arrays, held and not copied.
    """
    _over_the_calendars_index(calendar, fixings.index)
    rows = fixings.rows
    fixed = calendar.first_unfixed  # the fixed prints are the calendar's first rows
    unfixed = rows >= fixed
    if unfixed.any():
        k = int(rows[int(unfixed.argmax())])  # the earliest print with a price it should not have
        raise ValueError(
            f"fixings publication_date {calendar.dates[k]} is a print not yet fixed in calendar, "
            "expected a price for fixed prints alone; a print is fixed from the day after its date"
        )
    if rows.size != fixed:
        gap = rows != np.arange(rows.size)
        k = int(gap.argmax()) if gap.any() else rows.size  # the first fixed print without a price
        raise ValueError(
            f"fixings has no price for the print dated {calendar.dates[k]}, expected a price for "
            "every fixed print in calendar, a stand-in where its publisher has not released it"
        )
    return _frozen(calendar, rows, fixings.prices[:, None])


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


def _every_nearby_listed(calendar: Calendar, rows: NDArray[np.intp], nearbys: int) -> None:
    """Every nearby a futures series carries a settle of is a contract the schedule lists, on
    every fixed day: the contract `nearbys` less one places after the day's prompt is within
    the schedule, else the first fixed day it is not is named with the settles a day the
    schedule can name there, the contracts it lists from that day's prompt on. A series of
    the prompt alone asks nothing: the prompt is a row of the schedule. The prompt never
    moves back along the calendar, so the last fixed day's is the furthest on and the one
    look that decides, taken as a slice so that a history of no fixed day asks it of
    nothing; the days are searched only to name the first at fault."""
    codes = calendar.index.schedule.codes
    furthest = len(codes) - nearbys  # the last prompt every held nearby is listed after
    if (calendar.contract[rows[-1:]] > furthest).any():
        prompts = calendar.contract[rows]
        row = int(rows[int(np.searchsorted(prompts, furthest, side="right"))])
        prompt = int(calendar.contract[row])
        raise ValueError(
            f"fixings has {nearbys} settles on {calendar.dates[row]}, expected at most "
            f"{len(codes) - prompt}, the contracts the schedule lists from {codes[prompt]!r}, "
            f"prompt that day, through {codes[-1]!r}, its last; a later nearby names no listed "
            "contract"
        )


def _frozen(
    calendar: Calendar, rows: NDArray[np.intp], prices: NDArray[np.float64]
) -> MarketHistory:
    rows.setflags(write=False)
    prices.setflags(write=False)
    return MarketHistory(calendar, rows, prices)
