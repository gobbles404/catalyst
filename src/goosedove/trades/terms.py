"""The resolved terms of a batch of trades: which deals were struck, under which definitions, as
the resolution child of _CreateTrades establishes them from a template and a ticket, and as
tests supply them in Python. One instrument and one index for the batch, one route and one
settlement; then the occurrences, the ticket's rows, each with its date, the specification of
the index its quantity counts, its schedule method and its quantity basis, so that one batch
mixes units, methods and bases row by row, its clearing house, its counterparty and its broker
where given and the marketing reserve it booked; then the components, one per contract month
an occurrence holds, each with its occurrence, its contract, its signed quantity as entered,
the days it covers within its
contract's month, the quantity its occurrence's basis gives it and its fixed price; and for a
financial settlement the payment terms, the lag and the calendar each occurrence pays by and the
day each component pays. docs/library/trades/kernel.md is the page."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.contract_codes import month_and_year
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index, ReportingLot
from goosedove.index_definitions.kind import Kind, described
from goosedove.instruments.definitions import Instrument
from goosedove.trades.schedule_methods import (
    METHODS,
    ScheduleMethod,
    permits_physical_settlement,
    supported_on_iferc,
)


class Route(Enum):
    """How the trade is arranged for clearing: the result's labels follow it."""

    CLEARED = "cleared"
    BILATERAL = "bilateral"


class Settlement(Enum):
    """How the contract settles at the end: delivered, or paid in money on a day."""

    PHYSICAL = "physical"
    FINANCIAL = "financial"


class QuantityPer(Enum):
    """What the entered quantity is per. month: the quantity stands in every contract month the
    trade covers, a partial month's as much as a whole one's, never prorated. calday: the
    quantity is per calendar day, weekends and holidays included, and a month's quantity is the
    entered quantity times the days it covers, 3,100 for 100 a day over December. The basis says
    nothing of the pricing days, which the schedule method chooses; both are built."""

    MONTH = "month"
    CALDAY = "calday"


# The members of the basis choice in the definition's order, and their names as the sheet
# spells them: a selection holds each occurrence's choice as its position here, so that the
# kernel gathers and compares positions and never texts, and a reader turns a position back
# into its name. The schedule methods' members and names are schedule_methods.py's, the same
# way.
BASES: Final = tuple(QuantityPer)
BASIS_NAMES: Final = np.array([member.value for member in BASES], dtype=object)
BASIS_NAMES.setflags(write=False)


def one_choice[E: Enum](members: tuple[E, ...], choice: E, occurrences: int) -> NDArray[np.intp]:
    """One choice for every occurrence, as the kernel holds a selection: the member's position
    among the members, repeated, for a batch whose rows all chose alike."""
    return np.full(occurrences, members.index(choice), dtype=np.intp)


@dataclass(frozen=True, slots=True)
class PaymentTerms:
    """How a financial settlement pays, kept with the days it gives so that a batch explains its
    own payment days. Per occurrence: lag[i], the payment rule as the ticket or the template wrote
    it, `+2bd` or since #181 a chain such as `+3em+25cd-1bd+1bd`, its instructions read once at
    creation and applied then, and calendar[i], the holiday calendar its business days are counted
    on, the object the ticket's handle stood for, held by reference. Per component: date[k], the
    day it pays, its occurrence's rule applied instruction by instruction to its anchor, its
    contract's expiry under lastday and the business day before under penultimate, on its
    occurrence's calendar."""

    lag: tuple[str, ...]
    calendar: tuple[HolidayCalendar, ...]
    date: NDArray[np.datetime64]


