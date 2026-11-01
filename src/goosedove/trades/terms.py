"""The resolved terms of a batch of trades: which deals were struck, under which definitions, as
the resolution child of _CreateTrades establishes them from a template and a ticket, and as
tests supply them in Python. One instrument for the batch, one route and one settlement, and
its legs, one index each, one or since two-index-fixed-float.md two; then the occurrences,
the ticket's rows, each with its date, the specification of
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
from typing import Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.index_definitions.contract_codes import schedule_months
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index, ReportingLot
from goosedove.index_definitions.kind import Kind, described
from goosedove.instruments.definitions import Instrument
from goosedove.instruments.fields import DatesOrTexts
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
    own payment days. Per occurrence: entered, what the ticket or the template wrote for the
    row's payment_day since payment-day-date-or-rule.md, a date or a rule text each, `+2bd` or
    since #181 a chain such as `+3em+25cd-1bd+1bd`, a rule's instructions read once at creation
    and applied then; and calendar[i], the holiday calendar a rule's business days are counted
    on, the object the ticket's handle stood for, held by reference, read for nothing by a row
    that entered a date. Per component: date[k], the day it pays, its row's date as entered or
    its row's rule applied instruction by instruction to its anchor, its contract's expiry under
    lastday and the business day before under penultimate, on its occurrence's calendar."""

    entered: DatesOrTexts
    calendar: tuple[HolidayCalendar, ...]
    date: NDArray[np.datetime64]


@dataclass(frozen=True, slots=True)
class LegInputs:
    """What a second leg is made from, since two-index-fixed-float.md: the second index's side of
    the terms as the resolution hands it to resolved_trades, the first leg's being the builder's
    positional arguments as they were with one index. The index; specification[i], the row of
    its specifications each occurrence's quantity_unit names on this index; schedule_method[i],
    each occurrence's second_schedule_method as a position among METHODS; contract[k], the row of
    this index's schedule each component's month is; fixed_price[k], each component's
    second_fixed_price; and schedule_month, this schedule's months as the resolution read them,
    or None to read them in the builder."""

    index: Index
    specification: NDArray[np.intp]
    schedule_method: NDArray[np.intp]
    contract: NDArray[np.intp]
    fixed_price: NDArray[np.float64]
    schedule_month: NDArray[np.int64] | None = None


