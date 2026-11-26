"""The two children of _CreateTrades and the batch they make. Resolution completes a template's
shared values and a ticket's rows into the resolved terms of one batch on one index or, since
two-index-fixed-float.md, on two, the second leg's two fields beside the first's: every field
from exactly one of the two, the required fields present and the conditional ones present when
their condition holds, one route and one settlement for the batch and a quantity unit, a method
and a basis per row, in that order, each distinct text of the three read once, the quantity unit
naming one of the index's specifications, every code of the index's
schedule read for its month once, each row's period chosen row by row since #172, its two dates
when both are supplied and its contract code otherwise, the code resolved by month to the
schedule's rows or the dates split at month ends, every component
with the days it covers, its method's observations made once over those days, and for a
financial settlement each component's payment day, since payment-day-date-or-rule.md its row's
date as entered or its row's rule applied to its last observation day instruction by instruction
on the payment calendar, since #181. Then the kernel:
resolved_trades checks the first profile's rules and encoded turns the terms and the observations
into arrays, and the batch holds both. Nothing here reads a history, a price or a valuation date.
docs/library/trades/create-trades.md is the page."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any, Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from catalyst.cashflows.rules import finite_amounts
from catalyst.globals.discount_curve import curve_name
from catalyst.globals.unit_conversions import UnitConversions
from catalyst.index_definitions.contract_codes import month_label, schedule_months
from catalyst.index_definitions.date_offsets import shift_days
from catalyst.index_definitions.futures_schedule import FuturesSchedule
from catalyst.index_definitions.holiday_calendar import HolidayCalendar
from catalyst.index_definitions.holiday_calendars import (
    KEYS_BOUND,
    HolidayCalendars,
    keyed_calendar,
    no_collection,
)
from catalyst.index_definitions.index import Index
from catalyst.index_definitions.published_schedule import PublishedSchedule
from catalyst.index_definitions.sheet_days import SHEET_FIRST_DAY, SHEET_LAST_DAY
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.instruments.definitions import FIXED_FLOAT, FLOAT_FLOAT, FieldType
from catalyst.instruments.fields import DatesOrTexts, FieldValues
from catalyst.trades.encoding import Encoded, encoded
from catalyst.trades.observations import Observations, observed
from catalyst.trades.schedule_methods import METHODS
from catalyst.trades.template import (
    DayOrRule,
    TradeTemplate,
    months_of,
    payment_rule_of,
    price_unit_of,
    quantity_per_of,
    route_of,
    schedule_method_of,
    settlement_frequency_of,
    settlement_of,
)
from catalyst.trades.terms import (
    BASES,
    FREQUENCIES,
    LegInputs,
    PaymentTerms,
    PriceUnit,
    ResolvedTrades,
    Route,
    Settlement,
    SettlementFrequency,
    TradeSchedule,
    frequency_rules,
    marketing_reserves,
    month_bounds,
    named_trade,
    payments_after_observations,
    price_words,
    reporting_lot_of,
    resolved_trades,
    spread_legs,
    spread_pair,
    spread_rules,
    trade_schedule_of,
    whole_nearbys,
    whole_trade_ids,
)

RESOLVED_OCCURRENCES = "resolved_occurrences"  # ticket rows completed and typed
RESOLVED_COMPONENTS = "resolved_components"  # contract months resolved to schedule rows
PAYMENT_RULES_READ = "payment_rules_read"  # distinct payment rules read, since #181; none for
# a row that entered a date, since payment-day-date-or-rule.md
PAYMENT_SHIFTS = "payment_shifts"  # instructions applied, each over one rule's components
# on one calendar, since #181
SCHEDULE_CODES_READ = "schedule_codes_read"  # codes of the index's schedule read for their month
# Distinct codes of the rows that book by code, read for their months, since #172: a row that
# books by its dates has its code, if any, read for nothing and counted here for nothing.
TICKET_CODES_READ = "ticket_codes_read"
PERIOD_FIELDS: Final = ("contract_code", "start_date", "end_date")
# The second leg's two fields, since two-index-fixed-float.md, present exactly with two indexes.
# The field a second leg adds, since two-index-one-price.md the one: the second index's method;
# the fixed price is the trade's, entered once.
SECOND_LEG_FIELDS: Final = ("second_schedule_method",)

# The conditions of the fixed_float's required_when fields, as library rules: the field, the batch
# fact it depends on and the value that fact must have, rendered as the definition shows them,
# `route = cleared`; a field is present exactly when its condition holds.
CONDITIONS: Final[dict[str, tuple[str, Route | Settlement]]] = {
    "clearing_house": ("route", Route.CLEARED),
    "counterparty": ("route", Route.BILATERAL),  # since #175
    "discount_curve_key": ("route", Route.BILATERAL),  # named-curves-slice-3.md
    "payment_day": ("settlement_method", Settlement.FINANCIAL),  # payment-day-date-or-rule.md
    "payment_holiday_key": ("settlement_method", Settlement.FINANCIAL),  # payment-calendar-keys.md
}


@dataclass(frozen=True, slots=True)
class Trades:
    """A batch of trades as _CreateTrades publishes it: the resolved terms and their encoding, the
    encoding holding the terms by reference as well, so each fact is kept once and the two
    sections are read together or apart; and since #172 what each row entered for its
    contract_code, as the seam carries a field some rows leave unsupplied: code_entered, per
    occurrence whether the row entered one, from the ticket's cell or the template's value, and
    entered_codes, the texts of the rows that did, in row order, as typed, both owned and the
    mask read-only; kept apart from the contracts the components resolved to, so that a reader
    tells a label a row booked by from one its dates overrode, and read by nothing that prices.
    Nothing of a market, a history or a valuation date is
    here; preparation and evaluation make their own records over this one."""

    resolved: ResolvedTrades
    encoded: Encoded
    code_entered: NDArray[np.bool_]
    entered_codes: tuple[str, ...]


def trades(
    indexes: Sequence[Index],
    ticket: FieldValues,
    template: TradeTemplate,
    units: UnitConversions,
    counter: WorkCounter,
    calendars: HolidayCalendars | None = None,
) -> Trades:
    """The one way to make Trades: resolution, which makes each leg's schedule methods'
    observations on the way to the payment days, one index or since two-index-fixed-float.md
    two, then encoding over the terms and those observations, the unit tables and the counter
    passed in and never looked up; a failure in any publishes nothing."""
    terms, observations, entered = resolved(indexes, ticket, template, counter, calendars)
    return Trades(terms, encoded(terms, observations, units, counter), *entered)


def resolved(
    indexes: Sequence[Index],
    ticket: FieldValues,
    template: TradeTemplate,
    counter: WorkCounter,
    calendars: HolidayCalendars | None = None,
) -> tuple[ResolvedTrades, tuple[Observations, ...], tuple[NDArray[np.bool_], tuple[str, ...]]]:
    """The resolution child: the terms of a batch from a template and a ticket, checked in this
    order, the first failure being the message, and then the kernel's own rules; with them the
    observations the schedule method gave the components, one Observations per leg, made once
    here and handed on to the encoding, since the payment days count from them, and what the
    rows entered for their codes, the rows that entered one and their texts.

    The ticket is bound against the template's instrument, the fixed_float or since
    float-float-spread.md the float_float, the two whose trades are built. No field is supplied
    by both, even to the same value. Every required field is present
    in one of them. The route and the settlement are one each, the template's value or a column
    every row agrees on; the quantity unit, the method and the basis are each row's own, the
    template's value for every row or the ticket's column, so that one batch mixes them row by
    row, each distinct text read once for its meaning in the order its first row comes: the
    quantity unit by name among the index's specifications, exactly as the index names them,
    the method and the basis from their lists, the route and the settlement likewise, each named
    with its row where the ticket supplied it, since the page promises a ticket's field its row,
    the unit, the method, the route, the settlement and the basis in that order. Each conditional
    field is present exactly when its
    condition holds, a clearing house with a cleared route, since #175 a counterparty with a
    bilateral one, and the two payment fields with a financial settlement, and absent otherwise,
    since a label for a clearing house a bilateral trade has not, a counterparty a cleared trade
    faces through its clearing house, or a payment a physical contract never makes, would say
    something false. Since #175 a marketing reserve may stand in either, a finite amount of zero
    or more per row, the template's one value booked once by every row or the ticket's column,
    the first bad row named, and none at all when neither supplies the field. The
    trade IDs, since #168, are whole numbers of at most 15 digits, the template's one read when
    the template was made and the ticket's column read here, the first bad row named. The
    index is a futures index or a published index, a Gas Daily one refused by name,
    made with a reporting lot, the specification the batch's delta is counted in lots of, and
    every code of its schedule is read for its month, the rows the
    ticket does not use included, a label that is no contract code and two rows for one month
    refused by row. Each row's period is its own since #172, chosen from the three period fields
    as the row holds them, the template's value or the ticket's cell: a blank or an empty cell
    supplies nothing, so a row holds a field exactly when a value stands in it. Both dates
    supplied, the row books the days between them, whatever code stands beside them, the code
    kept as entered text and read for nothing; neither supplied, the row books its contract
    code; one date without the other, or no code and no pair, is refused by the first such row
    from the top, naming the field and the row, unless no period field stands in the template
    or the ticket at all, which is refused by name before any row is read, at the code's place
    in the definition's order. Each code of a row that books by it is read once per distinct
    text, in the order the sheet first shows each among those rows, so that the first row that
    breaks the grammar is the one named, by its own row, through the period grammar, in either
    case, for the months it spans; a code beside both dates is never read, so a label the
    grammar refuses stands there. Each pair of dates, an end before its start refused by row,
    gives the months from the start's to the end's; and each month is resolved to its schedule
    row, a month the schedule lacks refused by the row and the month, in the words of the form
    the row booked by. A period makes one component per month, in order, all on the one
    occurrence, the components in row order whichever form each row took, each covering its
    month's days, weekends and
    holidays included: the whole month from a code, and from dates the whole month too but for
    the first and the last, which start and end on the dates given, so 12 November to
    31 December is X26 over 12 to 30 November and Z26 over the whole of December; what a
    quantity per calendar day multiplies, and what the schedule method prices over. No calendar
    moves the days. Which rows entered a code, and the texts they entered, are kept beside the
    batch and apart from the contracts its components resolved to.
    The schedule method gives each component its observation days, the expiry under lastday, the
    business day before it under penultimate, the expiry and the two business days before it
    under last3day, a third each, the three refusing a component that covers a part of its
    month by its contract, its trade and its days, and every pricing day of the days it covers
    under asian, an equal share each, a partial month's share of them, a part with none refused
    the same way; on a published index the prints its period covers under asian, an equal
    share each, or under lastday the one print of a whole month that has one, the first row
    of another method refused by its method and row.
    For a financial settlement, since payment-day-date-or-rule.md each row's payment_day is a
    date or a rule: a date is the row's one payment day, every component of the row paying on it
    as entered, the first row whose date is on or before the row's last observation refused by
    its trade, its date and that day; a rule is read once per distinct text and each component
    pays that many business days strictly after its anchor, its last observation day on every
    index, counted on its occurrence's payment calendar with Monday to Friday eligible, that day
    itself rolled back first so that a day the payment calendar closes is not counted; the rule
    of the four methods.
    Two indexes, since two-index-fixed-float.md, make two legs of the same rows. The indexes are
    one or two, else refused by their number, before anything else. second_schedule_method is
    present exactly with two, checked here where the index count is known and by no template,
    refused by its name, missing with two and present with one; since two-index-one-price.md
    the one fixed_price is the trade's, the outright price of the deal, and no second price
    exists. The second leg follows the first's rules on its own index, the first leg's steps as they
    were: the quantity unit names one of its specifications, exactly; its methods are read
    from the list; every code of its schedule is read for its month; each row's months are
    resolved against its schedule, a month a schedule lacks refused by the index and the month,
    each leg's refusals naming its index; its observations are its own methods' over the same
    days; and the payment anchor is the later of the two legs' last observation days, so one
    rule finds one day both legs pay on, a date standing after both. The pair's rules, two
    distinct indexes of distinct names, one quote currency, quote quantity and settlement
    currency unit, and a financial settlement, are the kernel's.

    A float_float template, since float-float-spread.md, books the first index's price less the
    second's against its one spread_price, the field read where a fixed_float's fixed_price is.
    The kernel's rules for it are applied here as well, each before the step that would
    otherwise refuse it in other words: two indexes, before a leg's field is read, and the
    bilateral route with no named broker, before a conditional field is. Since
    float-float-units.md the spread's pair rules over the two indexes' conventions, spread_pair,
    are applied with the first, so that an energy index beside a volume one is refused as two
    measures and never as a quantity unit the second index does not define; and its spread
    price's unit is two fields of the batch,
    spread_price_currency_unit and spread_price_quantity_unit, required as any required field
    is and one each as the route is, the template's value or a column every row agrees on,
    handed to the kernel as given and read for their meaning by the encoding, which has the
    unit tables.

    A fixed_float's fixed price takes a unit of its own since #273, fixed_price_unit, optional
    and each row's own: the template's one text or the ticket's column, each distinct text read
    once for its form, a currency unit and a quantity unit joined by one slash, the first row
    from the top that breaks it named, and handed to the kernel as the batch's distinct units
    with each row's place among them. Left out of both, nothing is handed and the kernel takes
    the unit the index quotes in. What the two codes mean is the encoding's to read, as a
    spread price's are.

    Then the kernel's rules, through resolved_trades: whole quantities, zero included, and finite
    prices, each named by its trade, a financial settlement with penultimate, last3day and asian,
    the first row of them named under a physical one, and each component's quantity formed once
    by the basis, the entered quantity times its covered days under calday.

    Work: one occurrence per ticket row, one component per contract month, one schedule code
    per row of each leg's schedule and since #172 one ticket code per distinct code of the rows
    that book by code, none for a row that books by its dates, reported to the counter.
    """
    if not 1 <= len(indexes) <= 2:
        raise ValueError(
            f"indexes are {len(indexes)}, expected one or two; a batch is on one index or, since "
            "two-index-fixed-float.md, on a pair"
        )
    index = indexes[0]
    paired = len(indexes) == 2
    fields = _fields(template, ticket)
    spread = template.instrument is FLOAT_FLOAT
    if spread:
        spread_legs(len(indexes))
        spread_pair(index, indexes[1])
    _the_required(fields)
    specifications, by_unit = _each_distinct(
        fields, "quantity_unit", partial(_the_specification, index, owner=_owner(index, paired))
    )
    methods, by_method = _each_distinct(fields, "schedule_method", schedule_method_of)
    route = route_of(fields.where("route", 0), fields.one_text("route"))
    settlement = settlement_of(
        fields.where("settlement_method", 0), fields.one_text("settlement_method")
    )
    bases, by_basis = _each_distinct(fields, "quantity_per", quantity_per_of)
    frequencies, by_frequency = _each_distinct(
        fields, "settlement_frequency", settlement_frequency_of
    )
    price_units, price_unit = None, None
    if spread:
        # The trade IDs are read for a refusal's words alone, so only where a row is refused.
        spread_rules(
            route, fields.labels("broker"), lambda i: named_trade(fields.ids("trade_id"), i)
        )
        price_units = (
            PriceUnit(
                fields.one_text("spread_price_currency_unit"),
                fields.one_text("spread_price_quantity_unit"),
            ),
        )
    elif fields.has("fixed_price_unit"):
        # Each row's own since #273, the template's one or the ticket's column, each distinct
        # text read once for its form; left out of both, the kernel takes the index's unit.
        read_units, price_unit = _each_distinct(fields, "fixed_price_unit", price_unit_of)
        price_units = tuple(read_units)
    _the_conditions(fields, route, settlement)
    _the_leg_fields(fields, paired)
    specification = np.array(specifications, dtype=np.intp)[by_unit]
    schedule_method = np.array([METHODS.index(m) for m in methods], dtype=np.intp)[by_method]
    quantity_per = np.array([BASES.index(b) for b in bases], dtype=np.intp)[by_basis]
    settlement_frequency = np.array([FREQUENCIES.index(f) for f in frequencies], dtype=np.intp)[
        by_frequency
    ]
    trade_ids = fields.ids("trade_id")
    # The kernel's rule over the frequencies, applied here before any period is built or observed,
    # since onetime-averaging.md, so that a onetime row the terms would refuse is refused in the
    # rule's own words and never in an observation's.
    frequency_rules(
        settlement_frequency,
        quantity_per,
        schedule_method,
        settlement,
        index.kind,
        paired,
        partial(named_trade, trade_ids),
    )
    onetime_rows = settlement_frequency == FREQUENCIES.index(SettlementFrequency.ONETIME)
    schedule = trade_schedule_of(index)
    reporting_lot_of(index)
    months = schedule_months(schedule)
    counter.hit(SCHEDULE_CODES_READ, len(schedule.codes))
    schedules = [(months, _schedule_of(index, paired))]
    second = None
    if paired:
        second = _the_second_schedule(indexes[1], counter)
        schedules.append((second[1], _schedule_of(indexes[1], True)))
    periods = _the_periods(fields, tuple(schedules), onetime_rows, contract_days(schedule))
    counter.hit(TICKET_CODES_READ, periods.codes_read)
    occurrence = periods.occurrence
    start, end = periods.start, periods.end
    contract = periods.contracts[0]

    def booked(k: int) -> str:
        """What a component is booked under, in an observation's refusal: its contract's code,
        or `the window` for a onetime component, whose two dates the refusal states itself."""
        return "the window" if periods.window[k] else schedule.codes[int(contract[k])]

    observations = observed(
        schedule_method[occurrence],
        index,
        contract,
        start,
        end,
        lambda k: named_trade(trade_ids, int(occurrence[k])),
        booked=booked,
        dated=periods.dated,
    )
    # One anchor for every index since iferc-publication-payment-anchor.md, each component's
    # last observation day, the expiry under lastday on a futures index and the last
    # publication date on a published one, handed over as a temporary, not held across the
    # kernel's copies below; with two legs the later of the two, the one day both pay from.
    legs: tuple[Observations, ...] = (observations,)
    second_leg = None
    if second is not None:
        second_leg, second_observations = _the_second_leg(
            second[0],
            fields,
            periods.contracts[1],
            occurrence,
            start,
            end,
            trade_ids,
            second[1],
            periods.dated,
        )
        legs = (observations, second_observations)
    payment = _the_payments(settlement, fields, legs, occurrence, trade_ids, counter, calendars)
    counter.hit(RESOLVED_OCCURRENCES, fields.rows)
    counter.hit(RESOLVED_COMPONENTS, int(occurrence.size))
    terms = resolved_trades(
        template.instrument,
        index,
        specification,
        route,
        settlement,
        schedule_method,
        quantity_per,
        settlement_frequency,
        fields.nearbys("nearby"),
        trade_ids,
        fields.labels("clearing_house"),
        fields.labels("broker"),
        fields.dates("trade_date"),
        occurrence,
        contract,
        fields.numbers("quantity")[occurrence],
        start,
        end,
        fields.numbers(price_words(template.instrument)[0])[occurrence],
        payment,
        counterparty=fields.labels("counterparty"),
        marketing_reserve=fields.amounts("marketing_reserve", marketing_reserves),
        cva_reserve=fields.amounts("cva_reserve", finite_amounts),  # signed, cva-reserve.md
        discount_curve_key=fields.keys("discount_curve_key"),
        payment_holiday_key=fields.labels("payment_holiday_key"),  # bound above, kept to show
        schedule_month=months,
        second_leg=second_leg,
        price_units=price_units,
        price_unit=price_unit,
    )
    return terms, legs, periods.entered


# --- the fields of the batch, each from the template or the ticket --------------------------


@dataclass(frozen=True, slots=True)
class _Fields:
    """Every field of the batch read from whichever of the two supplied it: the template's one
    value, the same for every occurrence, or the ticket's column, one per occurrence."""

    template: TradeTemplate
    ticket: FieldValues

    @property
    def rows(self) -> int:
        return self.ticket.rows

    def has(self, name: str) -> bool:
        """Whether either names the field: the template owns every field its row named, a period
        field whose cell held nothing included, since #172, and the ticket every column."""
        return name in self.template.names or self.ticket.has(name)

    def where(self, name: str, row: int) -> str:
        """A field named in a message: with the row when the ticket supplied it, since each row
        has its own value, and alone when the template did, since every row has the same."""
        if name in self.template.names:
            return name
        return f"{name} row {row + 1}"

    def period_texts(self, name: str) -> tuple[NDArray[np.bool_], tuple[str, ...]]:
        """A period field's texts and which rows supplied them, since #172: the template's one
        value on every row, or on none when its cell held nothing; the ticket's column over the
        rows whose cells held a value, in row order; or nothing from either."""
        if name in self.template.names:
            if name in self.template.defaults:
                text = cast(str, self.template.defaults[name])
                return np.ones(self.rows, dtype=bool), (text,) * self.rows
            return np.zeros(self.rows, dtype=bool), ()
        if self.ticket.has(name):
            return self.ticket.supplied_rows(name), self.ticket.texts(name)
        return np.zeros(self.rows, dtype=bool), ()

    def period_dates(self, name: str) -> tuple[NDArray[np.bool_], NDArray[np.datetime64]]:
        """A period field's days and which rows supplied them, as period_texts gives texts."""
        if name in self.template.names:
            if name in self.template.defaults:
                day = cast(np.datetime64, self.template.defaults[name])
                return np.ones(self.rows, dtype=bool), np.full(
                    self.rows, day, dtype="datetime64[D]"
                )
            return np.zeros(self.rows, dtype=bool), np.empty(0, dtype="datetime64[D]")
        if self.ticket.has(name):
            return self.ticket.supplied_rows(name), self.ticket.dates(name)
        return np.zeros(self.rows, dtype=bool), np.empty(0, dtype="datetime64[D]")

    def one_text(self, name: str) -> str:
        """A batch field's one text: the template's, or the ticket's column when every row holds
        the same text, else the first row that differs from the first is named."""
        if name in self.template.defaults:
            return cast(str, self.template.defaults[name])
        texts = self.ticket.texts(name)
        if len(set(texts)) > 1:
            first = texts[0]
            i = next(i for i, text in enumerate(texts) if text != first)
            raise ValueError(
                f"{name} row {i + 1} is {texts[i]!r}, expected {first!r} as at row 1; "
                f"a batch has one {name}"
            )
        return texts[0]

    def texts(self, name: str) -> tuple[str, ...]:
        if name in self.template.defaults:
            return (cast(str, self.template.defaults[name]),) * self.rows
        return self.ticket.texts(name)

    def labels(self, name: str) -> tuple[str, ...] | None:
        """A label field per occurrence, or None when neither supplied it."""
        return self.texts(name) if self.has(name) else None

    def keys(self, name: str) -> tuple[str, ...] | None:
        """The curve keys per occurrence, since named-curves-slice-3.md, each read by the curve's
        own name rule, or None when neither supplied them: the template's one, read when the
        template was made and repeated here, or the ticket's column read now, the first bad row
        named by the field and the row."""
        if not self.has(name):
            return None
        if name in self.template.defaults:
            return (cast(str, self.template.defaults[name]),) * self.rows
        return tuple(
            [
                curve_name(self.where(name, k), text)
                for k, text in enumerate(self.ticket.texts(name))
            ]
        )

    def ids(self, name: str) -> NDArray[np.int64] | None:
        """The trade IDs per occurrence, whole numbers of at most 15 digits since #168, or None when
        neither supplied them: the template's one, read for the rule when the template was made
        and repeated here, or the ticket's column read for it now, the first bad row named by the
        field and the row."""
        if not self.has(name):
            return None
        if name in self.template.defaults:
            return np.full(self.rows, cast(int, self.template.defaults[name]), dtype=np.int64)
        return whole_trade_ids(self.ticket.numbers(name), lambda k: self.where(name, k))

    def nearbys(self, name: str) -> NDArray[np.intp]:
        """The nearbys per occurrence, whole numbers of 1 or more since nearby-selection.md:
        the template's one, read for the rule when the template was made and repeated here, or
        the ticket's column read for it now, the first bad row named by the field and the
        row. Required, so one of the two holds it."""
        if name in self.template.defaults:
            return np.full(self.rows, cast(int, self.template.defaults[name]), dtype=np.intp)
        return whole_nearbys(self.ticket.numbers(name), lambda k: self.where(name, k))

    def amounts(
        self, name: str, rule: Callable[[NDArray[np.float64], Callable[[int], str]], object]
    ) -> NDArray[np.float64] | None:
        """An entered reserve's amounts per occurrence, the marketing reserve's finite amounts of
        zero or more since #175 and the CVA reserve's finite amounts of either sign since
        cva-reserve.md, each by the rule its caller hands over, or None when neither supplied
        them: the template's one, read for the rule when the template was made and repeated
        here, or the ticket's column read for it now, the first bad row named by the field and
        the row."""
        if not self.has(name):
            return None
        if name in self.template.defaults:
            return np.full(self.rows, cast(float, self.template.defaults[name]))
        numbers = self.ticket.numbers(name)
        rule(numbers, lambda k: self.where(name, k))
        return numbers

    def numbers(self, name: str) -> NDArray[np.float64]:
        if name in self.template.defaults:
            return np.full(self.rows, cast(float, self.template.defaults[name]))
        return self.ticket.numbers(name)

    def dates(self, name: str) -> NDArray[np.datetime64]:
        if name in self.template.defaults:
            return np.full(self.rows, self.template.defaults[name], dtype="datetime64[D]")
        return self.ticket.dates(name)

    def days_or_rules(self, name: str) -> DatesOrTexts:
        """A field of a date or a rule text per occurrence, since payment-day-date-or-rule.md, the
        two told apart once by the seam and never read for which they are: the template's one
        value on every row, its day or its rule, or the ticket's column as the seam typed it,
        the dates of the dated rows and the texts of the rest each in row order."""
        if name in self.template.defaults:
            entry = cast(DayOrRule, self.template.defaults[name])
            if entry.day is not None:
                return DatesOrTexts.of_dates(np.full(self.rows, entry.day, dtype="datetime64[D]"))
            return DatesOrTexts.of_texts((cast(str, entry.rule),) * self.rows)
        return self.ticket.dates_or_texts(name)

    def shown(self, name: str) -> str:
        """A field's value as a message shows it, the first row's from the ticket: text quoted,
        a number or a day as it is, an object as the words of its kind."""
        match self.ticket.field(name).type:
            case FieldType.TEXT | FieldType.CODE:
                return repr(self.texts(name)[0])
            case FieldType.NUMBER:
                return repr(float(self.numbers(name)[0]))
            case FieldType.DATE:
                return str(self.dates(name)[0])
            case FieldType.DATE_OR_TEXT:
                entered = self.days_or_rules(name)
                return str(entered.dates[0]) if entered.is_date[0] else repr(entered.texts[0])
            case _:
                assert_never(self.ticket.field(name).type)


