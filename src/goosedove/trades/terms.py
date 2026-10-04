"""The resolved terms of a batch of trades: which deals were struck, under which definitions, as
the resolution child of _CreateTrades will establish them from a template and a ticket, and as
tests supply them in Python until it does. One index for the batch, one specification of it,
one route, one settlement and one schedule method; then the occurrences, the ticket's rows, each
with its date and its label; then the components, one per contract month an occurrence holds,
each with its occurrence, its contract, its signed lots and its fixed price, and for a financial
settlement the day it pays. docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass
from enum import Enum
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind, described

LOT = "LOT"  # the one quantity unit of the first future profile: lots of the specification


class Route(Enum):
    """How the trade is arranged for clearing: the result's labels follow it."""

    CLEARED = "cleared"
    BILATERAL = "bilateral"


class Settlement(Enum):
    """How the contract settles at the end: delivered, or paid in money on a day."""

    PHYSICAL = "physical"
    FINANCIAL = "financial"


class ScheduleMethod(Enum):
    """Which observations set a contract's final price. lastday, the settlement on the contract's
    last trading day, is the one method built; asian, penultimate and last3day join it here when
    they are built, and until then are refused by name where a ticket names them."""

    LASTDAY = "lastday"


class QuantityPer(Enum):
    """What the entered quantity is per: each contract month, or each calendar day of it. month
    is the one basis built; day joins it when it is."""

    MONTH = "month"


@dataclass(frozen=True, slots=True)
class ResolvedTrades:
    """The index, by reference, its futures schedule, the same object the index holds, typed as
    the kind rule found it, and the row of its specifications the batch trades as; the
    route, the settlement and the schedule method, one each for the batch; the quantity unit and
    basis the lots are stated in. Then two sets of columns aligned by position, all read-only.
    Per occurrence, the ticket's rows in order: trade_dates[i] the day the deal was struck and
    labels[i] its trade_id, or None for the whole tuple when the ticket gave none. Per component,
    the contract months the occurrences hold: occurrence[k] the row of the occurrence it belongs
    to, contract[k] the row of the schedule its month is, lots[k] the signed whole number of lots,
    fixed_price[k] the price agreed, in the index's quote units, and payment_date[k] the day it
    pays, an array for a financial settlement and None for a physical one, which pays on no day."""

    index: Index
    schedule: FuturesSchedule
    specification: int
    route: Route
    settlement: Settlement
    schedule_method: ScheduleMethod
    quantity_unit: str
    quantity_per: QuantityPer
    labels: tuple[str, ...] | None
    trade_dates: NDArray[np.datetime64]
    occurrence: NDArray[np.intp]
    contract: NDArray[np.intp]
    lots: NDArray[np.float64]
    fixed_price: NDArray[np.float64]
    payment_date: NDArray[np.datetime64] | None

    def named(self, component: int) -> str:
        """A component's trade named in a message, by its label when the ticket gave one and by
        its row as the sheet counts rows either way: `trade 'NG-001' at row 1`, `trade at row 3`."""
        row = int(self.occurrence[component])
        if self.labels is None:
            return f"trade at row {row + 1}"
        return f"trade {self.labels[row]!r} at row {row + 1}"


def resolved_trades(
    index: Index,
    specification: int,
    route: Route,
    settlement: Settlement,
    schedule_method: ScheduleMethod,
    quantity_unit: str,
    quantity_per: QuantityPer,
    labels: tuple[str, ...] | None,
    trade_dates: NDArray[np.datetime64],
    occurrence: NDArray[np.intp],
    contract: NDArray[np.intp],
    lots: NDArray[np.float64],
    fixed_price: NDArray[np.float64],
    payment_date: NDArray[np.datetime64] | None,
) -> ResolvedTrades:
    """The one way to make ResolvedTrades: the rules of the first future profile, checked once,
    in this order, the first failure being the message; then the columns copied and frozen.

    The index is a futures index, since a future's contract is a row of a futures schedule and
    its final price the settlement on that row's expiry day. The specification is a row of the
    index's specifications, since the lot size is read there. The quantity unit is LOT, the one
    unit built; a quantity in MMBTU or barrels waits for the conversion rule that would read it.
    The occurrences are the ticket's rows: one date each, and one label each when labels are
    given. The components are aligned, one or more, each belonging to an occurrence, every
    occurrence holding at least one, since a trade with no contract month has no economics;
    each contract is a row of the schedule; each lot count is a whole, nonzero number, the first
    profile's convention, a signed count of lots; each fixed price is a finite number. A
    financial settlement has one payment date per component and a physical one has none: a
    physical future pays on no day, and giving it one would invent a payment the contract does
    not make.
    """
    schedule = _the_batch(index, specification, quantity_unit)
    occurrences = _the_occurrences(trade_dates, labels)
    _the_components(occurrence, contract, lots, fixed_price, occurrences, len(schedule.codes))
    pays = _the_payment_dates(settlement, payment_date, occurrence.size)
    return ResolvedTrades(
        index,
        schedule,
        specification,
        route,
        settlement,
        schedule_method,
        quantity_unit,
        quantity_per,
        labels,
        _frozen_days(trade_dates),
        _frozen_rows(occurrence),
        _frozen_rows(contract),
        _frozen_numbers(lots),
        _frozen_numbers(fixed_price),
        pays,
    )


