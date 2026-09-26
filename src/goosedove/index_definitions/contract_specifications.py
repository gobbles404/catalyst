"""Contract specifications: the name of each contract one index trades as, the quantity in one
lot of it, and the brokerage and clearing charged per lot, one row per contract, so that an index
traded on more than one exchange, NYMEX lots and ICE lots of gas say, has a row for each.
docs/library/index-definitions/contract-specifications.md is the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class ContractSpecifications:
    """Names, lot sizes and the two fees aligned by position, the arrays read-only: names[i],
    lot_sizes[i], brokerage_rates_per_lot[i] and clearing_rates_per_lot[i] describe one contract.
    The names are as the desk typed them, each once; a lot size is a whole number of the
    contract's quantity unit, 1 or more; a fee is a cost per lot in the index's settlement
    currency, a number with any fraction, 0 or more."""

    names: tuple[str, ...]
    lot_sizes: NDArray[np.float64]
    brokerage_rates_per_lot: NDArray[np.float64]
    clearing_rates_per_lot: NDArray[np.float64]


def contract_specifications(
    names: tuple[str, ...],
    lot_sizes: NDArray[np.float64],
    brokerage_rates_per_lot: NDArray[np.float64],
    clearing_rates_per_lot: NDArray[np.float64],
) -> ContractSpecifications:
    """The one way to make a ContractSpecifications: five rules of meaning, checked once, in this
    order, the first failure being the message, and within a rule the first offending row named.

    Each contract is named once, since a name twice would be two specifications for one contract.
    Each lot size is whole, since a lot is a whole number of the contract's quantity unit, and 1
    or more, since a lot of nothing, or of a negative quantity, is no contract; a whole lot size
    below one fails the second of those, so -3 reads `expected 1 or more`. Each brokerage rate,
    then each clearing rate, is 0 or more, since a fee is a charge and zero is no charge; a rebate
    is not a fee, and a negative rate is refused as the mistyped charge it most often is. The
    fees are costs per lot in the index's settlement currency, which the consumer reads off the
    index; nothing here holds the conventions, so nothing here checks it. The seam hands the lot
    sizes over as the numbers the cells hold, and a whole double goes back out as it came, so no
    line at 2^53 is drawn here. The three columns of numbers are copied and then frozen, so the
    specifications own their data, each rule one look over its column; the names are the seam's
    tuple, kept as they are. Rows count as the sheet counts them, the first row of the body being
    row 1.
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
    below_one = lots < 1.0
    if below_one.any():
        i = int(below_one.argmax())
        raise ValueError(f"lot_size row {i + 1} is {float(lots[i])!r}, expected 1 or more")
    brokerage = np.array(brokerage_rates_per_lot, dtype=np.float64)
    clearing = np.array(clearing_rates_per_lot, dtype=np.float64)
    for argument, fees in (
        ("brokerage_rate_per_lot", brokerage),
        ("clearing_rate_per_lot", clearing),
    ):
        negative = fees < 0.0
        if negative.any():
            i = int(negative.argmax())
            raise ValueError(f"{argument} row {i + 1} is {float(fees[i])!r}, expected 0 or more")
    for column in (lots, brokerage, clearing):
        column.setflags(write=False)
    return ContractSpecifications(names, lots, brokerage, clearing)
