"""Gas Daily fixings: the midpoint Platts printed for each day gas flowed, price beside flow day,
one row for every calendar day from the first to the last, as Platts dates them, and the index
they are the fixings of. docs/library/market-data/gas-daily-fixings.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind, described


@dataclass(frozen=True, slots=True)
class GasDailyFixings:
    """The index whose fixings these are, kept by reference, and flow days and prices aligned by
    position, both read-only: dates[i] and prices[i] describe one flow day's price. The dates are
    consecutive calendar days from the first to the last, weekends and holidays included, each
    row the number Platts dated to that day; a price is any number a cell holds, zero and below
    included."""

    index: Index
    dates: NDArray[np.datetime64]
    prices: NDArray[np.float64]


def gas_daily_fixings(
    flow_date: NDArray[np.datetime64], price: NDArray[np.float64], index: Index
) -> GasDailyFixings:
    """The one way to make GasDailyFixings: three rules of meaning, checked once, vectorized, in
    this order, the first failure being the message.

    The index is a Gas Daily index, since Gas Daily fixings belong to one, and nothing else is
    read from it: a Gas Daily index has no holiday calendar, and the flow days are not held to
    its schedule, since a series may run past the calendar on either side, allowed and unused
    there. One price per flow day, since the seam never compares two columns and a series is
    rows. And each flow day the day after the row above, since a series that prices every
    calendar day has no other shape: the days increase, no day is given twice and no day between
    the first and the last is missing, one comparison over the column, the first row that breaks
    it named with the day that was expected. Nothing is sorted, filled or carried forward: a
    series pasted newest first fails at its second row, and a day without a row is a row the
    desk did not paste. No weekday is looked at, no holiday list is taken and no month is read
    off a day. Both columns are copied and then frozen, so the fixings own their data, and the
    index is kept by reference, the one the desk paired the series with. Rows count as the sheet
    counts them, the first row of the column being row 1.
    """
    if index.kind is not Kind.GAS_DAILY:
        raise ValueError(f"index is {described(index.kind, 'index')}, expected a Gas Daily index")
    if price.size != flow_date.size:
        have = f"{price.size} {'price' if price.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {flow_date.size}, one per flow_date")
    days = np.array(flow_date, dtype="datetime64[D]")
    following = days[:-1] + np.timedelta64(1, "D")
    broken = days[1:] != following
    if broken.any():
        k = int(broken.argmax())  # days[k + 1] is the first day that is not the day after days[k]
        raise ValueError(
            f"flow_date row {k + 2} is {days[k + 1]}, expected {following[k]}, "
            f"the day after row {k + 1}'s {days[k]}"
        )
    prices = np.array(price, dtype=np.float64)
    days.setflags(write=False)
    prices.setflags(write=False)
    return GasDailyFixings(index, days, prices)
