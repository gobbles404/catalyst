"""Gas Daily fixings: the midpoint Platts printed for each day gas flowed, price beside flow day,
as the desk keeps them, the newest at the top, one row for every calendar day from the last
row's day to the first row's, as Platts dates them, and the index they are the fixings of.
docs/library/market-data/gas-daily-fixings.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from catalyst.index_definitions.index import Index
from catalyst.index_definitions.kind import Kind, described


@dataclass(frozen=True, slots=True)
class GasDailyFixings:
    """The index whose fixings these are, kept by reference, and flow days and prices aligned by
    position, both read-only: dates[i] and prices[i] describe one flow day's price. The dates are
    consecutive calendar days from the first to the last, weekends and holidays included, each
    row the number Platts dated to that day, increasing: the sheet gives the series newest
    first, and it is kept oldest first, the order the history reads it in. A price is any number
    a cell holds, zero and below included."""

    index: Index
    dates: NDArray[np.datetime64]
    prices: NDArray[np.float64]


def gas_daily_fixings(
    flow_date: NDArray[np.datetime64], price: NDArray[np.float64], index: Index
) -> GasDailyFixings:
    """The one way to make GasDailyFixings: three rules of meaning, checked once, vectorized, in
    this order, the first failure being the message, then the two columns kept the other way up.

    The series is given as the desk keeps it, the newest flow day in the first row, so that a new
    day is a row added at the top. The index is a Gas Daily index, since Gas Daily fixings belong
    to one, and nothing else is read from it: a Gas Daily index has no holiday calendar, and the
    flow days are not held to its schedule, since a series may run past the calendar on either
    side, allowed and unused there. One price per flow day, since the seam never compares two
    columns and a series is rows. And each flow day the day before the row above, since a series
    that prices every calendar day has no other shape: the days decrease, no day is given twice
    and no day between the last row's and the first row's is missing, one comparison over the
    column, the first row from the top that breaks it named with the day that was expected.
    Nothing is sorted, filled or carried forward: a series pasted oldest first fails at its
    second row, one direction being the only one taken, and a day without a row is a row the
    desk did not paste. No weekday is looked at, no holiday list is taken and no month is read
    off a day.

    The rules run on the rows as the sheet gave them, a column of days, datetime64[D], as the
    seam hands it over and as a Python caller passes it, so each message names the sheet's own
    row, the first row of the column being row 1. Then both columns are copied from the last
    row to the first and frozen: one copy each, as before, and what is kept runs oldest first,
    flow day beside its own price, the order the market history reads. The fixings own their
    data, and the index is kept by reference, the one the desk paired the series with.
    """
    if index.kind is not Kind.GAS_DAILY:
        raise ValueError(f"index is {described(index.kind, 'index')}, expected a Gas Daily index")
    if price.size != flow_date.size:
        have = f"{price.size} {'price' if price.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {flow_date.size}, one per flow_date")
    # The column's rule runs on the rows as the sheet gave them, newest first, nothing copied yet.
    preceding = flow_date[:-1] - np.timedelta64(1, "D")
    broken = flow_date[1:] != preceding
    if broken.any():
        # flow_date[k + 1] is the first day from the top that is not the day before its row above
        k = int(broken.argmax())
        raise ValueError(
            f"flow_date row {k + 2} is {flow_date[k + 1]}, expected {preceding[k]}, "
            f"the day before row {k + 1}'s {flow_date[k]}"
        )
    # The one copy of each column, read from the last row back: oldest first, and contiguous.
    days = np.array(flow_date[::-1], dtype="datetime64[D]")
    prices = np.array(price[::-1], dtype=np.float64)
    days.setflags(write=False)
    prices.setflags(write=False)
    return GasDailyFixings(index, days, prices)