@dataclass(frozen=True, slots=True)
class LegTerms:
    """One leg's side of a batch's terms, since two-index-fixed-float.md: the facts that belong to
    the index the leg prices on, kept apart from the trade's own so that a second leg is another
    of these and nothing else. The index, by reference, its schedule, the same object the index
    holds, typed as the kind rule found it, and its reporting lot, the specification the leg's
    delta is counted in lots of. Per occurrence, aligned with the trade's rows: specification[i]
    the row of the index's specifications the row's quantity counts, the desk's word for a
    quantity of the index that its quantity_unit named, and schedule_method[i] the method, the
    position of the member among METHODS. Per component, aligned with the trade's components:
    contract[k] the row of the schedule the component's month is, and fixed_price[k] the price
    agreed for the leg, in the index's quote units. Then schedule_month[i], since #186, the
    calendar month of every row of the schedule as numpy counts months from 1970, read once by
    the resolution against the ticket's codes and kept for the encoding's contract-month axes.
    Every array read-only."""

    index: Index
    schedule: FuturesSchedule | IfercSchedule
    reporting_lot: ReportingLot
    specification: NDArray[np.intp]
    schedule_method: NDArray[np.intp]
    contract: NDArray[np.intp]
    fixed_price: NDArray[np.float64]
    schedule_month: NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class ResolvedTrades:
    """The trade's own facts, and its legs. The instrument, the definition the terms were resolved
    under; the route and the settlement, one each for the batch. Then two sets of columns
    aligned by position, all read-only. Per occurrence, the ticket's rows in order:
    quantity_per[i] the basis its quantity is stated per, the position of the member among
    BASES; trade_dates[i] the day the deal was struck, trade_ids[i] its trade_id, the source
    system's whole number of at most 15 digits held as an int64 since #168, clearing_house[i] its
    clearing organization, counterparty[i] since #175 the counterparty it faces and broker[i] its
    broker, the IDs an array and the three labels tuples, each None as a whole when the field was
    not given, each kept as given and read for nothing but a message's words and, since #188, the
    broker's text for brokered[i], whether the row names a broker and so charges brokerage:
    False for every row when the field was not given and where the row's text is none in any
    case, the desk's word for a screen trade, reserve-fee-applicability.md; marketing_reserve[i]
    since #175 the marketing cost the row booked once, a finite amount of zero or more in the
    settlement currency, None as a whole when neither the template nor the ticket supplied it,
    read by the reserves alone; discount_curve_key[i], since named-curves-slice-3.md, the
    exact name of the curve the row's payments discount on, one per occurrence for a bilateral
    batch and None as a whole for a cleared one, read by the encoding for the groups and by the
    evaluation to select the curve, never a curve itself. Per component, the contract months the
    occurrences hold: occurrence[k] the row of the occurrence it belongs to, quantity[k] the
    signed whole count of the specification as entered, per the basis, start_date[k] and
    end_date[k] the first and the last day the component covers, within its contract's calendar
    month, the whole month from a contract code and a booked period's share of it from explicit
    dates, period_start[k] and period_end[k] since onetime-averaging.md the first and the last
    day of the component's calculation period, the calendar month its days lie in, derived here
    and the identity the encoding keys its payment groups by, the days clipped within it
    deciding its observations and its quantity, covered_days[k] the calendar days between the
    two dates inclusive, weekends and holidays
    included, derived here, and component_quantity[k] the count the component holds, the entered
    quantity under month and the entered quantity times the covered days under calday, formed
    once here, the one quantity the encoding converts and nothing later scales again. Then
    payment, the terms a financial settlement pays by and the days they give, one day per
    component shared by every leg, and None for a physical one, which pays on no day.

    Then legs, since two-index-fixed-float.md: the LegTerms of each leg in leg order, one today,
    each the index a leg prices on with its schedule, reporting lot, specification rows, methods,
    contract rows and fixed prices, so that what an index owns is held once per leg and what
    the trade owns is held once. The first leg is the batch's for what a batch has one of: the
    fee source of its reserves and the name its handle carries. Then combined_fixed_price[k],
    since two-index-fixed-float.md's third pull request: the trade's fixed price per
    component, the legs' entered prices summed, derived and never entered, formed once and
    checked finite where it is made, a one-index batch's its leg's own array by reference,
    read by the readback and by nothing that prices."""

    instrument: Instrument
    route: Route
    settlement: Settlement
    quantity_per: NDArray[np.intp]
    trade_ids: NDArray[np.int64] | None
    clearing_house: tuple[str, ...] | None
    counterparty: tuple[str, ...] | None
    discount_curve_key: tuple[str, ...] | None
    broker: tuple[str, ...] | None
    brokered: NDArray[np.bool_]
    trade_dates: NDArray[np.datetime64]
    occurrence: NDArray[np.intp]
    quantity: NDArray[np.float64]
    start_date: NDArray[np.datetime64]
    end_date: NDArray[np.datetime64]
    period_start: NDArray[np.datetime64]
    period_end: NDArray[np.datetime64]
    covered_days: NDArray[np.int64]
    component_quantity: NDArray[np.float64]
    marketing_reserve: NDArray[np.float64] | None
    payment: PaymentTerms | None
    legs: tuple[LegTerms, ...]
    combined_fixed_price: NDArray[np.float64]

    def named(self, component: int) -> str:
        """A component's trade named in a message, by its ID when the ticket gave one and by its
        row as the sheet counts rows either way: `trade 1001 at row 1`, `trade at row 3`."""
        return named_trade(self.trade_ids, int(self.occurrence[component]))

    @property
    def descriptor(self) -> str:
        """The words a handle of the batch carries where a single index's name stands: the legs'
        index names joined by `+` in leg order, one index's name alone today, a readable
        descriptor and nothing more, read by nothing that decides."""
        return "+".join([leg.index.name for leg in self.legs])