def _fields(template: TradeTemplate, ticket: FieldValues) -> _Fields:
    """The template's instrument one whose trades are built, the fixed_float or since
    float-float-spread.md the float_float, the ticket bound against it, and the two disjoint."""
    if template.instrument is not FIXED_FLOAT and template.instrument is not FLOAT_FLOAT:
        raise ValueError(
            f"template is of instrument {template.instrument.name!r}, expected "
            f"{FIXED_FLOAT.name} or {FLOAT_FLOAT.name}, the instruments whose trades are built"
        )
    if ticket.instrument is not template.instrument:
        raise ValueError(
            f"ticket is of instrument {ticket.instrument.name!r}, expected the template's, "
            f"{template.instrument.name!r}"
        )
    for name in ticket.names:
        if name in template.names:
            raise ValueError(
                f"{name} is supplied by the template and by the ticket, expected by one of them"
            )
    return _Fields(template, ticket)


def _the_required(fields: _Fields) -> None:
    """Every field the definition always requires, present in one of the two, in the definition's
    order; at the contract code's place some period field, a code or a date, named by either,
    since the code was the required field before the dates could stand in for it: which rows
    hold which, and whether each holds a whole period, is the periods' own rule since #172."""
    for field in fields.template.instrument.fields:
        if field.name == "contract_code":
            if not any(fields.has(name) for name in PERIOD_FIELDS):
                raise ValueError(
                    "contract_code is missing, expected a value in the template or a column in "
                    "the ticket, or start_date and end_date in its place"
                )
        elif field.required and not fields.has(field.name):
            raise ValueError(
                f"{field.name} is missing, expected a value in the template or a column in the "
                "ticket"
            )


