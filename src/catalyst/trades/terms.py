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
from functools import partial
from typing import Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from catalyst.index_definitions.contract_codes import schedule_months
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.iferc_schedule import IfercSchedule
from catalyst.index_definitions.index import Index, ReportingLot
from catalyst.index_definitions.kind import Kind, described
from catalyst.instruments.definitions import FLOAT_FLOAT, Instrument
from catalyst.instruments.fields import DatesOrTexts
from catalyst.trades.schedule_methods import (
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
    # period: the quantity is the total of a onetime calculation period, the whole window's,
    # since onetime-averaging.md; refused under monthly, which has no window, and not yet priced,
    # the whole-period average being that ticket's third slice.
    PERIOD = "period"


class SettlementFrequency(Enum):
    """How many calculation periods a row's days make, since onetime-averaging.md, the
    independently calculated payoff periods and never the cash day, which payment_day decides.
    monthly: one period per calendar month the row covers, each with its own observations,
    weights and quantity, the one selection this version books. onetime: one period across the
    row's start_date and end_date, its observations averaged together and its quantity the
    window's; read and refused by every consumer until the third slice prices it."""

    MONTHLY = "monthly"
    ONETIME = "onetime"


# The members of the basis choice and of the frequency choice in the definition's order, and
# their names as the sheet spells them: a selection holds each occurrence's choice as its
# position here, so that the kernel gathers and compares positions and never texts, and a
# reader turns a position back into its name. The schedule methods' members and names are
# schedule_methods.py's, the same way.
BASES: Final = tuple(QuantityPer)
BASIS_NAMES: Final = np.array([member.value for member in BASES], dtype=object)
BASIS_NAMES.setflags(write=False)
FREQUENCIES: Final = tuple(SettlementFrequency)
FREQUENCY_NAMES: Final = np.array([member.value for member in FREQUENCIES], dtype=object)
FREQUENCY_NAMES.setflags(write=False)


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
    this index's schedule each component's month is; and schedule_month, this schedule's months
    as the resolution read them, or None to read them in the builder. No price: since
    two-index-one-price.md the one fixed price is the trade's."""

    index: Index
    specification: NDArray[np.intp]
    schedule_method: NDArray[np.intp]
    contract: NDArray[np.intp]
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
    contract[k] the row of the schedule the component's month is, or, for a onetime period since
    onetime-averaging.md, the row of the contract pricing the window's first day, the first whose
    expiry is on or after it by the calendar's rule, read for nothing that prices, the calendar
    giving each of its days its own contract and the window's two dates naming it. No price:
    since two-index-one-price.md the fixed price is the trade's, one outright price whatever the
    legs. Then schedule_month[i], since #186, the
    calendar month of every row of the schedule as numpy counts months from 1970, read once by
    the resolution against the ticket's codes and kept for the encoding's contract-month axes.
    Every array read-only. And subtracted, since float-float-spread.md: whether the leg's
    floating price is paid, not received, by a positive quantity, the second leg of a float_float
    and no other, read once by the encoding, which signs the leg's amounts with it."""

    index: Index
    schedule: FuturesSchedule | IfercSchedule
    reporting_lot: ReportingLot
    specification: NDArray[np.intp]
    schedule_method: NDArray[np.intp]
    contract: NDArray[np.intp]
    schedule_month: NDArray[np.int64]
    subtracted: bool


@dataclass(frozen=True, slots=True)
class ResolvedTrades:
    """The trade's own facts, and its legs. The instrument, the definition the terms were resolved
    under; the route and the settlement, one each for the batch. Then two sets of columns
    aligned by position, all read-only. Per occurrence, the ticket's rows in order:
    quantity_per[i] the basis its quantity is stated per, the position of the member among
    BASES; settlement_frequency[i] since onetime-averaging.md how many calculation periods its
    days make, the position among FREQUENCIES, monthly the one this version books, read by the
    rules here and kept for the readback; nearby[i] since nearby-selection.md which listed
    contract prices each of its observation days, counted from the day's prompt contract, 1
    the prompt and 2 the next the schedule lists, a whole number of 1 or more read by the
    encoding's reference rule; trade_dates[i] the day the deal was struck,
    trade_ids[i] its trade_id, the source
    system's whole number of at most 15 digits held as an int64 since #168, clearing_house[i] its
    clearing organization, counterparty[i] since #175 the counterparty it faces and broker[i] its
    broker, the IDs an array and the three labels tuples, each None as a whole when the field was
    not given, each kept as given and read for nothing but a message's words and, since #188, the
    broker's text for brokered[i], whether the row names a broker and so charges brokerage:
    False for every row when the field was not given and where the row's text is none in any
    case, the desk's word for a screen trade, reserve-fee-applicability.md; marketing_reserve[i]
    since #175 the marketing cost the row booked once, a finite amount of zero or more in the
    settlement currency, None as a whole when neither the template nor the ticket supplied it,
    read by the reserves alone; cva_reserve[i] since cva-reserve.md the credit valuation
    adjustment reserve the row booked once, a finite amount of either sign in the settlement
    currency, None as a whole when neither supplied it, read by the reserves alone;
    discount_curve_key[i], since named-curves-slice-3.md, the
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
    once here, the one quantity the encoding converts and nothing later scales again, and
    price[k], since two-index-one-price.md the trade's own: the one price agreed for the
    deal in the quote unit its indexes share, each occurrence's entered price on every component
    of its row, finite, a fixed_float's fixed_price, the outright price of the sum of two
    indexes where the batch is on a pair and the index's price where it is on one, and since
    float-float-spread.md a float_float's spread_price, paid against the first index's price
    less the second's. Then
    payment, the terms a financial settlement pays by and the days they give, one day per
    component shared by every leg, and None for a physical one, which pays on no day.

    Then legs, since two-index-fixed-float.md: the LegTerms of each leg in leg order, one today,
    each the index a leg prices on with its schedule, reporting lot, specification rows, methods
    and contract rows, so that what an index owns is held once per leg and what the trade owns
    is held once, the fixed price among the trade's since two-index-one-price.md. The first leg
    is the batch's for what a batch has one of: the fee source of its reserves, the coefficient
    its fixed leg is made with and the first word of the name its handle carries."""

    instrument: Instrument
    route: Route
    settlement: Settlement
    quantity_per: NDArray[np.intp]
    settlement_frequency: NDArray[np.intp]
    nearby: NDArray[np.intp]
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
    price: NDArray[np.float64]
    marketing_reserve: NDArray[np.float64] | None
    cva_reserve: NDArray[np.float64] | None
    payment: PaymentTerms | None
    legs: tuple[LegTerms, ...]

    def named(self, component: int) -> str:
        """A component's trade named in a message, by its ID when the ticket gave one and by its
        row as the sheet counts rows either way: `trade 1001 at row 1`, `trade at row 3`."""
        return named_trade(self.trade_ids, int(self.occurrence[component]))

    @property
    def descriptor(self) -> str:
        """The words a handle of the batch carries where a single index's name stands: the legs'
        index names in leg order, one index's name alone, a fixed_float pair's joined by `+`,
        the sum it pays, and since float-float-spread.md a float_float's by `-`, the difference;
        a readable descriptor and nothing more, read by nothing that decides."""
        joiner = "-" if self.instrument is FLOAT_FLOAT else "+"
        return joiner.join([leg.index.name for leg in self.legs])


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
    settlement_frequency: NDArray[np.intp],
    nearby: NDArray[np.intp],
    trade_ids: NDArray[np.int64] | None,
    clearing_house: tuple[str, ...] | None,
    broker: tuple[str, ...] | None,
    trade_dates: NDArray[np.datetime64],
    occurrence: NDArray[np.intp],
    contract: NDArray[np.intp],
    quantity: NDArray[np.float64],
    start_date: NDArray[np.datetime64],
    end_date: NDArray[np.datetime64],
    price: NDArray[np.float64],
    payment: PaymentTerms | None,
    *,
    schedule_month: NDArray[np.int64] | None = None,
    counterparty: tuple[str, ...] | None = None,
    marketing_reserve: NDArray[np.float64] | None = None,
    cva_reserve: NDArray[np.float64] | None = None,
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
    range refused. Each occurrence has a nearby, since nearby-selection.md, a whole number of 1
    or more the caller read by whole_nearbys, the contract its observation days are priced
    by counted from each day's prompt: a number above 1 stands on one futures index, under a
    financial settlement and the asian method, nearby_rules, the first row elsewhere refused
    by name. A penultimate, last3day or asian row settles financially, each being cash
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
    under its own kind, lastday alone on an IFERC index, and its contract rows per component,
    named second_schedule_method and second_contract in a refusal, the fields they came from.
    The trade's facts are checked once, whatever the legs, the one fixed price among them
    since two-index-one-price.md: the outright price of the deal, the price of the sum of the
    two indexes where the batch is on a pair, entered once and never per leg, so that no
    second price exists to add and nothing is derived from two.

    A float_float, since float-float-spread.md, is held to its own rules before any other,
    spread_legs and spread_rules: two legs, the bilateral route and no named broker. Its one
    price is its spread_price, named so in a refusal, and its second leg is the subtracted
    one, the leg whose amounts the encoding signs; a fixed_float subtracts no leg.
    """
    spread = instrument is FLOAT_FLOAT
    if spread:
        spread_legs(1 if second_leg is None else 2)
        spread_rules(route, broker, partial(named_trade, trade_ids))
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
        cva_reserve,
    )
    _the_keys(route, discount_curve_key)
    _the_selections(
        index, specification, schedule_method, quantity_per, settlement_frequency, occurrences
    )
    frequency_rules(
        settlement_frequency,
        quantity_per,
        schedule_method,
        settlement,
        index.kind,
        second_leg is not None,
        partial(named_trade, trade_ids),
    )
    _the_nearbys(nearby, occurrences)
    nearby_rules(
        nearby,
        schedule_method,
        settlement,
        index.kind,
        second_leg is not None,
        partial(named_trade, trade_ids),
    )
    _the_method(schedule_method, settlement, trade_ids, index.kind)
    _the_components(occurrence, quantity, start_date, end_date, trade_ids, occurrences)
    onetime = settlement_frequency[occurrence] == FREQUENCIES.index(SettlementFrequency.ONETIME)
    _the_monthly_components(start_date, end_date, onetime, trade_ids, occurrence)
    _the_contract_column(contract, occurrence, len(schedule.codes), "contract")
    _the_prices(price, occurrence, trade_ids, price_words(instrument)[0])
    legs = (
        _the_leg(
            index, schedule, lot, specification, schedule_method, contract, schedule_month, False
        ),
    )
    if second_leg is not None:
        legs = (
            *legs,
            _the_second_leg(
                index, second_leg, settlement, trade_ids, occurrence, occurrences, spread
            ),
        )
    pays = _the_payment(settlement, payment, occurrences, occurrence.size)
    quantities = _frozen_numbers(quantity)
    starts, ends = _frozen_days(start_date), _frozen_days(end_date)
    days = (ends - starts).astype(np.int64) + 1  # made here and owned here: frozen below
    days.setflags(write=False)
    period_start, period_end = _the_calculation_periods(starts, ends, onetime)
    brokered = _the_brokered(broker, occurrences)
    return ResolvedTrades(
        instrument,
        route,
        settlement,
        _frozen_rows(quantity_per),
        _frozen_rows(settlement_frequency),
        _frozen_rows(nearby),
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
        _frozen_numbers(price),
        None if marketing_reserve is None else _frozen_numbers(marketing_reserve),
        None if cva_reserve is None else _frozen_numbers(cva_reserve),
        pays,
        legs,
    )


def price_words(instrument: Instrument) -> tuple[str, str]:
    """What a batch's one price and the trade's own side of a payment are called in a message
    and on a readback, the words of its instrument: `spread_price` and `spread leg` on a
    float_float since float-float-spread.md, `fixed_price` and `fixed leg` otherwise: the one
    owner of the four words, read once where a batch is resolved, for the field to read and to
    name, and where a refusal is worded or a header written."""
    if instrument is FLOAT_FLOAT:
        return "spread_price", "spread leg"
    return "fixed_price", "fixed leg"


def spread_legs(legs: int) -> None:
    """A float_float's first rule, float-float-spread.md: two legs, since a spread is the first
    index's price less the second's and one index has nothing to be less than; the kernel's
    rule, applied by the resolution as well before a leg's field is read, so that one index is
    refused in these words."""
    if legs != 2:
        raise ValueError(
            f"indexes are {legs}, expected two with a float_float; a spread is the first index's "
            "price less the second's"
        )


def spread_rules(route: Route, broker: tuple[str, ...] | None, named: Callable[[int], str]) -> None:
    """A float_float's rules over its route and its brokers, float-float-spread.md: the
    bilateral route, a cleared spread not being built, and no named broker, the field left out
    or none in any case on every row, a brokered spread not being built, the first row naming
    one refused by its trade. The kernel's rule, applied by the resolution as well before a
    conditional field is read, so that a cleared spread is refused in these words and never as
    a missing clearing house."""
    if route is not Route.BILATERAL:
        raise ValueError(
            f"route is {route.value!r}, expected 'bilateral' on a float_float; a cleared spread "
            "is not built"
        )
    if broker is not None:
        for i, text in enumerate(broker):
            if text.lower() != UNBROKERED:
                raise ValueError(
                    f"broker of {named(i)} is {text!r}, expected none on a float_float; a "
                    "brokered spread is not built"
                )


def _the_prices(
    price: NDArray[np.float64],
    occurrence: NDArray[np.intp],
    trade_ids: NDArray[np.int64] | None,
    field: str,
) -> None:
    """The trade's one price column, since two-index-one-price.md: a price per component,
    aligned with the trade's components, each finite, a price refused naming the trade it
    belongs to and the field it came from, its instrument's, handed in: fixed_price, the
    outright price of a fixed_float whatever its legs, or since float-float-spread.md a
    float_float's spread_price."""
    _the_component_column(field, price, occurrence.size)
    finite_prices(price, lambda k: f"{field} of {named_trade(trade_ids, int(occurrence[k]))}")


def _the_leg(
    index: Index,
    schedule: FuturesSchedule | IfercSchedule,
    lot: ReportingLot,
    specification: NDArray[np.intp],
    schedule_method: NDArray[np.intp],
    contract: NDArray[np.intp],
    schedule_month: NDArray[np.int64] | None,
    subtracted: bool,
) -> LegTerms:
    """A leg over its checked columns, each copied into its type and frozen; the schedule's
    months the resolution's reading handed over or read here once, owned by the leg; and
    whether a positive quantity pays its price, a float_float's second leg alone."""
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
        months,
        subtracted,
    )