@dataclass(frozen=True, slots=True)
class ResolvedTrades:
    """The instrument, the definition the terms were resolved under; the index, by reference, its
    futures schedule, the same object the index holds, typed as the kind rule found it, and its
    reporting lot, the specification the batch's delta is counted in lots of, the one the index
    was made with; the route and the settlement, one each for the batch. Then two sets of columns
    aligned by position, all read-only. Per occurrence, the ticket's rows in order:
    specification[i] the row of the index's specifications its quantity counts, the desk's word
    for a quantity of the index that the row's quantity_unit named; schedule_method[i] its method
    and quantity_per[i] the basis its quantity is stated per, each the position of the member
    among METHODS and BASES, so that one batch mixes units, methods and bases row by row;
    trade_dates[i] the day the deal was struck, trade_ids[i] its trade_id, the source system's
    whole number of at most 15 digits held as an int64 since #168, clearing_house[i] its clearing
    organization, counterparty[i] since #175 the counterparty it faces and broker[i] its broker,
    the IDs an array and the three labels tuples, each None as a whole when the field was not
    given, each kept as given and read for nothing but a message's words and, since #188, the
    broker's text for brokered[i], whether the row names a broker and so charges brokerage:
    False for every row when the field was not given and where the row's text is none in any
    case, the desk's word for a screen trade, reserve-fee-applicability.md; marketing_reserve[i]
    since #175 the marketing cost the row booked once, a finite amount of zero or more in the
    settlement currency, None as a whole when neither the template nor the ticket supplied it,
    read by the reserves alone. Per
    component, the contract months the occurrences hold: occurrence[k] the row of the occurrence
    it belongs to, contract[k] the row of the schedule its month is, quantity[k] the signed whole
    count of the specification as entered, per the basis, start_date[k] and end_date[k] the first
    and the last day the component covers, within its contract's calendar month, the whole month
    from a contract code and a booked period's share of it from explicit dates, covered_days[k]
    the calendar days between them inclusive, weekends and holidays included, derived here,
    component_quantity[k] the count the component holds, the entered quantity under month and
    the entered quantity times the covered days under calday, formed once here, the one quantity
    the encoding converts and nothing later scales again, and fixed_price[k] the price agreed, in
    the index's quote units. Then payment, the terms a financial settlement pays by and the days
    they give, and None for a physical one, which pays on no day. Then schedule_month[i], since
    #186, the calendar month of every row of the schedule as numpy counts months from 1970, read
    once by the resolution against the ticket's codes and kept for the encoding, which gathers it
    by the pricing references for the delta's month and year buckets."""

    instrument: Instrument
    index: Index
    schedule: FuturesSchedule | IfercSchedule
    reporting_lot: ReportingLot
    specification: NDArray[np.intp]
    route: Route
    settlement: Settlement
    schedule_method: NDArray[np.intp]
    quantity_per: NDArray[np.intp]
    trade_ids: NDArray[np.int64] | None
    clearing_house: tuple[str, ...] | None
    counterparty: tuple[str, ...] | None
    broker: tuple[str, ...] | None
    brokered: NDArray[np.bool_]
    trade_dates: NDArray[np.datetime64]
    occurrence: NDArray[np.intp]
    contract: NDArray[np.intp]
    quantity: NDArray[np.float64]
    start_date: NDArray[np.datetime64]
    end_date: NDArray[np.datetime64]
    covered_days: NDArray[np.int64]
    component_quantity: NDArray[np.float64]
    fixed_price: NDArray[np.float64]
    marketing_reserve: NDArray[np.float64] | None
    payment: PaymentTerms | None
    schedule_month: NDArray[np.int64]

    def named(self, component: int) -> str:
        """A component's trade named in a message, by its ID when the ticket gave one and by its
        row as the sheet counts rows either way: `trade 1001 at row 1`, `trade at row 3`."""
        return named_trade(self.trade_ids, int(self.occurrence[component]))


def named_trade(trade_ids: NDArray[np.int64] | None, row: int) -> str:
    """A trade named in a message, by its ID when the ticket gave one, the whole number without
    quotes since #168, and by its row as the sheet counts rows either way, `trade 1001 at row 1`,
    `trade at row 3`: the words every refusal of a row's own fact uses, in the kernel and in the
    observations alike."""
    if trade_ids is None:
        return f"trade at row {row + 1}"
    return f"trade {int(trade_ids[row])} at row {row + 1}"


