"""Contract specifications: the desk's words for a quantity of one index, a contract or a bare
unit, each with the quantity in one lot of it, the unit that quantity is in, and the brokerage
and clearing charged per lot, one row per word, so that gas dealt as NYMEX lots, as ICE lots
and in MMBTU has a row for each. docs/library/index-definitions/contract-specifications.md is
the page."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.index_conventions import listed, measures_of


@dataclass(frozen=True, slots=True)
class ContractSpecifications:
    """Names, lot sizes, lot units and the two fees aligned by position, the arrays read-only:
    names[i], lot_sizes[i], lot_units[i], brokerage_rates_per_lot[i] and
    clearing_rates_per_lot[i] describe one word for a quantity. The names are as the desk typed
    them, each once; a lot size is a whole number, 1 or more, of the lot unit, a code of the
    unit tables kept as typed; a fee is a cost per lot in the index's settlement currency, a
    number with any fraction, 0 or more."""

    names: tuple[str, ...]
    lot_sizes: NDArray[np.float64]
    lot_units: tuple[str, ...]
    brokerage_rates_per_lot: NDArray[np.float64]
    clearing_rates_per_lot: NDArray[np.float64]


def contract_specifications(
    names: tuple[str, ...],
    lot_sizes: NDArray[np.float64],
    lot_units: tuple[str, ...],
    brokerage_rates_per_lot: NDArray[np.float64],
    clearing_rates_per_lot: NDArray[np.float64],
    units: UnitConversions,
) -> ContractSpecifications:
    """The one way to make a ContractSpecifications: six rules of meaning, checked once, in this
    order, the first failure being the message, and within a rule the first offending row named.

    Each word is named once, since a name twice would be two specifications for one word. Each
    lot size is whole, since a lot is a whole number of its unit, and 1 or more, since a lot of
    nothing, or of a negative quantity, is no lot; a whole lot size below one fails the second of
    those, so -3 reads `expected 1 or more`. Each lot unit is a unit of a category a quantity can
    measure, volume, mass or energy, in the tables passed in, matched exactly as a code and never
    trimmed or re-cased; whether it is a unit of the index's own category is the index's rule,
    since nothing here holds the conventions, so a barrel row and a gallon row stand side by side
    here and MMBTU beside them, and the index refuses the one that is not its measure. Each
    brokerage rate,
    then each clearing rate, is 0 or more, since a fee is a charge and zero is no charge; a rebate
    is not a fee, and a negative rate is refused as the mistyped charge it most often is. The
    fees are costs per lot in the index's settlement currency, which the consumer reads off the
    index; nothing here holds the conventions, so nothing here checks it. The seam hands the lot
    sizes over as the numbers the cells hold, and a whole double goes back out as it came, so no
    line at 2^53 is drawn here. The three columns of numbers are copied and then frozen, so the
    specifications own their data, each rule one look over its column; the names and the lot
    units are the seam's tuples, kept as they are, the units read against the tables by key.
    Rows count as the sheet counts them, the first row of the body being row 1.
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
    measures = measures_of(units)
    quantity_units = {unit for measure in measures for unit in units.categories[measure].sizes}
    for row, unit in enumerate(lot_units, start=1):
        if unit not in quantity_units:
            raise ValueError(f"lot_unit row {row} is {unit!r}, expected a {listed(measures)} unit")
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
    return ContractSpecifications(names, lots, lot_units, brokerage, clearing)