def _the_conditions(fields: _Fields, route: Route, settlement: Settlement) -> None:
    """Each conditional field present exactly when its condition holds of the batch."""
    facts: dict[str, Route | Settlement] = {"route": route, "settlement_method": settlement}
    for name, (fact, value) in CONDITIONS.items():
        condition = f"{fact} = {value.value}"
        if facts[fact] is value:
            if not fields.has(name):
                raise ValueError(f"{name} is missing, expected it when {condition}")
        elif fields.has(name):
            raise ValueError(f"{name} is {fields.shown(name)}, expected none unless {condition}")


def _the_specification(
    index: Index, where: str, name: str, owner: str = "the index's specifications"
) -> int:
    """The row of the index's specifications the quantity unit names, exactly: no trimming, no
    case folding, no alias and no first row taken for want of a match, the index's names being
    the choices, so a unit the tables know but the index does not define is refused like any
    other text; the specifications named as the owner words them, by the index's name with
    two indexes."""
    names = index.specifications.names
    if name not in names:
        choices = ", ".join(repr(each) for each in names)
        raise ValueError(f"{where} is {name!r}, expected one of {owner}: {choices}")
    return names.index(name)


# --- the contracts: every schedule code read, each ticket code resolved by month -------------


def _distinct_texts[T](
    texts: NDArray[Any],
    rows: NDArray[np.intp] | None,
    where: Callable[[int], str],
    read: Callable[[str, str], T],
) -> tuple[list[T], NDArray[np.intp]]:
    """A field's texts, over every row or over the rows given, read once per distinct text, the
    first row holding each named in a refusal by its own number, and the position of each text
    among the distinct ones. The texts are read in the order their first rows come, not the
    order they sort in, so the first row from the top that breaks the grammar is the one named;
    the values are kept in the sorted order the positions index."""
    distinct, first_rows, inverse = np.unique(texts, return_index=True, return_inverse=True)
    by_row = np.argsort(first_rows)  # the distinct texts in the order their first rows come
    read_values: dict[int, T] = {}
    for i in by_row:
        row = int(first_rows[i]) if rows is None else int(rows[first_rows[i]])
        read_values[int(i)] = read(where(row), str(distinct[i]))
    return [read_values[i] for i in range(distinct.size)], inverse.astype(np.intp)