def named_trade(trade_ids: NDArray[np.int64] | None, row: int) -> str:
    """A trade named in a message, by its ID when the ticket gave one, the whole number without
    quotes since #168, and by its row as the sheet counts rows either way, `trade 1001 at row 1`,
    `trade at row 3`: the words every refusal of a row's own fact uses, in the kernel and in the
    observations alike."""
    if trade_ids is None:
        return f"trade at row {row + 1}"
    return f"trade {int(trade_ids[row])} at row {row + 1}"


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
    discount_curve_key: tuple[str, ...] | None = None,
    second_leg: LegInputs | None = None,
) -> ResolvedTrades:
    """The one way to make ResolvedTrades: the rules of the first fixed_float profile, checked once,
    in this order, the first failure being the message; then the columns copied and frozen, the
    index's own into the batch's one leg, since two-index-fixed-float.md, and the trade's own
    into the record.

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
    here, and that month is its calculation period, derived here since onetime-averaging.md;
    each quantity is a whole number, positive, negative or zero, the first profile's
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

    A second leg, since two-index-fixed-float.md, is the second index's side of the same rows,
    LegInputs, checked after the first leg's rules and before the payment's: its index is not
    the first again and not another index of the first's name, one index for one name; it
    quotes in the first's quote currency and quote quantity units and settles in the first's
    currency, since the two entered prices add into one, and no conversion between differently
    quoted legs is invented; the settlement is financial, a two-index physical delivery being
    outside this version; then the leg's own rules, the index a futures or an IFERC one made
    with a reporting lot, its specification rows and methods per occurrence, its methods
    under its own kind, lastday alone on an IFERC index, and its contract rows and fixed
    prices per component, named second_schedule_method and second_fixed_price in a refusal,
    the fields they came from. The trade's facts are checked once, whatever the legs. The
    pair's combined fixed price, the two entered prices summed per component, is formed once
    here and checked finite, since two finite prices can sum past the largest number and
    nothing is published that a reader would then fail on; a one-index batch's is its leg's
    own.
    """
    schedule = trade_schedule_of(index)
    lot = reporting_lot_of(index)
    occurrences = _the_occurrences(
        trade_dates,
        trade_ids,
        clearing_house,
        counterparty,
        discount_curve_key,
        broker,
        marketing_reserve,
    )
    _the_keys(route, discount_curve_key)
    _the_selections(index, specification, schedule_method, quantity_per, occurrences)
    _the_method(schedule_method, settlement, trade_ids, index.kind)
    _the_components(occurrence, quantity, start_date, end_date, trade_ids, occurrences)
    _the_leg_columns(
        contract, fixed_price, occurrence, trade_ids, len(schedule.codes), "contract", "fixed_price"
    )
    legs = (
        _the_leg(
            index,
            schedule,
            lot,
            specification,
            schedule_method,
            contract,
            fixed_price,
            schedule_month,
        ),
    )
    if second_leg is not None:
        legs = (
            *legs,
            _the_second_leg(index, second_leg, settlement, trade_ids, occurrence, occurrences),
        )
    pays = _the_payment(settlement, payment, occurrences, occurrence.size)
    quantities = _frozen_numbers(quantity)
    starts, ends = _frozen_days(start_date), _frozen_days(end_date)
    days = (ends - starts).astype(np.int64) + 1  # made here and owned here: frozen below
    days.setflags(write=False)
    period_start, period_end = _the_calculation_periods(starts)
    brokered = _the_brokered(broker, occurrences)
    return ResolvedTrades(
        instrument,
        route,
        settlement,
        _frozen_rows(quantity_per),
        None if trade_ids is None else _frozen_ids(trade_ids),
        clearing_house,
        counterparty,
        discount_curve_key,
        broker,
        brokered,
        _frozen_days(trade_dates),
        _frozen_rows(occurrence),
        quantities,
        starts,
        ends,
        period_start,
        period_end,
        days,
        _the_component_quantity(quantity_per, quantities, days, trade_ids, occurrence),
        None if marketing_reserve is None else _frozen_numbers(marketing_reserve),
        pays,
        legs,
        legs[0].fixed_price if len(legs) == 1 else _the_combined_price(legs, trade_ids, occurrence),
    )


