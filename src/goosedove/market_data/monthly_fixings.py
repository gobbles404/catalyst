"""Monthly fixings: the price of one index for each contract month, dated by the day the index's
schedule says its settle is published, price beside publication date, as the desk keeps them,
for an index published once a month; a price is what the desk holds for the month, the settle
once published or a provisional value supplied before it appears, keyed by the same day.
docs/library/market-data/monthly-fixings.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class MonthlyFixings:
    """Publication dates and prices aligned by position, both read-only: publication_dates[i]
    and prices[i] describe one fixing. The dates are the schedule's publication dates from the
    first to the last, every one and no other, increasing, past or still to come; a price is
    any number a cell holds, zero and below included, published or provisional, which nothing
    here tells apart. The schedule the dates were checked against is not kept."""

    publication_dates: NDArray[np.datetime64]
    prices: NDArray[np.float64]


def monthly_fixings(
    publication_dates: NDArray[np.datetime64],
    prices: NDArray[np.float64],
    scheduled: NDArray[np.datetime64] | None,
) -> MonthlyFixings:
    """The one way to make a MonthlyFixings: five rules of meaning, checked once, vectorized,
    in this order, the first failure being the message.

    The schedule has publication dates, since a schedule without them says nothing about when a
    settle appears. One price per date, since the seam never compares two columns. Each date
    after the row above, which keeps one fixing per publication in the order a reader searches;
    nothing is sorted, so a series pasted newest first fails at its second row. Each date is one
    the schedule publishes on, before its first and after its last as much as between them,
    since a price on any other day is not this index's monthly settle; a date still to come is
    as good a key as a past one, the value a provisional one until the settle appears. And no
    publication
    between the first date and the last is without a fixing, since a gap is a row the desk did
    not paste: with every date scheduled and the dates increasing, the series is whole exactly
    when each date is the schedule's next publication after the one above, one search over the
    column. The schedule's dates are read as a set, sorted once into a copy of their own, so
    their order and any repetition change nothing and the schedule is not written to; what they
    say is authoritative, a weekend or a holiday included, since whoever wrote the schedule has
    already moved a publication off a closed day. Both columns are copied and then frozen, so
    the fixings own their data. Rows count as the sheet counts them, the first row of the
    column being row 1.
    """
    if scheduled is None:
        raise ValueError(
            "expiry_schedule has no publication dates, expected a schedule with one per contract"
        )
    if prices.size != publication_dates.size:
        have = f"{prices.size} {'price' if prices.size == 1 else 'prices'}"
        raise ValueError(
            f"price has {have}, expected {publication_dates.size}, one per publication_date"
        )
    days = np.array(publication_dates, dtype="datetime64[D]")
    unordered = days[1:] <= days[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # days[k + 1] is the first date not after the one before it
        raise ValueError(
            f"publication_date row {k + 2} is {days[k + 1]}, "
            f"expected a date after row {k + 1}'s {days[k]}"
        )
    published = np.unique(scheduled)  # sorted, each date once, a copy of its own
    places = np.searchsorted(published, days)
    absent = published[np.minimum(places, published.size - 1)] != days
    if absent.any():
        k = int(absent.argmax())  # days[k] is the first date the schedule does not publish on
        raise ValueError(
            f"publication_date row {k + 1} is {days[k]}, "
            "expected one of the schedule's publication dates"
        )
    following = published[places[:-1] + 1]  # each date's next publication, which exists
    skipped = following != days[1:]
    if skipped.any():
        k = int(skipped.argmax())  # following[k] is the first publication without a fixing
        raise ValueError(
            f"publication_date row {k + 2} is {days[k + 1]}, expected {following[k]}, "
            f"the schedule's publication after row {k + 1}'s {days[k]}"
        )
    kept = np.array(prices, dtype=np.float64)
    days.setflags(write=False)
    kept.setflags(write=False)
    return MonthlyFixings(days, kept)
