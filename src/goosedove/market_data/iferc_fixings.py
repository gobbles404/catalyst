"""IFERC fixings: Inside FERC's index for each contract month of one index whose index has been
published, price beside code, as the desk keeps them, for an index settled on the monthly
index. docs/library/market-data/iferc-fixings.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class IfercFixings:
    """Codes and prices aligned by position, the prices read-only: codes[i] and prices[i]
    describe one contract month's index, the code labelling the month the index is for and the
    price the index as printed, any number, zero and below included. The codes are as the desk
    typed them, each once, in the order given; the day each index printed is the IFERC
    schedule's, not kept here."""

    codes: tuple[str, ...]
    prices: NDArray[np.float64]


def iferc_fixings(codes: tuple[str, ...], prices: NDArray[np.float64]) -> IfercFixings:
    """The one way to make IfercFixings: two rules of meaning, checked once, in this order, the
    first failure being the message.

    One price per code, since the seam never compares two columns and a series is rows. And
    each code once, spelling and case as typed, since a code given twice is two indices for one
    month and neither can be the month's. The prices are copied and then frozen, so the fixings
    own their data: a Python caller keeps whatever it passed, and a later change to an input
    never changes a fixing. The codes are the seam's tuple, kept as they are. Nothing else is
    checked: whether the months are a schedule's, whether they run without a gap and whether a
    month's index has printed are the history's rules, written when the history is. Rows count
    as the sheet counts them, the first row of the column being row 1.
    """
    count = len(codes)
    if prices.size != count:
        have = f"{prices.size} {'price' if prices.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {count}, one per contract_code")
    if len(set(codes)) != count:
        seen: dict[str, int] = {}
        for row, code in enumerate(codes, start=1):
            if code in seen:
                raise ValueError(
                    f"contract_code row {row} is {code!r}, already given at row {seen[code]}"
                )
            seen[code] = row
    kept = np.array(prices, dtype=np.float64)
    kept.setflags(write=False)
    return IfercFixings(codes, kept)