def _each_distinct[T](
    fields: _Fields, name: str, read: Callable[[str, str], T]
) -> tuple[list[T], NDArray[np.intp]]:
    """A text field of every row read once per distinct text, each occurrence's position among
    the distinct texts beside the values."""
    return _distinct_texts(
        np.array(fields.texts(name)), None, lambda i: fields.where(name, i), read
    )


@dataclass(frozen=True, slots=True)
class RowPeriods:
    """What the rows' periods resolved to, a booking's and since dated-quotes.md a request's: per
    component its occurrence, its schedule row on each
    leg's schedule, one array per leg in leg order, a monthly component's the row of its month
    and a onetime component's the row of the contract pricing its first day, the first and the
    last day it covers, since onetime-averaging.md whether it is a onetime row's window, and
    whether its row entered two dates and not a code, which a published index selects its
    prints by, aligned; which rows entered a code, a read-only mask the batch owns, with the
    texts they entered in row order; and how many distinct codes were read for their months."""

    occurrence: NDArray[np.intp]
    contracts: tuple[NDArray[np.intp], ...]
    start: NDArray[np.datetime64]
    end: NDArray[np.datetime64]
    window: NDArray[np.bool_]
    dated: NDArray[np.bool_]
    entered: tuple[NDArray[np.bool_], tuple[str, ...]]
    codes_read: int


