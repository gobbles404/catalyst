"""The resolved terms of a batch of trades: which deals were struck, under which definitions, as
the resolution child of _CreateTrades establishes them from a template and a ticket, and as
tests supply them in Python. One instrument and one index for the batch, one specification of
the index, the quantity unit its quantities count, one route, one settlement and one schedule
method; then the occurrences, the ticket's rows, each with its date, its label, its clearing
house and its broker where given; then the components, one per contract month an occurrence
holds, each with its occurrence, its contract, its signed quantity and its fixed price; and for
a financial settlement the payment terms, the lag and the calendar each occurrence pays by and
the day each component pays. docs/library/trades/kernel.md is the page."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind, described
from goosedove.instruments.definitions import Instrument


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
    last trading day, and penultimate, the settlement on the business day before it, are the two
    methods built; asian and last3day join them here when they are built, and until then are
    refused by name where a ticket names them."""

    LASTDAY = "lastday"
    PENULTIMATE = "penultimate"


class QuantityPer(Enum):
    """What the entered quantity is per: each contract month, or each calendar day of it. month
    is the one basis built; day joins it when it is."""

    MONTH = "month"


@dataclass(frozen=True, slots=True)
class PaymentTerms:
    """How a financial settlement pays, kept with the days it gives so that a batch explains its
    own payment days. Per occurrence: lag_days[i], the positive whole number of business days
    after a component's last observation day the occurrence pays, `+2bd` read once as 2, and
    calendar[i], the holiday calendar those days are counted on, the object the ticket's handle
    stood for, held by reference. Per component: date[k], the day it pays, counted from its last
    observation day, its contract's expiry under lastday and the business day before under
    penultimate, by its occurrence's lag on its occurrence's calendar."""

    lag_days: NDArray[np.int64]
    calendar: tuple[HolidayCalendar, ...]
    date: NDArray[np.datetime64]


@dataclass(frozen=True, slots=True)
class ResolvedTrades:
    """The instrument, the definition the terms were resolved under; the index, by reference, its
    futures schedule, the same object the index holds, typed as the kind rule found it, and the
    row of its specifications the batch's quantities count, the one selection, the desk's word
    for a quantity of the index that the sheet's quantity_unit named; the route, the settlement
    and the schedule method, one each for the batch; the basis the quantities are stated per.
    Then two sets of columns aligned by position, all read-only. Per occurrence, the ticket's
    rows in order: trade_dates[i] the day the deal was struck, and labels[i] its trade_id,
    clearing_house[i] its clearing organization and broker[i] its broker, each tuple None as a
    whole when the field was not given, each a label kept as typed and read for nothing. Per
    component, the contract months the occurrences hold: occurrence[k] the row of the occurrence
    it belongs to, contract[k] the row of the schedule its month is, quantity[k] the signed whole
    count of the specification and fixed_price[k] the price agreed, in the index's quote units.
    Then payment, the terms a financial settlement pays by and the days they give, and None for
    a physical one, which pays on no day."""

    instrument: Instrument
    index: Index
    schedule: FuturesSchedule
    specification: int
    route: Route
    settlement: Settlement
    schedule_method: ScheduleMethod
    quantity_per: QuantityPer
    labels: tuple[str, ...] | None
    clearing_house: tuple[str, ...] | None
    broker: tuple[str, ...] | None
    trade_dates: NDArray[np.datetime64]
    occurrence: NDArray[np.intp]
    contract: NDArray[np.intp]
    quantity: NDArray[np.float64]
    fixed_price: NDArray[np.float64]
    payment: PaymentTerms | None

    def named(self, component: int) -> str:
        """A component's trade named in a message, by its label when the ticket gave one and by
        its row as the sheet counts rows either way: `trade 'NG-001' at row 1`, `trade at row 3`."""
        return _named(self.labels, int(self.occurrence[component]))


def _named(labels: tuple[str, ...] | None, row: int) -> str:
    if labels is None:
        return f"trade at row {row + 1}"
    return f"trade {labels[row]!r} at row {row + 1}"