def schedule_months(schedule: FuturesSchedule | IfercSchedule) -> NDArray[np.int64]:
    """The month of every code of the schedule, as numpy counts months, one read per code: a
    code that is no contract code is refused by row, and so are two rows for one month, since a
    month resolved to two rows would name no contract. The resolution reads them once,
    resolves the ticket's periods against them and hands them to the terms, which keep them for
    the encoding's contract-month axes since #186."""
    codes = schedule.codes
    months = np.empty(len(codes), dtype=np.int64)
    for i, code in enumerate(codes):
        try:
            month, year = month_and_year(code)
        except ValueError:
            raise ValueError(
                f"index schedule row {i + 1} is {code!r}, expected a contract code, "
                "a month letter and a two-digit year such as F26"
            ) from None
        months[i] = (year - 1970) * 12 + month - 1
    order = np.argsort(months, kind="stable")
    by_month = months[order]
    same = np.flatnonzero(by_month[1:] == by_month[:-1])
    if same.size:
        a, b = int(order[same[0]]), int(order[same[0] + 1])
        raise ValueError(
            f"index schedule rows {a + 1} and {b + 1} are {codes[a]!r} and {codes[b]!r}, "
            f"both {month_label(by_month[same[0]])}, expected one contract per month"
        )
    return months


def month_label(count: object) -> str:
    """A month as numpy counts them, written as the sheet reads one: 2027-04."""
    return str(np.datetime64(int(cast(Any, count)), "M"))


def resolved_trades(
    instrument: Instrument,
    index: Index,
    specification: NDArray[np.intp],
    route: Route,
    settlement: Settlement,
    schedule_method: NDArray[np.intp],
    quantity_per: NDArray[np.intp],
    trade_ids: NDArray[np.int64] | None,
    clearing_house: tuple[str, ...] | None,
    broker: tuple[str, ...] | None,
    trade_dates: NDArray[np.datetime64],
    occurrence: NDArray[np.intp],
    contract: NDArray[np.intp],
    quantity: NDArray[np.float64],
    start_date: NDArray[np.datetime64],
    end_date: NDArray[np.datetime64],
    fixed_price: NDArray[np.float64],
    payment: PaymentTerms | None,
    *,
    schedule_month: NDArray[np.int64] | None = None,
    counterparty: tuple[str, ...] | None = None,
    marketing_reserve: NDArray[np.float64] | None = None,
) -> ResolvedTrades:
    """The one way to make ResolvedTrades: the rules of the first fixed_float profile, checked once,
    in this order, the first failure being the message; then the columns copied and frozen.

    The index is a futures or, since #167, an IFERC index, since a fixed_float's contract is a row
    of a futures schedule, its final price the settlement on that row's expiry day, or a row of an
    IFERC schedule, its final price the month's index on that row's publication day, the traded
    basis; a Gas Daily index is refused by name. An IFERC index takes a financial settlement and
    the lastday method alone, the first row of another method named, since an IFERC month has
    one index, published once. The index was made with a reporting
    lot, since the batch's delta is a count of that lot and a batch without one could not report
    its risk. The occurrences are the ticket's
    rows: one date each, and one trade ID, a whole number of at most 15 digits the caller read
    by whole_trade_ids since #168, clearing house and broker each where those are given;
    one specification, method and basis each, the specification a row of the index's
    specifications, since the lot size and the lot unit are read there, its quantities counting
    it, whatever the desk's word for it, an exchange lot or a bare unit the index defines with a
    size of one, the method and the basis positions among their members, the first row out of
    range refused. A penultimate, last3day or asian row settles financially, each being cash
    settled against settles on or before its contract's expiry, and a physical settlement would
    say a delivery the contract does not make: a physical batch takes lastday rows alone, the
    first other row refused by its method and named by its row. The components are aligned, one
    or more, each belonging to an occurrence, every
    occurrence holding at least one, since a trade with no contract month has no economics; each
    contract is a row of the schedule; each component covers the days from its start date to its
    end date, the end on or after the start and both in one calendar month, since a component is
    one contract month's and a quantity per day over no day states nothing, the days counted
    here; each quantity is a whole number, positive, negative or zero, the first profile's
    convention, a signed count of the specification, a zero row kept ready for a deal and
    contributing nothing; each fixed price is a finite number, the quantity, the days and the
    price named by the trade they belong to, as the sheet counts its rows. Each component's
    quantity is then formed once by its occurrence's basis, the entered quantity under month and
    the entered quantity times its covered days under calday, finite, for the encoding to convert
    and nothing later to scale again. A financial settlement has payment terms, a lag and a
    calendar per occurrence and one payment day per component, and a physical one has none: a
    physical fixed_float
    pays on no
    day, and giving it terms would invent a payment the contract does not make. The instrument
    is kept as the definition the terms stand under, and read for nothing here. The schedule's
    months, since #186, are the resolution's reading of every row's code handed over, or read here
    once by schedule_months when a Python caller gives none; kept frozen for the encoding's
    contract-month axes and read for nothing here. The brokered rows, since #188, are read here
    once from the broker texts, none in any case meaning a screen trade, and kept frozen for the
    reserves, which charge brokerage on their components alone.
    """
    schedule = trade_schedule_of(index)
    lot = reporting_lot_of(index)
    occurrences = _the_occurrences(
        trade_dates, trade_ids, clearing_house, counterparty, broker, marketing_reserve
    )
    _the_selections(index, specification, schedule_method, quantity_per, occurrences)
    _the_method(schedule_method, settlement, trade_ids, index.kind)
    _the_components(
        occurrence,
        contract,
        quantity,
        start_date,
        end_date,
        fixed_price,
        trade_ids,
        occurrences,
        len(schedule.codes),
    )
    pays = _the_payment(settlement, payment, occurrences, occurrence.size)
    quantities = _frozen_numbers(quantity)
    starts, ends = _frozen_days(start_date), _frozen_days(end_date)
    days = (ends - starts).astype(np.int64) + 1  # made here and owned here: frozen below
    days.setflags(write=False)
    # The schedule's months, the resolution's reading handed over or read here once; owned here.
    months = (
        schedule_months(schedule)
        if schedule_month is None
        else np.array(schedule_month, dtype=np.int64)
    )
    months.setflags(write=False)
    brokered = _the_brokered(broker, occurrences)
    return ResolvedTrades(
        instrument,
        index,
        schedule,
        lot,
        _frozen_rows(specification),
        route,
        settlement,
        _frozen_rows(schedule_method),
        _frozen_rows(quantity_per),
        None if trade_ids is None else _frozen_ids(trade_ids),
        clearing_house,
        counterparty,
        broker,
        brokered,
        _frozen_days(trade_dates),
        _frozen_rows(occurrence),
        _frozen_rows(contract),
        quantities,
        starts,
        ends,
        days,
        _the_component_quantity(quantity_per, quantities, days, trade_ids, occurrence),
        _frozen_numbers(fixed_price),
        None if marketing_reserve is None else _frozen_numbers(marketing_reserve),
        pays,
        months,
    )