def _the_second_leg(
    first: Index,
    second: LegInputs,
    settlement: Settlement,
    trade_ids: NDArray[np.int64] | None,
    occurrence: NDArray[np.intp],
    occurrences: int,
    subtracted: bool,
) -> LegTerms:
    """The second leg over the pair's rules and its own, since two-index-fixed-float.md, in
    this order: another index than the first, by identity and by name; the first's quote
    currency, quote quantity and settlement currency units; a financial settlement; then the
    first leg's rules over this index and these columns, each refusal naming the second leg's
    field. No price of its own since two-index-one-price.md. Subtracted, since
    float-float-spread.md, when the batch is a float_float, whose two prices net where a
    fixed_float's add, the unit refusal saying which."""
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
            f"{theirs.currency_unit} as index 1 {first.name!r}; two legs' prices "
            f"{'net' if subtracted else 'add'} in one unit"
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
    _the_contract_column(second.contract, occurrence, len(schedule.codes), "second_contract")
    return _the_leg(
        index,
        schedule,
        lot,
        second.specification,
        second.schedule_method,
        second.contract,
        second.schedule_month,
        subtracted,
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
    settlement_frequency: NDArray[np.intp],
    occurrences: int,
) -> None:
    """Each occurrence's four choices, one per occurrence: its specification a row of the index's
    specifications, its method a position among METHODS, its basis one among BASES and since
    onetime-averaging.md its frequency one among FREQUENCIES, the first out of range refused by
    its row."""
    _the_leg_selections(index, specification, schedule_method, occurrences, "")
    _the_choices(
        (
            ("quantity_per", quantity_per, len(BASES), "a basis, its position among BASES"),
            (
                "settlement_frequency",
                settlement_frequency,
                len(FREQUENCIES),
                "a frequency, its position among FREQUENCIES",
            ),
        ),
        occurrences,
    )