def resolved_trades(
    instrument: Instrument,
    index: Index,
    specification: int,
    route: Route,
    settlement: Settlement,
    schedule_method: ScheduleMethod,
    quantity_per: QuantityPer,
    labels: tuple[str, ...] | None,
    clearing_house: tuple[str, ...] | None,
    broker: tuple[str, ...] | None,
    trade_dates: NDArray[np.datetime64],
    occurrence: NDArray[np.intp],
    contract: NDArray[np.intp],
    quantity: NDArray[np.float64],
    fixed_price: NDArray[np.float64],
    payment: PaymentTerms | None,
) -> ResolvedTrades:
    """The one way to make ResolvedTrades: the rules of the first future profile, checked once,
    in this order, the first failure being the message; then the columns copied and frozen.

    The index is a futures index, since a future's contract is a row of a futures schedule and
    its final price the settlement on that row's expiry day. The specification is a row of the
    index's specifications, since the lot size and the lot unit are read there: it is the one
    selection, and the quantities count it, whatever the desk's word for it, an exchange lot or
    a bare unit the index defines with a size of one. A penultimate future settles financially:
    it is cash settled against the settle on the business day before its contract's expiry, and
    a physical settlement would say a delivery the contract does not make. The occurrences are
    the ticket's rows: one date each, and one label, clearing house and broker each where those
    are given. The components are aligned, one or more, each belonging to an occurrence, every
    occurrence holding at least one, since a trade with no contract month has no economics; each
    contract is a row of the schedule; each quantity is a whole number, positive, negative or
    zero, the first profile's convention, a signed count of the specification, a zero row kept
    ready for a deal and contributing nothing; each fixed price is a finite
    number, the quantity and the price named by the trade they belong to, as the sheet counts
    its rows. A financial settlement has payment terms, a lag and a calendar per occurrence and
    one payment day per component, and a physical one has none: a physical future pays on no
    day, and giving it terms would invent a payment the contract does not make. The instrument
    is kept as the definition the terms stand under, and read for nothing here.
    """
    schedule = _the_batch(index, specification)
    _the_method(schedule_method, settlement)
    occurrences = _the_occurrences(trade_dates, labels, clearing_house, broker)
    _the_components(
        occurrence, contract, quantity, fixed_price, labels, occurrences, len(schedule.codes)
    )
    pays = _the_payment(settlement, payment, occurrences, occurrence.size)
    return ResolvedTrades(
        instrument,
        index,
        schedule,
        specification,
        route,
        settlement,
        schedule_method,
        quantity_per,
        labels,
        clearing_house,
        broker,
        _frozen_days(trade_dates),
        _frozen_rows(occurrence),
        _frozen_rows(contract),
        _frozen_numbers(quantity),
        _frozen_numbers(fixed_price),
        pays,
    )


def futures_schedule_of(index: Index) -> FuturesSchedule:
    """The schedule of a futures index, typed as the kind rule found it: a future's contract is
    a row of a futures schedule and its final price the settlement on that row's expiry day, so
    an index of another kind is refused, in the resolution of a batch and in the kernel alike."""
    if index.kind is not Kind.FUTURES:
        raise ValueError(
            f"index is {described(index.kind, 'index')}, expected a futures index for a future"
        )
    return cast(FuturesSchedule, index.schedule)  # what the kind just said


def _the_batch(index: Index, specification: int) -> FuturesSchedule:
    """A futures index and a row of its specifications: the index's schedule, typed."""
    schedule = futures_schedule_of(index)
    rows = len(index.specifications.names)
    if not 0 <= specification < rows:
        raise ValueError(
            f"specification is {specification}, "
            f"expected a row of the index's specifications, 0 to {rows - 1}"
        )
    return schedule


def _the_method(schedule_method: ScheduleMethod, settlement: Settlement) -> None:
    """The method and the settlement together: a penultimate future is cash settled against the
    settle on the business day before its contract's expiry, so a physical settlement is refused;
    lastday settles either way."""
    match schedule_method:
        case ScheduleMethod.LASTDAY:
            return
        case ScheduleMethod.PENULTIMATE:
            if settlement is Settlement.PHYSICAL:
                raise ValueError(
                    "settlement_method is 'physical', expected 'financial' with the penultimate "
                    "method; "
                    "a penultimate future is cash settled on the business day before its "
                    "contract's expiry"
                )
        case _:
            assert_never(schedule_method)