def trade_schedule_of(index: Index) -> FuturesSchedule | IfercSchedule:
    """The schedule of an index a fixed_float is booked on, typed as the kind rule found it: a
    futures schedule, whose rows' expiry days settle the contracts, or since #167 an IFERC
    schedule, whose rows' publication days print each month's index, the traded basis; a Gas
    Daily index is refused, in the resolution of a batch and in the kernel alike. The steps
    that read a day off the schedule dispatch on which it is."""
    match index.kind:
        case Kind.FUTURES:
            return cast(FuturesSchedule, index.schedule)  # what the kind just said
        case Kind.IFERC:
            return cast(IfercSchedule, index.schedule)
        case Kind.GAS_DAILY:
            raise ValueError(
                f"index is {described(index.kind, 'index')}, expected a futures or an IFERC "
                "index for a fixed_float"
            )
        case _:
            assert_never(index.kind)


def reporting_lot_of(index: Index) -> ReportingLot:
    """The specification the index reports delta in lots of, named when the index was made: a
    batch's delta is a count of it, so an index made without one is refused, in the resolution
    of a batch and in the kernel alike, before any row is read; a market needs none, and an
    index that only builds markets is made without one."""
    if index.reporting_lot is None:
        raise ValueError(
            f"index {index.name!r} has no reporting_lot, expected one of its specifications named "
            "when the index was made; a batch's delta is reported in lots of it"
        )
    return index.reporting_lot


