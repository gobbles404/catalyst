"""Monthly fixings: the price of one index for each month it fixed, month beside price, as the
desk keeps them, for an index that fixes once a month. docs/library/market-data/monthly-fixings.md
is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class MonthlyFixings:
    """Months and prices aligned by position, both read-only: months[i] and prices[i] describe
    one fixing. The months are numpy months, the library's unit for a contract month, increasing
    with any gaps between them; a price is any number a cell holds, zero and below included."""

    months: NDArray[np.datetime64]
    prices: NDArray[np.float64]


def monthly_fixings(dates: NDArray[np.datetime64], prices: NDArray[np.float64]) -> MonthlyFixings:
    """The one way to make a MonthlyFixings: three rules of meaning, checked once, vectorized.

    One price per month, since the seam never compares two columns; each date the first day of
    its month, which is how a month is typed into a cell, so that a day typed by mistake, the
    26th for May 2026 say, is refused rather than read as its month; and each month after the
    row above, which keeps one fixing per month in the order a reader searches. The months are
    kept as months, never as first-of-month dates, docs/library/time.md, and the prices are
    copied; both are frozen, so the fixings own their data. Rows count as the sheet counts them.
    """
    if prices.size != dates.size:
        have = f"{prices.size} {'price' if prices.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {dates.size}, one per month")
    days = np.asarray(dates, dtype="datetime64[D]")
    months = days.astype("datetime64[M]")
    not_first = months.astype("datetime64[D]") != days
    if not_first.any():
        i = int(not_first.argmax())
        raise ValueError(f"month row {i + 1} is {days[i]}, expected the first day of a month")
    unordered = months[1:] <= months[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # months[k + 1] is the first month not after the one before
        raise ValueError(
            f"month row {k + 2} is {months[k + 1]}, "
            f"expected a month after row {k + 1}'s {months[k]}"
        )
    kept = np.array(prices, dtype=np.float64)
    months.setflags(write=False)
    kept.setflags(write=False)
    return MonthlyFixings(months, kept)