def _the_periods(
    fields: _Fields,
    schedules: tuple[tuple[NDArray[np.int64], str], ...],
    onetime_rows: NDArray[np.bool_],
    contract_day: NDArray[np.datetime64],
) -> RowPeriods:
    """The batch's rows' periods, resolve_periods over the three period fields as the template or
    the ticket supplied them, each named with its row where the ticket did."""
    code_on, codes = fields.period_texts("contract_code")
    start_on, starts = fields.period_dates("start_date")
    end_on, ends = fields.period_dates("end_date")
    return resolve_periods(
        code_on,
        codes,
        start_on,
        starts,
        end_on,
        ends,
        fields.where,
        onetime_rows,
        schedules,
        contract_day,
    )


def resolve_periods(
    code_on: NDArray[np.bool_],
    codes: tuple[str, ...],
    start_on: NDArray[np.bool_],
    starts: NDArray[np.datetime64],
    end_on: NDArray[np.bool_],
    ends: NDArray[np.datetime64],
    where: Callable[[str, int], str],
    onetime_rows: NDArray[np.bool_],
    schedules: tuple[tuple[NDArray[np.int64], str], ...],
    contract_day: NDArray[np.datetime64],
) -> RowPeriods:
    """Each row's period chosen row by row and resolved to its components, one per calendar month
    it covers, or since onetime-averaging.md one for the whole of it where the row is onetime, in
    one pass over the components, since #172; the rows of a booking and since dated-quotes.md the
    rows of a request for quote alike, each field named in a refusal by `where`, the field and the
    row. code_on, start_on and end_on say which rows supplied each of the three period fields,
    and codes, starts and ends hold the values of those rows alone, in row order. A row with both
    dates books the days between them, a code beside them kept as entered text and never read; a
    row with neither books its code; a row with one date and not the other, or with no code and
    no pair, is refused, the first such row from the top, once every row's three fields are known
    and before any code is read. The dated rows' ends are held on or after their starts, by row.
    The codes of the rows that book by code are read once per distinct text, in the order their
    first rows come, so the first row from the top that breaks the grammar is the one named;
    then each row's first month and the month after its last, from the code's span or the
    dates' months, the components in row order whichever form each row took, each month looked
    up in each leg's schedule, the schedules' months given with the words a refusal names each
    schedule by, a month without a contract refused by the row and the month, the first leg's
    schedule first, and each component's days its month's, a dated row's first and last clipped
    to its dates. A onetime row is one component whatever months it spans, its days the whole
    window, a dated row's two dates or a code's first day to its last, and its schedule row the
    contract pricing its first day, the first whose day, contract_day, the first leg's expiries,
    is on or after it by the calendar's rule, one search over the windows and no month looked up,
    since a window may open in a month the schedule has no contract for while every day of it
    prices, since onetime-averaging.md and the review of its third slice. The month bounds are one
    conversion each over the components, the clipping one maximum and one minimum over the dated
    components, and the days are the kernel's to count."""
    rows = code_on.size
    dated = start_on & end_on
    faulty = (start_on ^ end_on) | ~(dated | code_on)
    if faulty.any():
        i = int(faulty.argmax())
        if start_on[i] == end_on[i]:
            raise ValueError(
                f"row {i + 1} has no period, expected a contract_code or start_date with end_date "
                "on each row; contract_code, start_date and end_date are not supplied"
            )
        given, other, on, values = (
            ("start_date", "end_date", start_on, starts)
            if start_on[i]
            else ("end_date", "start_date", end_on, ends)
        )
        raise ValueError(
            f"{where(given, i)} is {values[int(np.count_nonzero(on[:i]))]} without "
            f"{where(other, i)}, expected both dates, the period's first and last day, or "
            "neither and a contract_code"
        )
    # Each row's place among the rows that supplied a field, where that field's values are.
    rank_start = np.cumsum(start_on) - 1
    rank_end = np.cumsum(end_on) - 1
    rank_code = np.cumsum(code_on) - 1
    rank_dated = np.cumsum(dated) - 1
    dated_rows = np.flatnonzero(dated)
    dated_starts = starts[rank_start[dated_rows]]
    dated_ends = ends[rank_end[dated_rows]]
    backwards = dated_ends < dated_starts
    if backwards.any():
        k = int(backwards.argmax())
        i = int(dated_rows[k])
        raise ValueError(
            f"{where('end_date', i)} is {dated_ends[k]}, expected a day on or after "
            f"{where('start_date', i)}, {dated_starts[k]}"
        )
    coded_rows = np.flatnonzero(~dated)  # each supplies a code, the rule above having passed
    coded_texts = np.array(codes, dtype=object)[rank_code[coded_rows]]
    spans, inverse = _distinct_texts(
        coded_texts, coded_rows, lambda i: where("contract_code", i), months_of
    )
    bounds = np.array(spans, dtype=np.int64).reshape(-1, 2)[inverse]
    first = np.empty(rows, dtype=np.int64)
    after = np.empty(rows, dtype=np.int64)
    first[coded_rows], after[coded_rows] = bounds[:, 0], bounds[:, 1]
    first[dated_rows] = dated_starts.astype("datetime64[M]").astype(np.int64)
    after[dated_rows] = dated_ends.astype("datetime64[M]").astype(np.int64) + 1
    count = np.where(onetime_rows, 1, after - first)  # a onetime row one component, its window
    occurrence = np.repeat(np.arange(rows, dtype=np.intp), count)
    offsets = np.cumsum(count) - count
    month = first[occurrence] + (np.arange(occurrence.size) - offsets[occurrence])

    def period_of(i: int) -> str:
        """A row's period as a refusal names it: its two dates, or the code it books by."""
        if dated[i]:
            k = int(rank_dated[i])
            return (
                f"{where('start_date', i)} is {dated_starts[k]} and "
                f"{where('end_date', i)} {dated_ends[k]}"
            )
        return f"{where('contract_code', i)} is {codes[int(rank_code[i])]!r}"

    start, end = month_bounds(month)
    window = onetime_rows[occurrence]  # a onetime component runs to its row's last month's end
    windows = bool(window.any())
    if windows:
        _, span_end = month_bounds(after[occurrence[window]] - 1)
        end[window] = span_end
    on = dated[occurrence]  # the dated rows' components, clipped to their rows' dates
    if on.any():
        k = rank_dated[occurrence[on]]
        start[on] = np.maximum(start[on], dated_starts[k])
        end[on] = np.minimum(end[on], dated_ends[k])
    contracts = tuple(
        [
            _the_contracts(
                months,
                month,
                occurrence,
                period_of,
                words,
                window if windows else None,
                contract_day,
                start,
            )
            for months, words in schedules
        ]
    )
    entered = np.array(code_on, dtype=bool)  # the batch's own copy of which rows entered a code
    entered.setflags(write=False)
    return RowPeriods(occurrence, contracts, start, end, window, on, (entered, codes), len(spans))


