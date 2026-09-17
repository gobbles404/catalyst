"""Daily fixings: the settlement price of one index on each day it fixed, date beside settle, as
the desk keeps them. docs/library/market-data/daily-fixings.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class DailyFixings:
    """Dates and settles aligned by position, both read-only: dates[i] and settles[i] describe
    one fixing. The dates increase, with any gaps between them, and a settle is any number a cell
    holds, zero and below included."""

    dates: NDArray[np.datetime64]
    settles: NDArray[np.float64]


def daily_fixings(dates: NDArray[np.datetime64], settles: NDArray[np.float64]) -> DailyFixings:
    """The one way to make a DailyFixings: its one rule of meaning, that each date is after the
    row above, checked once, vectorized.

    One fixing per day is what the rule keeps, since a date twice would be two settles for one
    day, and the order is the curve's, so a reader finds a day by search. Nothing is sorted: a
    series pasted newest first fails at its second row, and the desk sorts it. Both columns are
    copied and then frozen, so the fixings own their data: a Python caller keeps whatever it
    passed, and a later change to an input never changes a fixing. Rows count as the sheet counts
    them, the first row of the body being row 1.
    """
    days = np.array(dates, dtype="datetime64[D]")
    unordered = days[1:] <= days[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # days[k + 1] is the first date not after the one before it
        raise ValueError(
            f"date row {k + 2} is {days[k + 1]}, expected a date after row {k + 1}'s {days[k]}"
        )
    prices = np.array(settles, dtype=np.float64)
    days.setflags(write=False)
    prices.setflags(write=False)
    return DailyFixings(days, prices)