def frequency_rules(
    settlement_frequency: NDArray[np.intp],
    quantity_per: NDArray[np.intp],
    schedule_method: NDArray[np.intp],
    settlement: Settlement,
    kind: Kind,
    paired: bool,
    named: Callable[[int], str],
) -> None:
    """Each occurrence's frequency with the terms it stands under, since onetime-averaging.md,
    the kernel's rule, applied by the resolution before any period is built or observed so that
    a refused onetime row is refused in these words and never in an observation's, and since
    dated-quotes.md by a quote and a request for quote over their template's one set of terms.
    A onetime period, one average over every pricing day of the row's window, is priced on a
    futures index alone, an IFERC month having one index published once; on one index, a pair's
    onetime period not being built; under a financial settlement, since it is cash settled on
    its average; under the asian method, the expiry-based methods taking their contract's month;
    and in a quantity of period, the window's total, or calday, never month, which says nothing
    of a window. Under monthly the basis is month or calday, period being a window's total. The
    first occurrence that breaks a rule is refused in the words `named` gives it, a trade by its
    row or the quote, the rules in this order."""

    def first(rows: NDArray[np.bool_]) -> str:
        """The words for the first occurrence at fault, found only when a rule refuses."""
        return named(int(rows.argmax()))

    onetime = settlement_frequency == FREQUENCIES.index(SettlementFrequency.ONETIME)
    if onetime.any():
        if kind is Kind.IFERC:
            raise ValueError(
                f"settlement_frequency of {first(onetime)} is 'onetime', expected 'monthly' on an "
                "IFERC index; an IFERC month has one index, published once, and a onetime period "
                "averages the pricing days of a futures index"
            )
        if paired:
            raise ValueError(
                f"settlement_frequency of {first(onetime)} is 'onetime', expected 'monthly' with "
                "two indexes; a onetime period on a pair is not built"
            )
        if settlement is Settlement.PHYSICAL:
            raise ValueError(
                f"settlement_method is 'physical', expected 'financial' with settlement_frequency "
                f"= onetime of {first(onetime)}; a onetime period is cash settled on its average"
            )
        unaveraged = onetime & (schedule_method != METHODS.index(ScheduleMethod.ASIAN))
        if unaveraged.any():
            k = int(unaveraged.argmax())
            raise ValueError(
                f"schedule_method of {named(k)} is "
                f"{METHODS[int(schedule_method[k])].value!r}, expected 'asian' under "
                "settlement_frequency = onetime; a onetime period averages every pricing day it "
                "covers, and the expiry-based methods take their contract's month"
            )
        by_month = onetime & (quantity_per == BASES.index(QuantityPer.MONTH))
        if by_month.any():
            raise ValueError(
                f"quantity_per of {first(by_month)} is 'month', expected 'period' or 'calday' "
                "under settlement_frequency = onetime; month says nothing of a window, period is "
                "its total and calday its days"
            )
    period = ~onetime & (quantity_per == BASES.index(QuantityPer.PERIOD))
    if period.any():
        raise ValueError(
            f"quantity_per of {first(period)} is 'period', expected 'month' or 'calday' under "
            "settlement_frequency = monthly; period is the total of a onetime period and says "
            "nothing of a month"
        )