def contract_days(schedule: TradeSchedule) -> NDArray[np.datetime64]:
    """The day each contract of the schedule prices on last: a futures contract's expiry, a
    published month's last publication date; what a onetime window's contract is found by, since
    the review of onetime-averaging.md's third slice, the first contract pricing on or after the
    window's first day, as the calendar gives a day its contract, window_rows' search key for a
    booking and since dated-quotes.md for a quote. A published schedule's days are never
    searched, a onetime window on a published index being refused by the frequency's rules
    first."""
    match schedule:
        case FuturesSchedule():
            return schedule.future_expiry
        case PublishedSchedule():
            # The date of each month's last print, one search of the column that says each
            # print's month; never searched in turn, a onetime window on a published index
            # being refused by the frequency's rules first.
            months = np.arange(len(schedule.codes), dtype=np.intp)
            last = np.searchsorted(schedule.contract, months, side="right") - 1
            return schedule.publication_date[last]
        case _:
            assert_never(schedule)


def window_rows(
    contract_day: NDArray[np.datetime64],
    opens: NDArray[np.datetime64],
    named: Callable[[int], str],
    schedule: str = "the index's schedule",
) -> NDArray[np.intp]:
    """Each window's row on the schedule, the contract pricing its first day: the first whose
    day, contract_day, the schedule's expiries or publication days, is on or after the day it
    opens, by the calendar's rule, one search over the windows and no month looked up, since a
    window is bound to no month and may open in a month the schedule has no contract for while
    every day of it prices; the row is read for nothing that prices, the window's two dates
    naming it. A window opening after the last day the schedule's contracts price is refused in
    the words `named` gives it, the schedule named as given. The one search a booking's windows
    and since dated-quotes.md a quote's share."""
    row = np.searchsorted(contract_day, opens)
    late = row >= contract_day.size
    if late.any():
        k = int(late.argmax())
        raise ValueError(
            f"{named(k)}, expected a window priced by the contracts of {schedule}; it opens on "
            f"{opens[k]}, after the last day they price, {contract_day[-1]}"
        )
    return row


