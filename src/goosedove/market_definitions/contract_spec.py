"""A contract spec: the name of one contract, the quantity in one lot of it, and the brokerage
and clearing charged per lot. docs/library/market-definitions/contract-spec.md is the page."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContractSpec:
    """Four facts as the desk gave them: the name, WTI say; the lot size, a whole number of the
    contract's quantity unit, 1000 say; and the two fees per lot, numbers with any fraction."""

    name: str
    lot_size: int
    brokerage_rate_per_lot: float
    clearing_rate_per_lot: float


def contract_spec(
    name: str, lot_size: int, brokerage_rate_per_lot: float, clearing_rate_per_lot: float
) -> ContractSpec:
    """The one way to make a ContractSpec: the four facts kept as given.

    Nothing is checked yet, and that is a task for later, noted here rather than on a backlog:
    whether a lot size must be at least one, whether a fee may be negative, a rebate, and which
    unit the fees are in, are decided when the first consumer needs them to mean something.
    Until then the name is text as typed, and the numbers are the numbers.
    """
    return ContractSpec(name, lot_size, brokerage_rate_per_lot, clearing_rate_per_lot)