def _the_nearbys(nearby: NDArray[np.intp], occurrences: int) -> None:
    """Each occurrence's nearby, one per occurrence and 1 or more, the first other refused by
    its row: a position is counted from the prompt, and nothing stands before it."""
    if nearby.size != occurrences:
        raise ValueError(
            f"nearby has {nearby.size} rows, expected {occurrences}, one per occurrence"
        )
    before = nearby < 1
    if before.any():
        i = int(before.argmax())
        raise ValueError(
            f"nearby row {i + 1} is {nearby[i]}, expected 1 or more, 1 the prompt contract and "
            "2 the next the schedule lists"
        )


def nearby_rules(
    nearby: NDArray[np.intp],
    schedule_method: NDArray[np.intp],
    settlement: Settlement,
    kind: Kind,
    paired: bool,
    named: Callable[[int], str],
) -> None:
    """Each occurrence's nearby with the terms it stands under, since nearby-selection.md, the
    kernel's rule. A nearby above 1, a contract after the day's prompt, is priced on a futures
    index alone, an IFERC month having one index and no contract after it to count; on one
    index, a later nearby on a pair not being built; under a financial settlement, a physical
    position delivering its own contract; and under the asian method, the expiry-based methods
    taking their own contract's days. Everywhere else the nearby is 1. The first occurrence
    that breaks a rule is refused in the words `named` gives it, the rules in this order."""
    later = nearby > 1
    if not later.any():
        return
    k = int(later.argmax())
    if kind is Kind.IFERC:
        raise ValueError(
            f"nearby of {named(k)} is {int(nearby[k])}, expected 1 on an IFERC index; an IFERC "
            "month has one index, published once, and no contract after the prompt to count"
        )
    if paired:
        raise ValueError(
            f"nearby of {named(k)} is {int(nearby[k])}, expected 1 with two indexes; a later "
            "nearby on a pair is not built"
        )
    if settlement is Settlement.PHYSICAL:
        raise ValueError(
            f"nearby of {named(k)} is {int(nearby[k])}, expected 1 under settlement_method = "
            "physical; a physical position delivers its own contract, and a later nearby is "
            "cash settled on its average"
        )
    unaveraged = later & (schedule_method != METHODS.index(ScheduleMethod.ASIAN))
    if unaveraged.any():
        k = int(unaveraged.argmax())
        raise ValueError(
            f"nearby of {named(k)} is {int(nearby[k])}, expected 1 under schedule_method = "
            f"{METHODS[int(schedule_method[k])].value}; the expiry-based methods take their own "
            "contract's days, and a later nearby is priced under asian"
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
    cva_reserve: NDArray[np.float64] | None,
) -> int:
    """One or more, a date each and, for the IDs, each label tuple and each entered reserve
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
    for name, amounts in (("marketing_reserve", marketing_reserve), ("cva_reserve", cva_reserve)):
        if amounts is not None and amounts.size != occurrences:
            raise ValueError(
                f"{name} has {amounts.size} amounts, expected {occurrences}, one per occurrence"
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
    holding one; each component's end on or after its start, each quantity whole, zero included,
    the days or a quantity refused naming the trade it belongs to, since a strip's component is
    no row of the sheet; a monthly component's one calendar month is _the_monthly_components'
    rule, once the frequencies are known. A leg's contract column is _the_contract_column's and
    the trade's prices _the_prices'."""
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
    whole_quantities(
        quantity, lambda k: f"quantity of {named_trade(trade_ids, int(occurrence[k]))}"
    )


