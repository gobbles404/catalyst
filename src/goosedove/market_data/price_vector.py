"""A price vector: the futures prices of one index as a vendor feeds them, one column kept as a
snapshot, position by position. docs/library/market-data/price-vector.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PriceVector:
    """The prices, read-only: one float64 per row of the column, in the order given, every
    value as it arrived, zero, below zero and a value repeated included. What a position means,
    which contract it prices, is the consumer's to say."""

    prices: NDArray[np.float64]


def price_vector(prices: NDArray[np.float64]) -> PriceVector:
    """The one way to make a PriceVector. It has no rule of meaning: a vector is the prices as
    supplied, nothing sorted, rounded, deduplicated, padded, cut or bounded, and what a position
    means belongs to the consumer that reads it, written when the consumer is.

    The column is copied once and then frozen, so the vector owns its data: a Python caller
    keeps whatever it passed, and a later change to an input never changes a snapshot. That copy,
    eight bytes a price and float64 whatever arrived, is the whole cost beyond the seam's.
    """
    snapshot = np.array(prices, dtype=np.float64)
    snapshot.setflags(write=False)
    return PriceVector(snapshot)