def _the_occurrences(
    trade_dates: NDArray[np.datetime64],
    labels: tuple[str, ...] | None,
    clearing_house: tuple[str, ...] | None,
    broker: tuple[str, ...] | None,
) -> int:
    """One or more, a date each and, for each label tuple given, a text each: their count."""
    occurrences = trade_dates.size
    if occurrences == 0:
        raise ValueError("trade_dates has 0 dates, expected at least 1, one per occurrence")
    for name, texts in (("labels", labels), ("clearing_house", clearing_house), ("broker", broker)):
        if texts is not None and len(texts) != occurrences:
            raise ValueError(
                f"{name} has {len(texts)} texts, expected {occurrences}, one per occurrence"
            )
    return occurrences


def _the_components(
    occurrence: NDArray[np.intp],
    contract: NDArray[np.intp],
    quantity: NDArray[np.float64],
    fixed_price: NDArray[np.float64],
    labels: tuple[str, ...] | None,
    occurrences: int,
    schedule_rows: int,
) -> None:
    """Aligned, one or more, each of an occurrence and every occurrence holding one; each
    contract a row of the schedule, each quantity whole, zero included, each price finite, a
    quantity or a price refused naming the trade it belongs to, since a strip's component is no
    row of the sheet."""
    components = occurrence.size
    if components == 0:
        raise ValueError("occurrence has 0 rows, expected at least 1, one per component")
    for name, column in (
        ("contract", contract),
        ("quantity", quantity),
        ("fixed_price", fixed_price),
    ):
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
        raise ValueError(f"{_named(labels, i)} has no component, expected at least one")
    outside = (contract < 0) | (contract >= schedule_rows)
    if outside.any():
        k = int(outside.argmax())
        raise ValueError(
            f"contract row {k + 1} is {contract[k]}, "
            f"expected a row of the schedule, 0 to {schedule_rows - 1}"
        )
    whole_quantities(quantity, lambda k: f"quantity of {_named(labels, int(occurrence[k]))}")
    finite_prices(fixed_price, lambda k: f"fixed_price of {_named(labels, int(occurrence[k]))}")


def whole_quantities(quantity: NDArray[np.float64], where: Callable[[int], str]) -> None:
    """Each quantity a whole number, the first profile's convention, a signed count of the
    specification selected, zero included, since a row kept ready for a deal holds a zero and
    contributes nothing: the first that is not whole, a fraction, a NaN or an infinity, is
    refused, named by the caller's words for its position, the trade it belongs to in a batch
    and the field in a template."""
    fractional = ~np.isfinite(quantity) | (quantity != np.round(quantity))
    if fractional.any():
        k = int(fractional.argmax())
        raise ValueError(f"{where(k)} is {float(quantity[k])!r}, expected a whole number")


def finite_prices(prices: NDArray[np.float64], where: Callable[[int], str]) -> None:
    """Each price a finite number, the first that is not refused in the caller's words."""
    unfinished = ~np.isfinite(prices)
    if unfinished.any():
        k = int(unfinished.argmax())
        raise ValueError(f"{where(k)} is {float(prices[k])!r}, expected a finite price")


def _the_payment(
    settlement: Settlement, payment: PaymentTerms | None, occurrences: int, components: int
) -> PaymentTerms | None:
    """For a financial settlement the terms, a lag and a calendar per occurrence and a day per
    component, the arrays frozen; for a physical one none."""
    match settlement:
        case Settlement.FINANCIAL:
            if payment is None:
                raise ValueError(
                    "payment is missing, expected a lag and a calendar per occurrence and one "
                    "date per component with a financial settlement"
                )
            for name, count in (
                ("lag_days", payment.lag_days.size),
                ("calendar", len(payment.calendar)),
            ):
                if count != occurrences:
                    raise ValueError(
                        f"payment {name} has {count}, expected {occurrences}, one per occurrence"
                    )
            if payment.date.size != components:
                raise ValueError(
                    f"payment date has {payment.date.size} dates, expected {components}, "
                    "one per component"
                )
            lag_days = np.array(payment.lag_days, dtype=np.int64)
            lag_days.setflags(write=False)
            return PaymentTerms(lag_days, payment.calendar, _frozen_days(payment.date))
        case Settlement.PHYSICAL:
            if payment is not None:
                raise ValueError(
                    f"payment has {payment.date.size} dates, "
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