def _the_batch(index: Index, specification: int, quantity_unit: str) -> FuturesSchedule:
    """A futures index, a row of its specifications, and lots: the index's schedule, typed."""
    if index.kind is not Kind.FUTURES:
        raise ValueError(
            f"index is {described(index.kind, 'index')}, expected a futures index for a future"
        )
    rows = len(index.specifications.names)
    if not 0 <= specification < rows:
        raise ValueError(
            f"specification is {specification}, "
            f"expected a row of the index's specifications, 0 to {rows - 1}"
        )
    if quantity_unit != LOT:
        raise ValueError(
            f"quantity_unit is {quantity_unit!r}, expected {LOT}, the one quantity unit built"
        )
    return cast(FuturesSchedule, index.schedule)  # what the kind just said


def _the_occurrences(trade_dates: NDArray[np.datetime64], labels: tuple[str, ...] | None) -> int:
    """One or more, a date each and, when labels are given, a label each: their count."""
    occurrences = trade_dates.size
    if occurrences == 0:
        raise ValueError("trade_dates has 0 dates, expected at least 1, one per occurrence")
    if labels is not None and len(labels) != occurrences:
        raise ValueError(
            f"labels has {len(labels)} texts, expected {occurrences}, one per occurrence"
        )
    return occurrences


def _the_components(
    occurrence: NDArray[np.intp],
    contract: NDArray[np.intp],
    lots: NDArray[np.float64],
    fixed_price: NDArray[np.float64],
    occurrences: int,
    schedule_rows: int,
) -> None:
    """Aligned, one or more, each of an occurrence and every occurrence holding one; each
    contract a row of the schedule, each lot count whole and nonzero, each price finite."""
    components = occurrence.size
    if components == 0:
        raise ValueError("occurrence has 0 rows, expected at least 1, one per component")
    for name, column in (("contract", contract), ("lots", lots), ("fixed_price", fixed_price)):
        if column.size != components:
            raise ValueError(
                f"{name} has {column.size} rows, expected {components}, one per component"
            )
    outside = (occurrence < 0) | (occurrence >= occurrences)
    if outside.any():
        k = int(outside.argmax())
        raise ValueError(
            f"occurrence row {k + 1} is {occurrence[k]}, "
            f"expected an occurrence, 0 to {occurrences - 1}"
        )
    held = np.bincount(occurrence, minlength=occurrences)
    if (held == 0).any():
        i = int((held == 0).argmax())
        raise ValueError(f"trade at row {i + 1} has no component, expected at least one")
    outside = (contract < 0) | (contract >= schedule_rows)
    if outside.any():
        k = int(outside.argmax())
        raise ValueError(
            f"contract row {k + 1} is {contract[k]}, "
            f"expected a row of the schedule, 0 to {schedule_rows - 1}"
        )
    fractional = ~np.isfinite(lots) | (lots != np.round(lots))
    if fractional.any():
        k = int(fractional.argmax())
        raise ValueError(f"lots row {k + 1} is {float(lots[k])!r}, expected a whole number of lots")
    if (lots == 0).any():
        k = int((lots == 0).argmax())
        raise ValueError(f"lots row {k + 1} is {float(lots[k])!r}, expected a nonzero quantity")
    unfinished = ~np.isfinite(fixed_price)
    if unfinished.any():
        k = int(unfinished.argmax())
        raise ValueError(
            f"fixed_price row {k + 1} is {float(fixed_price[k])!r}, expected a finite price"
        )


def _the_payment_dates(
    settlement: Settlement, payment_date: NDArray[np.datetime64] | None, components: int
) -> NDArray[np.datetime64] | None:
    """One per component for a financial settlement, none for a physical one, frozen."""
    match settlement:
        case Settlement.FINANCIAL:
            if payment_date is None:
                raise ValueError(
                    "payment_date is missing, expected one date per component "
                    "with a financial settlement"
                )
            if payment_date.size != components:
                raise ValueError(
                    f"payment_date has {payment_date.size} dates, expected {components}, "
                    "one per component"
                )
            return _frozen_days(payment_date)
        case Settlement.PHYSICAL:
            if payment_date is not None:
                raise ValueError(
                    f"payment_date has {payment_date.size} dates, "
                    "expected none with a physical settlement, which pays on no day"
                )
            return None
        case _:
            assert_never(settlement)


# Each column copied into its type and frozen, so the record owns its data: a Python caller
# keeps whatever it passed, and a later change to an input never changes a batch.


def _frozen_rows(column: NDArray[np.intp]) -> NDArray[np.intp]:
    rows = np.array(column, dtype=np.intp)
    rows.setflags(write=False)
    return rows


def _frozen_numbers(column: NDArray[np.float64]) -> NDArray[np.float64]:
    numbers = np.array(column, dtype=np.float64)
    numbers.setflags(write=False)
    return numbers


def _frozen_days(column: NDArray[np.datetime64]) -> NDArray[np.datetime64]:
    days = np.array(column, dtype="datetime64[D]")
    days.setflags(write=False)
    return days