def _the_contracts(
    months: NDArray[np.int64],
    month: NDArray[np.int64],
    occurrence: NDArray[np.intp],
    period_of: Callable[[int], str],
    schedule: str,
    window: NDArray[np.bool_] | None,
    contract_day: NDArray[np.datetime64],
    start: NDArray[np.datetime64],
) -> NDArray[np.intp]:
    """Each component's row on one leg's schedule: a monthly component's the row of its calendar
    month, schedule_rows over those components, and since the review of onetime-averaging.md's
    third slice a onetime component's the row of the contract pricing its first day, window_rows
    over the windows, a window opening after the last day the schedule's contracts price refused
    by its row. window is None when no row is a window, the monthly lookup then over every
    component as it was."""
    if window is None:
        return schedule_rows(months, month, occurrence, period_of, schedule)
    monthly = ~window
    contract = np.empty(window.size, dtype=np.intp)
    contract[monthly] = schedule_rows(
        months, month[monthly], occurrence[monthly], period_of, schedule
    )
    windows = occurrence[window]
    contract[window] = window_rows(
        contract_day, start[window], lambda k: period_of(int(windows[k])), schedule
    )
    return contract


def _owner(index: Index, paired: bool) -> str:
    """The words a refusal names an index's specifications by: the index's, or with two indexes
    the index's by name, since a batch on a pair must say whose."""
    return f"the specifications of index {index.name!r}" if paired else "the index's specifications"


def _schedule_of(index: Index, paired: bool) -> str:
    """The words a refusal names an index's schedule by, as _owner names its specifications."""
    return f"the schedule of index {index.name!r}" if paired else "the index's schedule"


def _the_leg_fields(fields: _Fields, paired: bool) -> None:
    """The second leg's field, second_schedule_method, present exactly with two indexes, since
    two-index-fixed-float.md and the one field since two-index-one-price.md, the count the
    creator alone knows: refused by its name, missing with two and present with one."""
    for name in SECOND_LEG_FIELDS:
        if paired and not fields.has(name):
            raise ValueError(f"{name} is missing, expected it with two indexes")
        if not paired and fields.has(name):
            raise ValueError(f"{name} is {fields.shown(name)}, expected none unless two indexes")


def _the_second_schedule(index: Index, counter: WorkCounter) -> tuple[Index, NDArray[np.int64]]:
    """The second index and its schedule's months, since two-index-fixed-float.md, read before
    the rows' periods are resolved against it: a futures or a published index made with a reporting
    lot, every code of its schedule read for its month, reported to the counter."""
    schedule = trade_schedule_of(index)
    reporting_lot_of(index)
    months = schedule_months(schedule)
    counter.hit(SCHEDULE_CODES_READ, len(schedule.codes))
    return index, months


def _the_second_leg(
    index: Index,
    fields: _Fields,
    contract: NDArray[np.intp],
    occurrence: NDArray[np.intp],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
    trade_ids: NDArray[np.int64] | None,
    months: NDArray[np.int64],
    dated: NDArray[np.bool_],
) -> tuple[LegInputs, Observations]:
    """The second leg's inputs and observations, since two-index-fixed-float.md, over the rows
    the first leg resolved and the contract rows the periods resolved on this index's schedule:
    the quantity unit resolved on this index, each distinct text once; second_schedule_method
    read from the list, each distinct text once; and the observations this leg's methods give the
    components over the same days, by code or by dates as the first leg's are, named as the
    first leg's are. No price of its own since
    two-index-one-price.md: the trade's one fixed price is the outright."""
    specifications, by_unit = _each_distinct(
        fields, "quantity_unit", partial(_the_specification, index, owner=_owner(index, True))
    )
    methods, by_method = _each_distinct(fields, "second_schedule_method", schedule_method_of)
    schedule_method = np.array([METHODS.index(m) for m in methods], dtype=np.intp)[by_method]
    observations = observed(
        schedule_method[occurrence],
        index,
        contract,
        start,
        end,
        lambda k: named_trade(trade_ids, int(occurrence[k])),
        "second_schedule_method",
        dated=dated,
    )
    leg = LegInputs(
        index, np.array(specifications, dtype=np.intp)[by_unit], schedule_method, contract, months
    )
    return leg, observations


def _the_payments(
    settlement: Settlement,
    fields: _Fields,
    legs: tuple[Observations, ...],
    occurrence: NDArray[np.intp],
    trade_ids: NDArray[np.int64] | None,
    counter: WorkCounter,
    collection: HolidayCalendars | None,
) -> PaymentTerms | None:
    """The payment terms over the legs' anchors: one anchor for every index since
    iferc-publication-payment-anchor.md, each component's last observation day, the expiry under
    lastday on a futures index and the last publication date on a published one, and with two
    legs the later of the two since two-index-fixed-float.md, the one day both legs pay from;
    handed over as a temporary, not held across the kernel's copies."""
    anchors = last_days(legs[0], occurrence.size)
    for observations in legs[1:]:
        anchors = np.maximum(anchors, last_days(observations, occurrence.size))
    return _the_payment_terms(
        settlement, fields, anchors, occurrence, trade_ids, counter, collection
    )


def schedule_rows(
    months: NDArray[np.int64],
    month: NDArray[np.int64],
    occurrence: NDArray[np.intp],
    period_of: Callable[[int], str],
    schedule: str = "the index's schedule",
) -> NDArray[np.intp]:
    """Each component's month resolved to its schedule row, one lookup over the components; a
    month the schedule lacks is refused by the row that covers it and the month, in the words of
    the period form the row booked by, the schedule named as given, by its index's name with two
    indexes since two-index-fixed-float.md."""
    low, high = int(months.min()), int(months.max())
    row_of = np.full(high - low + 1, -1, dtype=np.intp)
    row_of[months - low] = np.arange(months.size, dtype=np.intp)
    inside = (month >= low) & (month <= high)
    contract = np.where(inside, row_of[np.clip(month - low, 0, high - low)], -1)
    missing = contract < 0
    if missing.any():
        k = int(missing.argmax())
        raise ValueError(
            f"{period_of(int(occurrence[k]))}, expected months {schedule} has a contract for; "
            f"it has none for {month_label(month[k])}"
        )
    return contract.astype(np.intp)


# --- the payment days of a financial settlement ---------------------------------------------


def last_days(observations: Observations, components: int) -> NDArray[np.datetime64]:
    """Each component's last observation day, the anchor its payment counts from: the observations
    are in component order, each component's days increasing and every component holding at
    least one, so the last of each sits just before the first of the next, however many a
    method gives; one search over the components for the position after each."""
    after = np.searchsorted(
        observations.component, np.arange(components, dtype=np.intp), side="right"
    )
    return observations.date[after - 1]