def _the_selections(
    index: Index,
    specification: NDArray[np.intp],
    schedule_method: NDArray[np.intp],
    quantity_per: NDArray[np.intp],
    occurrences: int,
) -> None:
    """Each occurrence's three choices, one per occurrence: its specification a row of the index's
    specifications, its method a position among METHODS and its basis one among BASES, the first
    out of range refused by its row."""
    choices = (
        (
            "specification",
            specification,
            len(index.specifications.names),
            "a row of the index's specifications",
        ),
        ("schedule_method", schedule_method, len(METHODS), "a method, its position among METHODS"),
        ("quantity_per", quantity_per, len(BASES), "a basis, its position among BASES"),
    )
    for name, column, count, words in choices:
        if column.size != occurrences:
            raise ValueError(
                f"{name} has {column.size} rows, expected {occurrences}, one per occurrence"
            )
        outside = (column < 0) | (column >= count)
        if outside.any():
            i = int(outside.argmax())
            raise ValueError(
                f"{name} row {i + 1} is {column[i]}, expected {words}, 0 to {count - 1}"
            )


def _the_method(
    schedule_method: NDArray[np.intp],
    settlement: Settlement,
    trade_ids: NDArray[np.int64] | None,
    kind: Kind,
) -> None:
    """Each occurrence's method with the batch's settlement and the index's kind. On an IFERC
    index, since #167, the settlement is financial, an IFERC basis future being cash settled on
    its month's published index, and every row's method is lastday, the one observation of that
    index, the first row of another method refused by its method and its row. On a futures
    index: a penultimate future is cash settled
    against the settle on the business day before its contract's expiry, a last3day future
    against the average of its last three pricing days and an asian future against the average
    of its month's pricing days, so a physical settlement is refused with the first row that
    chose any of the three, named by its label and its row; lastday settles either way, and a
    physical batch is lastday rows alone."""
    if kind is Kind.IFERC:
        if settlement is Settlement.PHYSICAL:
            raise ValueError(
                "settlement_method is 'physical', expected 'financial' on an IFERC index; an "
                "IFERC basis future is cash settled on its month's published index"
            )
        supported = supported_on_iferc(schedule_method)
        if not supported.all():
            i = int((~supported).argmax())
            raise ValueError(
                f"schedule_method of {named_trade(trade_ids, i)} is "
                f"{METHODS[int(schedule_method[i])].value!r}, expected 'lastday' on an IFERC "
                "index; an IFERC month has one index, published once"
            )
        return
    match settlement:
        case Settlement.FINANCIAL:
            return
        case Settlement.PHYSICAL:
            permitted = permits_physical_settlement(schedule_method)
            if permitted.all():
                return
            i = int((~permitted).argmax())
            method = METHODS[int(schedule_method[i])]
            trade = named_trade(trade_ids, i)
            match method:
                case ScheduleMethod.LASTDAY:
                    return
                case ScheduleMethod.ASIAN:
                    raise ValueError(
                        "settlement_method is 'physical', expected 'financial' with the asian "
                        f"method of {trade}; an asian future is cash settled on the average of "
                        "its month's pricing days"
                    )
                case ScheduleMethod.LAST3DAY:
                    raise ValueError(
                        "settlement_method is 'physical', expected 'financial' with the last3day "
                        f"method of {trade}; a last3day future is cash settled on the average of "
                        "its last three pricing days"
                    )
                case ScheduleMethod.PENULTIMATE:
                    raise ValueError(
                        "settlement_method is 'physical', expected 'financial' with the "
                        f"penultimate method of {trade}; a penultimate future is cash settled on "
                        "the business day before its contract's expiry"
                    )
                case _:
                    assert_never(method)
        case _:
            assert_never(settlement)


UNBROKERED = "none"  # a broker text, in any case, naming no broker: a screen trade, since #188


def _the_brokered(broker: tuple[str, ...] | None, occurrences: int) -> NDArray[np.bool_]:
    """Which occurrences name a broker, since #188: none of them when the field was not given, and
    each whose text is other than none, in any case, when it was; the texts themselves stand as
    given. Frozen."""
    if broker is None:
        brokered = np.zeros(occurrences, dtype=np.bool_)
    else:
        brokered = np.array([text.lower() != UNBROKERED for text in broker], dtype=np.bool_)
    brokered.setflags(write=False)
    return brokered


