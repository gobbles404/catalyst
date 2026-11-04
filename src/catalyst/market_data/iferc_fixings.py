"""IFERC fixings: Inside FERC's index for each contract month of one index whose index has been
published, price beside code, as the desk keeps them, the newest month at the top, kept oldest
first, for an index settled on the monthly index, and the index they are the fixings of.
docs/library/market-data/iferc-fixings.md is the page."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray

from catalyst.index_definitions.iferc_schedule import IfercSchedule
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.kind import Kind, described


@dataclass(frozen=True, slots=True)
class IfercFixings:
    """The index whose fixings these are, kept by reference, and codes and prices aligned by
    position, the prices read-only: codes[i] and prices[i] describe one contract month's index,
    the code labelling the month the index is for, one of the index's months, each once, and
    the price the index as printed, any number, zero and below included. The months run oldest
    first, by the day each month's index printed, the IFERC schedule's publication day beside
    the code: the sheet gives the series newest first, and it is kept the other way up, the
    order the history reads it in. The codes are as the desk typed them; the day each index
    printed is the schedule's, not kept here."""

    index: Index
    codes: tuple[str, ...]
    prices: NDArray[np.float64]


def iferc_fixings(
    codes: tuple[str, ...], prices: NDArray[np.float64], index: Index
) -> IfercFixings:
    """The one way to make IfercFixings: six rules of meaning, checked once, in this order, the
    first failure being the message, then the two columns kept the other way up.

    The series is given as the desk keeps it, the newest month in the first row, so that a new
    month is a row added at the top. The index is an IFERC index, since the codes are checked
    against the months of an IFERC schedule and only an IFERC index has one. One price per code,
    since the seam never compares two columns and a series is rows. Then one pass over the codes
    in row order, each code striking its month off the set of the index's months not yet given,
    so the earliest offending row is named: each code is one of the index's months, matched
    exactly, spelling and case as typed, since an index for a month the schedule does not hold
    names nothing; and each code once, since a code given twice is two indices for one month and
    neither can be the month's. A code with no month left to strike was either given already, if
    it is a month of the index, or never a month at all. Then the day each code's index printed
    is read off the schedule, the publication day beside the month: a code the schedule holds at
    two rows names two days and is refused, in row order, while a month held twice that no code
    names is left to the calendar, whose rule it is; and each month printed before the month
    above's, one comparison over the column as the sheet gave it, which keeps the newest first
    and refuses two months printed on one day. Nothing is sorted, so a series pasted oldest first
    fails at its second row and one direction is the only one taken; the order is read from the
    schedule's days alone, never from a code's spelling, its row in the schedule or the day its
    future stopped trading. Rows count as the sheet counts them, the first row of the column
    being row 1, and within a rule the first row from the top that breaks it is named; a rule
    earlier in the order is reported before a later one, whichever row each is on.

    Then both columns are kept from the last row to the first: the codes as a tuple the other
    way up, and the prices copied once and frozen, so what is kept runs oldest first, each price
    beside its own code, the order the market history reads. The fixings own their data, a
    Python caller keeps whatever it passed, and a later change to an input never changes a
    fixing; the index is kept by reference, the one the desk paired the series with. Nothing
    else is checked: whether a month's index has printed by a given day and whether every
    published month has its index are the history's rules, checked against the calendar it
    takes.
    """
    if index.kind is not Kind.IFERC:
        raise ValueError(f"index is {described(index.kind, 'index')}, expected an IFERC index")
    count = len(codes)
    if prices.size != count:
        have = f"{prices.size} {'price' if prices.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {count}, one per contract_code")
    schedule = cast(IfercSchedule, index.schedule)  # an IFERC index has one
    months = schedule.codes
    waiting = set(months)  # the months no code has named yet
    held_twice = len(waiting) != len(months)  # some month at two rows of the schedule; which, below
    for row, code in enumerate(codes, start=1):
        if code in waiting:
            waiting.remove(code)
        elif code in months:  # a month of the index, so one already struck off
            raise ValueError(
                f"contract_code row {row} is {code!r}, already given at row {codes.index(code) + 1}"
            )
        else:
            raise ValueError(
                f"contract_code row {row} is {code!r}, expected one of the index's months"
            )
    # The day each code's index printed, read off its row of the schedule. A code the schedule
    # holds at two rows names two days, so it is refused before any day is read, in row order;
    # the schedule's other months are not looked at, a month held twice that no code names being
    # the calendar's to refuse.
    if held_twice:
        for row, code in enumerate(codes, start=1):
            if months.count(code) > 1:
                at = _listed(k for k, month in enumerate(months, start=1) if month == code)
                raise ValueError(
                    f"contract_code row {row} is {code!r}, a month the index's schedule holds "
                    f"at rows {at}, expected a month it holds once"
                )
    place = {month: k for k, month in enumerate(months)}
    published = schedule.publication_date[np.array([place[code] for code in codes], dtype=np.intp)]
    # Each month printed before the month above's, one comparison over the column as the sheet
    # gave it, newest first, nothing copied yet: published[k + 1] is the first day from the top
    # that is not before the row above's.
    unordered = published[1:] >= published[:-1]
    if unordered.any():
        k = int(unordered.argmax())
        raise ValueError(
            f"contract_code row {k + 2} is {codes[k + 1]!r}, published {published[k + 1]}, "
            f"expected a month published before row {k + 1}'s {codes[k]!r}, "
            f"published {published[k]}"
        )
    # The one copy of the prices, read from the last row back, and the codes the other way up:
    # oldest first, each price beside its own code.
    kept = np.array(prices[::-1], dtype=np.float64)
    kept.setflags(write=False)
    return IfercFixings(index, codes[::-1], kept)


def _listed(rows: Iterable[int]) -> str:
    """Rows as a sentence counts them: 2 and 3, or 2, 3 and 5."""
    *first, last = (str(row) for row in rows)
    return f"{', '.join(first)} and {last}"