def _the_payment_terms(
    settlement: Settlement,
    fields: _Fields,
    anchors: NDArray[np.datetime64],
    occurrence: NDArray[np.intp],
    trade_ids: NDArray[np.int64] | None,
    counter: WorkCounter,
    collection: HolidayCalendars | None,
) -> PaymentTerms | None:
    """For a financial settlement, the payment terms: what each occurrence entered for its
    payment_day, a date or a rule text, with its payment calendar, retained, and each component's
    payment day. Since payment-day-date-or-rule.md a row that entered a date pays every one of its
    components on that day as entered, never rolled, and the day must fall after the row's last
    observation, the latest of its components' anchors, the first row from the top whose day does
    not refused by its trade, its day and that observation through the kernel's one rule; a row
    that entered a rule has it applied to each of its components' anchors instruction by
    instruction, since #181: the anchor its last observation day on every index, the one day under
    lastday and penultimate, the third under last3day and the month's last pricing day under asian
    on a futures index, and on a published index the last publication date its period covers,
    iferc-publication-payment-anchor.md; business days on that calendar, Monday to Friday less
    its holidays, the anchor rolled back to the last eligible day on or before it first, so that a
    day the calendar closes is not itself counted, calendar days and month ends whatever the
    calendar. Each distinct rule is read once, `payment_rule_of`, and applied once per calendar it
    is paid on, to every component of that rule and calendar at once, `shift_days`. Each day an
    instruction makes lies within the sheet's calendar, 1 March 1900 to 31 December 9999, since
    one outside could reach no cell: the first component, in ticket order, whose rule leaves it is
    refused naming its rule, with the row when the ticket gave it, the anchor, the day reached and
    the instruction that reached it when the rule has more than one, representability and no term
    of business; the kernel then holds every final day after its group's last observation. None
    for a physical settlement. A batch whose rows all entered a rule takes the path it took before
    the dates, over every component at once; one with a dated row shifts the ruled components
    alone.

    Work: `payment_rules_read`, the distinct rules, none for a dated row; `payment_shifts`, the
    instructions applied, each over one rule's components on one calendar."""
    match settlement:
        case Settlement.PHYSICAL:
            return None
        case Settlement.FINANCIAL:
            entered = fields.days_or_rules("payment_day")
            calendars = _the_calendars(fields, collection, counter)
            if not entered.is_date.any():
                pays, rules_read, shifts = _the_ruled_days(
                    entered.texts, None, anchors, occurrence, calendars, fields
                )
            else:
                pays = np.empty(anchors.size, dtype="datetime64[D]")
                dated = entered.is_date[occurrence]
                dated_rows = np.flatnonzero(entered.is_date)
                pays[dated] = entered.dates[np.searchsorted(dated_rows, occurrence[dated])]
                # The row's last observation is the latest of its components' anchors, so a strip
                # dated before its final month is refused by the day it needs, not the first it
                # fails; one reduction over the dated components.
                last = np.full(fields.rows, np.iinfo(np.int64).min, dtype=np.int64)
                np.maximum.at(last, occurrence[dated], anchors[dated].astype(np.int64))
                payments_after_observations(
                    entered.dates,
                    last[dated_rows].astype("datetime64[D]"),
                    lambda i: named_trade(trade_ids, int(dated_rows[i])),
                )
                ruled = ~dated
                rules_read = shifts = 0
                if ruled.any():
                    ruled_pays, rules_read, shifts = _the_ruled_days(
                        entered.texts,
                        np.flatnonzero(~entered.is_date),
                        anchors[ruled],
                        occurrence[ruled],
                        calendars,
                        fields,
                    )
                    pays[ruled] = ruled_pays
            counter.hit(PAYMENT_RULES_READ, rules_read)
            counter.hit(PAYMENT_SHIFTS, shifts)
            return PaymentTerms(entered, calendars, pays)
        case _:
            assert_never(settlement)


def _the_calendars(
    fields: _Fields, collection: HolidayCalendars | None, counter: WorkCounter
) -> tuple[HolidayCalendar, ...]:
    """Each occurrence's payment calendar, the one its payment_holiday_key selects from the
    collection, payment-calendar-keys.md: each distinct key text bound once, in the order its
    first row comes, so a refusal names the first row that holds it, by the step a quote
    template shares, keyed_calendar; keys that name one set of calendars share one calendar,
    and rows that share a calendar are counted together as rows sharing a handle were. Every
    row's key is bound, a row paying on a date included, which reads its calendar for nothing:
    the owner's rule of 21 November 2026. A financial batch with no collection is refused by
    the argument. Work: `holiday_keys_bound`, the distinct keys; a combination's own counts."""
    if collection is None:
        raise no_collection("a financially settled batch")
    combined: dict[tuple[str, ...], HolidayCalendar] = {}
    bound, by_key = _each_distinct(
        fields, "payment_holiday_key", partial(keyed_calendar, collection, combined, counter)
    )
    counter.hit(KEYS_BOUND, len(bound))
    return tuple([bound[int(k)] for k in by_key])


def _the_ruled_days(
    texts: tuple[str, ...],
    ruled_rows: NDArray[np.intp] | None,
    anchors: NDArray[np.datetime64],
    occurrence: NDArray[np.intp],
    calendars: tuple[HolidayCalendar, ...],
    fields: _Fields,
) -> tuple[NDArray[np.datetime64], int, int]:
    """The payment days of the components whose rows entered a rule, the rules' instructions
    applied to the anchors given, in the components' order, with the distinct rules read and the
    instructions applied: texts, the ruled rows' rule texts in row order; ruled_rows, those rows,
    or None when every row of the batch entered a rule, the anchors and the occurrences then the
    batch's own; calendars, every occurrence's. One group per rule and calendar paid together,
    numbered rule-major, so the groups come in the order of the rules' first rows and then of
    the calendars'."""
    position = occurrence if ruled_rows is None else np.searchsorted(ruled_rows, occurrence)

    def row_of(at: int) -> int:
        return at if ruled_rows is None else int(ruled_rows[at])

    rules, by_rule = _distinct_texts(
        np.array(texts),
        None,
        lambda i: fields.where("payment_day", row_of(int(i))),
        payment_rule_of,
    )
    ids = np.fromiter(map(id, calendars), dtype=np.int64, count=len(calendars))
    if ruled_rows is not None:
        ids = ids[ruled_rows]
    _, first_rows, inverse = np.unique(ids, return_index=True, return_inverse=True)
    key = (by_rule * first_rows.size + inverse)[position]
    groups, group_of = np.unique(key, return_inverse=True)
    pays = np.empty(anchors.size, dtype="datetime64[D]")
    strayed_at = np.full(anchors.size, -1, dtype=np.intp)
    strayed_to = np.empty(anchors.size, dtype="datetime64[D]")
    shifts = 0
    for g, group in enumerate(groups):
        on = group_of == g
        r, c = divmod(int(group), first_rows.size)
        shifted = shift_days(anchors[on], rules[r], calendars[row_of(int(first_rows[c]))])
        pays[on] = shifted.days
        strayed_at[on] = shifted.strayed_at
        strayed_to[on] = shifted.strayed_to
        shifts += len(rules[r])
    strayed = strayed_at >= 0
    if strayed.any():
        k = int(strayed.argmax())  # the first component, in ticket order, whose rule strays
        at = int(position[k])
        rule = rules[int(by_rule[at])]
        step = int(strayed_at[k])
        named = "" if len(rule) == 1 else f" at instruction {step + 1}, {rule[step].text!r}"
        raise ValueError(
            f"{fields.where('payment_day', row_of(at))} is {texts[at]!r}, counted from "
            f"{anchors[k]} to {strayed_to[k]}{named}, expected a payment day within the "
            f"sheet's calendar, {SHEET_FIRST_DAY} to {SHEET_LAST_DAY}"
        )
    return pays, len(rules), shifts