def _the_monthly_components(
    start_date: NDArray[np.datetime64],
    end_date: NDArray[np.datetime64],
    onetime: NDArray[np.bool_],
    trade_ids: NDArray[np.int64] | None,
    occurrence: NDArray[np.intp],
) -> None:
    """A monthly component's days lie in one calendar month, since a monthly component is one
    contract month's and a quantity per day over no day states nothing; a onetime component,
    since onetime-averaging.md, covers its row's whole window, months and all, and is held to
    nothing here. The first monthly component in two months is refused by its trade."""
    two_months = (start_date.astype("datetime64[M]") != end_date.astype("datetime64[M]")) & ~onetime
    if two_months.any():
        k = int(two_months.argmax())
        raise ValueError(
            f"{named_trade(trade_ids, int(occurrence[k]))} covers {start_date[k]} to "
            f"{end_date[k]}, expected one calendar month per component"
        )


def _the_component_column(
    name: str, column: NDArray[np.intp] | NDArray[np.float64], components: int
) -> None:
    """A column per component, aligned with the trade's components, else refused by its name
    and its count."""
    if column.size != components:
        raise ValueError(f"{name} has {column.size} rows, expected {components}, one per component")


def _the_contract_column(
    contract: NDArray[np.intp], occurrence: NDArray[np.intp], schedule_rows: int, name: str
) -> None:
    """A leg's contract column per component, aligned with the trade's components, each a row
    of the leg's schedule, named contract or since two-index-fixed-float.md second_contract."""
    _the_component_column(name, contract, occurrence.size)
    outside = (contract < 0) | (contract >= schedule_rows)
    if outside.any():
        k = int(outside.argmax())
        raise ValueError(
            f"{name} row {k + 1} is {contract[k]}, "
            f"expected a row of the schedule, 0 to {schedule_rows - 1}"
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


def whole_nearbys(values: NDArray[np.float64], where: Callable[[int], str]) -> NDArray[np.intp]:
    """Each nearby a whole number of 1 or more, since nearby-selection.md: a position counted
    from the prompt contract, 1 the prompt itself, finite, whole, at least 1 and of at most 15
    digits, the digits a cell carries exactly; the first that is not is refused in the
    caller's words for its position, the row in a ticket and the field in a template. Then
    the values converted once to whole positions, the one form every later reader takes;
    whether the schedule lists a contract that far on is the reference rule's, day by day."""
    bad = (
        ~np.isfinite(values)
        | (values != np.round(values))
        | (values < 1)
        | (values > TRADE_ID_LIMIT)
    )
    if bad.any():
        k = int(bad.argmax())
        value = float(values[k])
        whole = np.isfinite(value) and value == round(value) and abs(value) <= TRADE_ID_LIMIT
        shown = str(int(value)) if whole else repr(value)
        raise ValueError(
            f"{where(k)} is {shown}, expected a whole number of 1 or more, of at most "
            f"{TRADE_ID_DIGITS} digits: 1 the prompt contract, 2 the next the schedule lists"
        )
    return values.astype(np.intp)


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
    entered quantity stands in every month the trade covers, and under period, since
    onetime-averaging.md, the entered quantity itself again, the total of the one component a
    onetime row is, the frozen column shared when no row chose calday; under calday the entered
    quantity times the component's covered days, a onetime row's whole window's, one
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
    end_date: NDArray[np.datetime64],
    onetime: NDArray[np.bool_],
) -> tuple[NDArray[np.datetime64], NDArray[np.datetime64]]:
    """Each component's calculation period, since onetime-averaging.md: under monthly the
    calendar month its first day lies in, its last day in the same month by the monthly
    components' rule, the two bounds made once by month_bounds; under onetime the component's
    own two dates, the row's whole window, so that the period is the component. Frozen. The
    identity the encoding keys the payment groups by, a part of a month and the whole of it
    alike, so that two rows of one month paying on one day are one group, each component keeping
    its own days, weights and quantity, and a window its own group."""
    first, last = month_bounds(start_date.astype("datetime64[M]").astype(np.int64))
    if onetime.any():
        first = np.where(onetime, start_date, first)
        last = np.where(onetime, end_date, last)
    first.setflags(write=False)
    last.setflags(write=False)
    return first, last


