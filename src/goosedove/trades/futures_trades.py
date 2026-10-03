"""One or many futures trades: shared contract facts and aligned, immutable columns."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind


@dataclass(frozen=True, slots=True, eq=False)
class FuturesTrades:
    """Row i is one trade occurrence, including when there is only one row.

    IDs are labels, not unique keys. Input order and repeated occurrences are retained.
    Prices are the agreed deal prices in the index's quote units. Positive lots are buys,
    negative lots sells; lot size stays in the shared specification. Contract positions
    address the index's schedule, not a market price vector. All arrays are owned and read-only.
    """

    index: Index
    specification_position: int
    trade_ids: tuple[str, ...]
    trade_dates: NDArray[np.datetime64]
    contract_codes: tuple[str, ...]
    signed_lots: NDArray[np.float64]
    trade_prices: NDArray[np.float64]
    contract_positions: NDArray[np.intp]


def futures_trades(
    index: Index,
    contract_specification: str,
    trade_ids: tuple[str, ...],
    trade_dates: NDArray[np.datetime64],
    contract_codes: tuple[str, ...],
    signed_lots: NDArray[np.float64],
    trade_prices: NDArray[np.float64],
) -> FuturesTrades:
    """Bind a typed table to its shared index and specification, once.

    The seam supplies aligned columns. Meaning is checked here: a futures index, a named
    specification, unambiguous scheduled contracts and whole, nonzero lots. Prices are not
    rounded or constrained to positive numbers. No calendar, market or valuation is built.
    """
    if index.kind is not Kind.FUTURES:
        raise ValueError(f"index is {index.kind.value!r}, expected a futures index")
    try:
        specification_position = index.specifications.names.index(contract_specification)
    except ValueError:
        raise ValueError(
            f"contract_specification is {contract_specification!r}, "
            "expected a name in the index's specifications"
        ) from None
    contract_positions = _contract_positions(index.schedule.codes, contract_codes)
    fraction = signed_lots != np.floor(signed_lots)
    if fraction.any():
        row = int(fraction.argmax())
        raise ValueError(
            f"signed_lots row {row + 1} is {float(signed_lots[row])!r}, expected a whole number"
        )
    zero = signed_lots == 0.0
    if zero.any():
        row = int(zero.argmax())
        raise ValueError(f"signed_lots row {row + 1} is 0.0, expected nonzero lots")
    dates = np.array(trade_dates, dtype="datetime64[D]")
    lots = np.array(signed_lots, dtype=np.float64)
    prices = np.array(trade_prices, dtype=np.float64)
    for column in (dates, lots, prices, contract_positions):
        column.setflags(write=False)
    return FuturesTrades(
        index,
        specification_position,
        trade_ids,
        dates,
        contract_codes,
        lots,
        prices,
        contract_positions,
    )


def _contract_positions(codes: tuple[str, ...], traded: tuple[str, ...]) -> NDArray[np.intp]:
    """Resolve text identifiers once; numerical consumers never parse contract codes."""
    positions = {code: position for position, code in enumerate(codes)}
    if len(positions) != len(codes):
        raise ValueError("index schedule has duplicate contract codes, expected each code once")
    resolved = np.fromiter(
        (positions.get(code, -1) for code in traded), dtype=np.intp, count=len(traded)
    )
    missing = resolved < 0
    if missing.any():
        row = int(missing.argmax())
        raise ValueError(
            f"contract_code row {row + 1} is {traded[row]!r}, "
            "expected a code in the index's schedule"
        )
    return resolved