def _the_combined_price(
    legs: tuple[LegTerms, ...],
    trade_ids: NDArray[np.int64] | None,
    occurrence: NDArray[np.intp],
) -> NDArray[np.float64]:
    """A pair's fixed price per component, since two-index-fixed-float.md's third pull request:
    the two legs' entered prices summed, formed once here, checked finite where it is made, since
    two finite prices can sum past the largest number and nothing is published that a reader
    would then fail on, the first such component refused by its trade in the pair's shared quote
    unit, and frozen. A one-index batch's is its leg's own frozen array, which the caller takes
    by reference with no call here, so the one-leg path runs as it did."""
    first, second = legs[0].fixed_price, legs[1].fixed_price
    with np.errstate(over="ignore"):  # the overflow is this rule's to catch, below
        combined = first + second
    outrun = ~np.isfinite(combined)
    if outrun.any():
        k = int(outrun.argmax())
        quote = legs[0].index.conventions
        raise ValueError(
            f"{named_trade(trade_ids, int(occurrence[k]))} has {float(combined[k])!r} of combined "
            f"fixed price, expected a finite price in {quote.quote_currency_unit} per "
            f"{quote.quote_quantity_unit}; its legs' prices, {float(first[k])!r} and "
            f"{float(second[k])!r}, sum past the largest number"
        )
    combined.setflags(write=False)
    return combined


def _the_leg(
    index: Index,
    schedule: FuturesSchedule | IfercSchedule,
    lot: ReportingLot,
    specification: NDArray[np.intp],
    schedule_method: NDArray[np.intp],
    contract: NDArray[np.intp],
    fixed_price: NDArray[np.float64],
    schedule_month: NDArray[np.int64] | None,
) -> LegTerms:
    """A leg over its checked columns, each copied into its type and frozen; the schedule's
    months the resolution's reading handed over or read here once, owned by the leg."""
    months = (
        schedule_months(schedule)
        if schedule_month is None
        else np.array(schedule_month, dtype=np.int64)
    )
    months.setflags(write=False)
    return LegTerms(
        index,
        schedule,
        lot,
        _frozen_rows(specification),
        _frozen_rows(schedule_method),
        _frozen_rows(contract),
        _frozen_numbers(fixed_price),
        months,
    )