def _the_occurrences(
    trade_dates: NDArray[np.datetime64],
    trade_ids: NDArray[np.int64] | None,
    clearing_house: tuple[str, ...] | None,
    counterparty: tuple[str, ...] | None,
    broker: tuple[str, ...] | None,
    marketing_reserve: NDArray[np.float64] | None,
) -> int:
    """One or more, a date each and, for the IDs, each label tuple and the marketing reserves
    given, one each: their count."""
    occurrences = trade_dates.size
    if occurrences == 0:
        raise ValueError("trade_dates has 0 dates, expected at least 1, one per occurrence")
    if trade_ids is not None and trade_ids.size != occurrences:
        raise ValueError(
            f"trade_ids has {trade_ids.size} ids, expected {occurrences}, one per occurrence"
        )
    for name, texts in (
        ("clearing_house", clearing_house),
        ("counterparty", counterparty),
        ("broker", broker),
    ):
        if texts is not None and len(texts) != occurrences:
            raise ValueError(
                f"{name} has {len(texts)} texts, expected {occurrences}, one per occurrence"
            )
    if marketing_reserve is not None and marketing_reserve.size != occurrences:
        raise ValueError(
            f"marketing_reserve has {marketing_reserve.size} amounts, expected {occurrences}, "
            "one per occurrence"
        )
    return occurrences


