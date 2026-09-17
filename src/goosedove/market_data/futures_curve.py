"""A futures curve: the price of each contract of one index, code beside price, as the desk keeps
it. docs/library/market-data/futures-curve.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class FuturesCurve:
    """Codes and prices aligned by position, the prices read-only: codes[i] and prices[i]
    describe one contract. The codes are as the desk typed them, in the order given, and a price
    is any number a cell holds, zero and below included: a future has settled below zero."""

    codes: tuple[str, ...]
    prices: NDArray[np.float64]


def futures_curve(codes: tuple[str, ...], prices: NDArray[np.float64]) -> FuturesCurve:
    """The one way to make a FuturesCurve: its one rule of meaning, that the columns line up,
    checked once.

    The prices are copied and then frozen, so the curve owns its data: a Python caller keeps
    whatever it passed, and a later change to an input never changes a curve. The codes are the
    seam's tuple, kept as they are. Nothing else is checked: whether codes repeat or follow the
    schedule's order, and what a price may be, are a reader's rules, written when the reader is.
    """
    if prices.size != len(codes):
        have = f"{prices.size} {'price' if prices.size == 1 else 'prices'}"
        raise ValueError(f"price has {have}, expected {len(codes)}, one per future_code")
    kept = np.array(prices, dtype=np.float64)
    kept.setflags(write=False)
    return FuturesCurve(codes, kept)