def onetime_components(terms: ResolvedTrades) -> NDArray[np.bool_]:
    """Which components are a onetime period's, since onetime-averaging.md: their occurrence's
    frequency gathered, one compare over the components, nothing stored twice."""
    return terms.settlement_frequency[terms.occurrence] == FREQUENCIES.index(
        SettlementFrequency.ONETIME
    )


def booked_words(
    terms: ResolvedTrades, leg: LegTerms, components: NDArray[np.intp]
) -> NDArray[np.object_]:
    """The booked period of each of those components in words, since onetime-averaging.md, the
    one source of the label a readback, a group and a refusal give it, made when asked and kept
    by nothing: period_words over this leg's schedule and the components' contracts, calculation
    periods and frequency, its contract's code under monthly, `K26`, and its two dates under
    onetime, `2026-05-26 to 2026-06-25`."""
    return period_words(
        leg.schedule.codes,
        leg.contract[components],
        onetime_components(terms)[components],
        terms.period_start[components],
        terms.period_end[components],
    )


def period_words(
    codes: tuple[str, ...],
    contract: NDArray[np.intp],
    window: NDArray[np.bool_],
    first: NDArray[np.datetime64],
    last: NDArray[np.datetime64],
) -> NDArray[np.object_]:
    """Each component's period in words from the arrays that hold it, since dated-quotes.md the
    one form a booking, a quote and a request for quote name a component by: its contract's
    code from the schedule's codes for a month, and for a window, which prices off whichever
    contracts its days fall on and no one contract names, its first and last day, `2026-05-26 to
    2026-06-25`, in the form every date in a refusal takes. One gather of the codes, and over
    the window components alone two date-to-text conversions and two joins, numpy's over the
    array; components without a window make no text but the codes'."""
    words = np.array(codes, dtype=object)[contract]
    if window.any():
        words[window] = np.strings.add(
            np.strings.add(np.datetime_as_string(first[window]), " to "),
            np.datetime_as_string(last[window]),
        )
    return words


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