def _the_components(
    occurrence: NDArray[np.intp],
    contract: NDArray[np.intp],
    quantity: NDArray[np.float64],
    start_date: NDArray[np.datetime64],
    end_date: NDArray[np.datetime64],
    fixed_price: NDArray[np.float64],
    trade_ids: NDArray[np.int64] | None,
    occurrences: int,
    schedule_rows: int,
) -> None:
    """Aligned, one or more, each of an occurrence and every occurrence holding one; each
    contract a row of the schedule, each component's end on or after its start and both in one
    calendar month, each quantity whole, zero included, each price finite, the days, a quantity
    or a price refused naming the trade it belongs to, since a strip's component is no row of
    the sheet."""
    components = occurrence.size
    if components == 0:
        raise ValueError("occurrence has 0 rows, expected at least 1, one per component")
    for name, column in (
        ("contract", contract),
        ("quantity", quantity),
        ("start_date", start_date),
        ("end_date", end_date),
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
        raise ValueError(f"{named_trade(trade_ids, i)} has no component, expected at least one")
    outside = (contract < 0) | (contract >= schedule_rows)
    if outside.any():
        k = int(outside.argmax())
        raise ValueError(
            f"contract row {k + 1} is {contract[k]}, "
            f"expected a row of the schedule, 0 to {schedule_rows - 1}"
        )
    backwards = end_date < start_date
    if backwards.any():
        k = int(backwards.argmax())
        raise ValueError(
            f"end_date of {named_trade(trade_ids, int(occurrence[k]))} is {end_date[k]}, "
            f"expected a day on or after its start_date, {start_date[k]}"
        )
    two_months = start_date.astype("datetime64[M]") != end_date.astype("datetime64[M]")
    if two_months.any():
        k = int(two_months.argmax())
        raise ValueError(
            f"{named_trade(trade_ids, int(occurrence[k]))} covers {start_date[k]} to "
            f"{end_date[k]}, expected one calendar month per component"
        )
    whole_quantities(
        quantity, lambda k: f"quantity of {named_trade(trade_ids, int(occurrence[k]))}"
    )
    finite_prices(
        fixed_price, lambda k: f"fixed_price of {named_trade(trade_ids, int(occurrence[k]))}"
    )


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


TRADE_ID_DIGITS = 15  # the source system's and Excel's: a cell carries fifteen digits exactly
TRADE_ID_LIMIT = 10**TRADE_ID_DIGITS - 1


def whole_trade_ids(values: NDArray[np.float64], where: Callable[[int], str]) -> NDArray[np.int64]:
    """Each trade ID a whole number of at most 15 digits, the source system's deal numbers as the
    sheet carries them exactly, since #168: finite, whole and within -999,999,999,999,999 to
    999,999,999,999,999, zero and signed values included, since an identifier is not a quantity;
    the first that is not is refused in the caller's words for its position, the row in a
    ticket and the field in a template, a whole value shown without a fraction. Then the values
    converted once to int64 and frozen, the one integer form every later reader takes; nothing
    rounds, truncates or invents an ID."""
    bad = ~np.isfinite(values) | (values != np.round(values)) | (np.abs(values) > TRADE_ID_LIMIT)
    if bad.any():
        k = int(bad.argmax())
        value = float(values[k])
        shown = str(int(value)) if np.isfinite(value) and value == round(value) else repr(value)
        raise ValueError(
            f"{where(k)} is {shown}, expected a whole number of at most {TRADE_ID_DIGITS} digits"
        )
    ids = values.astype(np.int64)
    ids.setflags(write=False)
    return ids


def finite_prices(prices: NDArray[np.float64], where: Callable[[int], str]) -> None:
    """Each price a finite number, the first that is not refused in the caller's words."""
    unfinished = ~np.isfinite(prices)
    if unfinished.any():
        k = int(unfinished.argmax())
        raise ValueError(f"{where(k)} is {float(prices[k])!r}, expected a finite price")


def marketing_reserves(
    amounts: NDArray[np.float64], where: Callable[[int], str]
) -> NDArray[np.float64]:
    """Each marketing reserve a finite amount of zero or more, since #175, the first that is not
    refused in the caller's words, a negative amount, NaN and the infinities alike; the amounts
    handed back for the record, the one rule a template's value and a ticket's column share."""
    bad = ~(np.isfinite(amounts) & (amounts >= 0.0))
    if bad.any():
        k = int(bad.argmax())
        raise ValueError(
            f"{where(k)} is {float(amounts[k])!r}, expected a finite amount of zero or more"
        )
    return amounts


def _the_component_quantity(
    quantity_per: NDArray[np.intp],
    quantity: NDArray[np.float64],
    covered_days: NDArray[np.int64],
    trade_ids: NDArray[np.int64] | None,
    occurrence: NDArray[np.intp],
) -> NDArray[np.float64]:
    """Each component's quantity by its occurrence's basis, formed once here for the encoding to
    convert and nothing later to scale again. Under month the entered quantity itself, since the
    entered quantity stands in every month the trade covers, the frozen column shared when no
    row chose calday; under calday the entered quantity times the component's covered days, one
    multiplication and one choice over the components, frozen, and finite: the product itself is
    looked at, since a bound on the entered quantity is a rounded quotient a quantity at it can
    pass and still overflow, the overflow let happen here quietly and the first infinite product
    refused by its trade, since the whole-number rule admits entered quantities the product
    outruns; a month row's unused product is never looked at, its entered quantity standing."""
    calday = quantity_per[occurrence] == BASES.index(QuantityPer.CALDAY)
    if not calday.any():
        return quantity
    with np.errstate(over="ignore"):  # the overflow is this rule's to catch, below
        expanded = np.where(calday, quantity * covered_days, quantity)
    overflow = ~np.isfinite(expanded)
    if overflow.any():
        k = int(overflow.argmax())
        raise ValueError(
            f"quantity of {named_trade(trade_ids, int(occurrence[k]))} is {float(quantity[k])!r} "
            f"over {int(covered_days[k])} days, expected a finite quantity"
        )
    expanded.setflags(write=False)  # made here and owned here: no copy to freeze
    return expanded


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
                ("lag", len(payment.lag)),
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
            return PaymentTerms(tuple(payment.lag), payment.calendar, _frozen_days(payment.date))
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


def _frozen_ids(column: NDArray[np.int64]) -> NDArray[np.int64]:
    ids = np.array(column, dtype=np.int64)
    ids.setflags(write=False)
    return ids


def _frozen_numbers(column: NDArray[np.float64]) -> NDArray[np.float64]:
    numbers = np.array(column, dtype=np.float64)
    numbers.setflags(write=False)
    return numbers


def _frozen_days(column: NDArray[np.datetime64]) -> NDArray[np.datetime64]:
    days = np.array(column, dtype="datetime64[D]")
    days.setflags(write=False)
    return days
