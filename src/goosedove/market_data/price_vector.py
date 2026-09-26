"""A price vector: the futures prices of one index as a vendor feeds them, one column kept as a
snapshot, position by position, under the name of the index it prices.
docs/library/market-data/price-vector.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PriceVector:
    """The name of the index the prices are of, text as typed, and the prices, read-only: one
    float64 per row of the column, in the order given, every value as it arrived, zero, below
    zero and a value repeated included. The name is a label the market compares with the name
    its history's index was created with; no index is held, looked up or kept alive here. What
    a position means, which contract it prices, is the consumer's to say."""

    index_name: str
    prices: NDArray[np.float64]


def price_vector(index_name: str, prices: NDArray[np.float64]) -> PriceVector:
    """The one way to make a PriceVector. It has no rule of meaning: the name is kept as typed,
    never trimmed or re-cased, and whether it names the history's index is the market's rule; a
    vector is the prices as supplied, nothing sorted, rounded, deduplicated, padded, cut or
    bounded, and what a position means belongs to the consumer that reads it, written when the
    consumer is.

    The column is copied once and then frozen, so the vector owns its data: a Python caller
    keeps whatever it passed, and a later change to an input never changes a snapshot. That copy,
    eight bytes a price and float64 whatever arrived, is the whole cost beyond the seam's; the
    name costs the library nothing.
    """
    snapshot = np.array(prices, dtype=np.float64)
    snapshot.setflags(write=False)
    return PriceVector(index_name, snapshot)
