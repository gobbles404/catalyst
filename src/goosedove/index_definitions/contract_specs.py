"""Contract specs: the name of each contract one index trades as, the quantity in one lot of it,
and the brokerage and clearing charged per lot, one row per contract, so that an index traded on
more than one exchange, NYMEX lots and ICE lots of gas say, has a spec for each.
docs/library/index-definitions/contract-specs.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class ContractSpecs:
    """Names, lot sizes and the two fees aligned by position, the arrays read-only: names[i],
    lot_sizes[i], brokerage_rates_per_lot[i] and clearing_rates_per_lot[i] describe one contract.
    The names are as the desk typed them, each once; a lot size is a whole number of the
    contract's quantity unit, and a fee a number with any fraction."""

    names: tuple[str, ...]
    lot_sizes: NDArray[np.float64]
    brokerage_rates_per_lot: NDArray[np.float64]
    clearing_rates_per_lot: NDArray[np.float64]


def contract_specs(
    names: tuple[str, ...],
    lot_sizes: NDArray[np.float64],
    brokerage_rates_per_lot: NDArray[np.float64],
    clearing_rates_per_lot: NDArray[np.float64],
) -> ContractSpecs:
    """The one way to make a ContractSpecs: its two rules of meaning, checked once, in this order.

    Each contract is named once, since a name twice would be two specs for one contract; and each
    lot size is whole, since a lot is a whole number of the contract's quantity unit. The seam
    hands the lot sizes over as the numbers the cells hold, and a whole double goes back out as it
    came, so no line at 2^53 is drawn here. Nothing else is checked yet, and that is a task for
    later, noted here rather than on a backlog: whether a lot size must be at least one, whether a
    fee may be negative, a rebate, and which unit the fees are in, are decided when the first
    consumer needs them to mean something. The three columns of numbers are copied and then
    frozen, so the specs own their data; the names are the seam's tuple, kept as they are. Rows
    count as the sheet counts them, the first row of the body being row 1.
    """
    if len(set(names)) != len(names):
        seen: dict[str, int] = {}
        for row, name in enumerate(names, start=1):
            if name in seen:
                raise ValueError(f"name row {row} is {name!r}, already given at row {seen[name]}")
            seen[name] = row
    lots = np.array(lot_sizes, dtype=np.float64)
    fraction = lots != np.floor(lots)
    if fraction.any():
        i = int(fraction.argmax())
        raise ValueError(f"lot_size row {i + 1} is {float(lots[i])!r}, expected a whole number")
    brokerage = np.array(brokerage_rates_per_lot, dtype=np.float64)
    clearing = np.array(clearing_rates_per_lot, dtype=np.float64)
    for column in (lots, brokerage, clearing):
        column.setflags(write=False)
    return ContractSpecs(names, lots, brokerage, clearing)
