"""Published fixings: the price of each print of one published index that has a price, price
beside the print's publication date, as the desk keeps them, the newest at the top, each date one
of the index's schedule, kept oldest first by the print each belongs to, and the index they are
the fixings of. docs/library/market-data/published-fixings.md is the page."""

from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray

from catalyst.index_definitions.index import Index
from catalyst.index_definitions.kind import Kind, described
from catalyst.index_definitions.published_schedule import PublishedSchedule


@dataclass(frozen=True, slots=True)
class PublishedFixings:
    """The index whose fixings these are, kept by reference, and prints and prices aligned by
    position, both read-only: rows[i] is the print prices[i] is the price of, its row of the
    index's schedule, which is its row of every calendar over that index, increasing, each print
    once; prices[i] the price dated that print's publication date, any number a cell holds, zero
    and below included. The sheet gives the series newest first, and it is kept oldest first,
    the order the history reads it in. A print's date is the schedule's, read through its row
    and not kept here. Whether a price is the publisher's or a stand-in the desk entered before
    the publisher released it is no fact of the record: both are a number beside a date."""

    index: Index
    rows: NDArray[np.intp]
    prices: NDArray[np.float64]


def published_fixings(
    publication_date: NDArray[np.datetime64], price: NDArray[np.float64], index: Index
) -> PublishedFixings:
    """The one way to make PublishedFixings: four rules of meaning, checked once, vectorized, in
    this order, the first failure being the message, then each price's print and the prices kept
    the other way up.

    The series is given as the desk keeps it, the newest print in the first row, so that a new
    price is a row added at the top. The index is a published index, since the dates are checked
    against the prints of a published schedule and only a published index has one. One price per
    date, since the seam never compares two columns and a series is rows. Each date before the
    row above, one comparison over the column as the sheet gave it, which keeps the newest first
    and refuses a date given twice; nothing is sorted, so a series pasted oldest first fails at
    its second row. And each date the publication date of one of the index's prints, found by
    one search of the schedule's dates, which the schedule holds in order: a price dated a day
    the schedule does not list names no print, so history from before the schedule's first row
    stays off the sheet, and so does a price dated the day its publisher released it. Rows count
    as the sheet counts them, the first row of a column being row 1, and within a rule the first
    row from the top that breaks it is named.

    Then the prices are copied once from the last row to the first and frozen, and each price's
    print is the row the search found, so what is kept runs oldest first, each price beside its
    own print. The fixings own their data, and the index is kept by reference, the one the desk
    paired the series with. Nothing else is checked: which prints have fixed by a given day, and
    whether every fixed print has its price, are the history's rules, checked against the
    calendar it takes; the fixings take no valuation date.
    """
    if index.kind is not Kind.PUBLISHED:
        raise ValueError(f"index is {described(index.kind, 'index')}, expected a published index")
    count = publication_date.size
    if price.size != count:
        have = f"{price.size} {'price' if price.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {count}, one per publication_date")
    # The column's order runs on the rows as the sheet gave them, newest first, nothing copied yet.
    unordered = publication_date[1:] >= publication_date[:-1]
    if unordered.any():
        k = int(unordered.argmax())  # publication_date[k + 1] is the first not before its row above
        raise ValueError(
            f"publication_date row {k + 2} is {publication_date[k + 1]}, "
            f"expected a date before row {k + 1}'s {publication_date[k]}"
        )
    listed = cast(PublishedSchedule, index.schedule).publication_date  # a published index has one
    days = publication_date[::-1]  # oldest first, a view
    rows = np.searchsorted(listed, days)
    unlisted = rows >= listed.size  # a date after the schedule's last print
    inside = ~unlisted
    unlisted[inside] = listed[rows[inside]] != days[inside]
    if unlisted.any():
        j = int(unlisted.nonzero()[0][-1])  # the last oldest first is the first from the top
        raise ValueError(
            f"publication_date row {count - j} is {days[j]}, expected the publication date of one "
            "of the index's prints"
        )
    prices = np.array(price[::-1], dtype=np.float64)
    for column in (rows, prices):
        column.setflags(write=False)
    return PublishedFixings(index, rows, prices)