def _the_second_leg(
    first: Index,
    second: LegInputs,
    settlement: Settlement,
    trade_ids: NDArray[np.int64] | None,
    occurrence: NDArray[np.intp],
    occurrences: int,
) -> LegTerms:
    """The second leg over the pair's rules and its own, since two-index-fixed-float.md, in
    this order: another index than the first, by identity and by name; the first's quote
    currency, quote quantity and settlement currency units; a financial settlement; then the
    first leg's rules over this index and these columns, each refusal naming the second leg's
    field."""
    index = second.index
    if index is first:
        raise ValueError(
            f"index 2 is index 1, {first.name!r}, again, expected two distinct indexes; a pair of "
            "one index is outside this version"
        )
    if index.name == first.name:
        raise ValueError(
            f"index 2 is another index named {index.name!r}, the name of index 1, expected one "
            "index for one name"
        )
    mine, theirs = index.conventions, first.conventions
    if (mine.quote_currency_unit, mine.quote_quantity_unit, mine.currency_unit) != (
        theirs.quote_currency_unit,
        theirs.quote_quantity_unit,
        theirs.currency_unit,
    ):
        raise ValueError(
            f"index 2 {index.name!r} quotes in {mine.quote_currency_unit} per "
            f"{mine.quote_quantity_unit} and settles in {mine.currency_unit}, expected "
            f"{theirs.quote_currency_unit} per {theirs.quote_quantity_unit} settled in "
            f"{theirs.currency_unit} as index 1 {first.name!r}; two legs' prices add in one unit"
        )
    if settlement is Settlement.PHYSICAL:
        raise ValueError(
            "settlement_method is 'physical', expected 'financial' with two indexes; a two-index "
            "physical settlement is outside this version"
        )
    schedule = trade_schedule_of(index)
    lot = reporting_lot_of(index)
    _the_leg_selections(index, second.specification, second.schedule_method, occurrences, "second_")
    _the_method(second.schedule_method, settlement, trade_ids, index.kind, "second_schedule_method")
    _the_leg_columns(
        second.contract,
        second.fixed_price,
        occurrence,
        trade_ids,
        len(schedule.codes),
        "second_contract",
        "second_fixed_price",
    )
    return _the_leg(
        index,
        schedule,
        lot,
        second.specification,
        second.schedule_method,
        second.contract,
        second.fixed_price,
        second.schedule_month,
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
    _the_leg_selections(index, specification, schedule_method, occurrences, "")
    _the_choices(
        (("quantity_per", quantity_per, len(BASES), "a basis, its position among BASES"),),
        occurrences,
    )


def _the_leg_selections(
    index: Index,
    specification: NDArray[np.intp],
    schedule_method: NDArray[np.intp],
    occurrences: int,
    prefix: str,
) -> None:
    """A leg's two choices per occurrence, its specification a row of its index's specifications
    and its method a position among METHODS, named with the second leg's prefix where they are
    the second leg's."""
    _the_choices(
        (
            (
                f"{prefix}specification",
                specification,
                len(index.specifications.names),
                "a row of the index's specifications",
            ),
            (
                f"{prefix}schedule_method",
                schedule_method,
                len(METHODS),
                "a method, its position among METHODS",
            ),
        ),
        occurrences,
    )


def _the_choices(
    choices: tuple[tuple[str, NDArray[np.intp], int, str], ...], occurrences: int
) -> None:
    """Each choice one per occurrence and within its members, the first out of range refused by
    its row."""
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
    field: str = "schedule_method",
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
                f"{field} of {named_trade(trade_ids, i)} is "
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
    discount_curve_key: tuple[str, ...] | None,
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
        ("discount_curve_key", discount_curve_key),
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


def _the_keys(route: Route, discount_curve_key: tuple[str, ...] | None) -> None:
    """A bilateral batch names its curves, since named-curves-slice-3.md, one key per occurrence,
    and a cleared batch names none, the definition's condition; the resolution reads each key by
    the curve's name rule, and the kernel holds the presence alone."""
    match route:
        case Route.BILATERAL:
            if discount_curve_key is None:
                raise ValueError(
                    "discount_curve_key is missing, expected it when route = bilateral"
                )
        case Route.CLEARED:
            if discount_curve_key is not None:
                raise ValueError(
                    f"discount_curve_key is {discount_curve_key[0]!r}, expected none unless "
                    "route = bilateral"
                )
        case _:
            assert_never(route)


def _the_components(
    occurrence: NDArray[np.intp],
    quantity: NDArray[np.float64],
    start_date: NDArray[np.datetime64],
    end_date: NDArray[np.datetime64],
    trade_ids: NDArray[np.int64] | None,
    occurrences: int,
) -> None:
    """The trade's columns, aligned, one or more, each of an occurrence and every occurrence
    holding one; each component's end on or after its start and both in one calendar month, each
    quantity whole, zero included, the days or a quantity refused naming the trade it belongs to,
    since a strip's component is no row of the sheet. A leg's columns are _the_leg_columns'."""
    components = occurrence.size
    if components == 0:
        raise ValueError("occurrence has 0 rows, expected at least 1, one per component")
    for name, column in (
        ("quantity", quantity),
        ("start_date", start_date),
        ("end_date", end_date),
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


def _the_leg_columns(
    contract: NDArray[np.intp],
    fixed_price: NDArray[np.float64],
    occurrence: NDArray[np.intp],
    trade_ids: NDArray[np.int64] | None,
    schedule_rows: int,
    contract_name: str,
    price_name: str,
) -> None:
    """A leg's two columns per component, aligned with the trade's: each contract a row of the
    leg's schedule, each price finite, a price refused naming the trade it belongs to and the
    field it came from, fixed_price or since two-index-fixed-float.md second_fixed_price."""
    components = occurrence.size
    for name, column in ((contract_name, contract), (price_name, fixed_price)):
        if column.size != components:
            raise ValueError(
                f"{name} has {column.size} rows, expected {components}, one per component"
            )
    outside = (contract < 0) | (contract >= schedule_rows)
    if outside.any():
        k = int(outside.argmax())
        raise ValueError(
            f"{contract_name} row {k + 1} is {contract[k]}, "
            f"expected a row of the schedule, 0 to {schedule_rows - 1}"
        )
    finite_prices(
        fixed_price, lambda k: f"{price_name} of {named_trade(trade_ids, int(occurrence[k]))}"
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


def payments_after_observations(
    payment_date: NDArray[np.datetime64],
    last_observed: NDArray[np.datetime64],
    where: Callable[[int], str],
) -> None:
    """A financial settlement's rule, one owner since payment-day-date-or-rule.md: each payment
    falls after the last observation it pays for, the day its final price exists, since a
    payment on or before it would have nothing to pay; the first on or before it, in the
    caller's order, is refused in the caller's words for its position, a group's contract in
    the encoding and a month's code in a quote, with the two days. The two arrays stand
    aligned, one payment day and one last observation per item."""
    early = payment_date <= last_observed
    if early.any():
        k = int(early.argmax())
        raise ValueError(
            f"{where(k)} pays on {payment_date[k]}, expected a day after its last observation, "
            f"{last_observed[k]}, when its final price exists"
        )


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
    """For a financial settlement the terms, an entered payment day and a calendar per occurrence
    and a day per component, the arrays frozen; for a physical one none."""
    match settlement:
        case Settlement.FINANCIAL:
            if payment is None:
                raise ValueError(
                    "payment is missing, expected a payment day and a calendar per occurrence and "
                    "one date per component with a financial settlement"
                )
            for name, count in (
                ("day", payment.entered.is_date.size),
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
            return PaymentTerms(payment.entered, payment.calendar, _frozen_days(payment.date))
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


def month_bounds(
    month: NDArray[np.int64],
) -> tuple[NDArray[np.datetime64], NDArray[np.datetime64]]:
    """The first and the last calendar day of each month given, as numpy counts months: the days a
    whole-month component covers, the bounds an explicit period's components are clipped to, and
    since onetime-averaging.md a monthly component's calculation period, one conversion each way
    and one day subtracted."""
    first = month.astype("datetime64[M]").astype("datetime64[D]")
    after = (month + 1).astype("datetime64[M]").astype("datetime64[D]")
    last = cast(NDArray[np.datetime64], after - np.timedelta64(1, "D"))  # a day, not a span
    return first, last


def _the_calculation_periods(
    start_date: NDArray[np.datetime64],
) -> tuple[NDArray[np.datetime64], NDArray[np.datetime64]]:
    """Each component's calculation period, since onetime-averaging.md: under the monthly
    selection, the one this version books, the calendar month its first day lies in, its last day
    in the same month by the components' rule, the two bounds made once by month_bounds and
    frozen. The identity the encoding keys the payment groups by, a part of a month and the whole
    of it alike, so that two rows of one month paying on one day are one group, each component
    keeping its own days, weights and quantity; a whole-period average will book its own two
    dates here."""
    first, last = month_bounds(start_date.astype("datetime64[M]").astype(np.int64))
    first.setflags(write=False)
    last.setflags(write=False)
    return first, last


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
