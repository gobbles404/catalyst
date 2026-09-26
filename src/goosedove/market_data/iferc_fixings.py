"""IFERC fixings: Inside FERC's index for each contract month of one index whose index has been
published, price beside code, as the desk keeps them, for an index settled on the monthly index,
and the index they are the fixings of. docs/library/market-data/iferc-fixings.md is the page."""

from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind, described


@dataclass(frozen=True, slots=True)
class IfercFixings:
    """The index whose fixings these are, kept by reference, and codes and prices aligned by
    position, the prices read-only: codes[i] and prices[i] describe one contract month's index,
    the code labelling the month the index is for, one of the index's months, each once, and
    the price the index as printed, any number, zero and below included. The codes are as the
    desk typed them, in the order given; the day each index printed is the IFERC schedule's,
    not kept here."""

    index: Index
    codes: tuple[str, ...]
    prices: NDArray[np.float64]


def iferc_fixings(
    codes: tuple[str, ...], prices: NDArray[np.float64], index: Index
) -> IfercFixings:
    """The one way to make IfercFixings: four rules of meaning, checked once, in this order, the
    first failure being the message.

    The index is an IFERC index, since the codes are checked against the months of an IFERC
    schedule and only an IFERC index has one. One price per code, since the seam never compares
    two columns and a series is rows. Then one pass over the codes in row order, each code
    striking its month off the set of the index's months not yet given, so the earliest offending
    row is named: each code is one of the index's months, matched exactly, spelling and case as
    typed, since an index for a month the schedule does not hold names nothing; and each code
    once, since a code given twice is two indices for one month and neither can be the month's.
    A code with no month left to strike was either given already, if it is a month of the index,
    or never a month at all. The prices are copied and then frozen, so the fixings own their
    data: a Python caller keeps whatever it passed, and a later change to an input never changes
    a fixing. The codes are the seam's tuple, kept as they are, and the index is kept by
    reference, the one the desk paired the series with. Nothing else is checked: whether a
    month's index has printed by a given day and whether every published month has its index are
    the history's rules, checked against the calendar it takes. Rows count as the sheet counts
    them, the first row of the column being row 1.
    """
    if index.kind is not Kind.IFERC:
        raise ValueError(f"index is {described(index.kind, 'index')}, expected an IFERC index")
    count = len(codes)
    if prices.size != count:
        have = f"{prices.size} {'price' if prices.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {count}, one per contract_code")
    months = cast(IfercSchedule, index.schedule).codes  # an IFERC index has one
    waiting = set(months)  # the months no code has named yet
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
    kept = np.array(prices, dtype=np.float64)
    kept.setflags(write=False)
    return IfercFixings(index, codes, kept)
