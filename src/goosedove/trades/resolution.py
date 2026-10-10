"""The two children of _CreateTrades and the batch they make. Resolution completes a template's
shared values and a ticket's rows into the resolved terms of one batch on one index: every field
from exactly one of the two, the required fields present and the conditional ones present when
their condition holds, one route and one settlement for the batch and a quantity unit, a method
and a basis per row, in that order, each distinct text of the three read once, the quantity unit
naming one of the index's specifications, every code of the index's
schedule read for its month once, each row's period chosen row by row since #172, its two dates
when both are supplied and its contract code otherwise, the code resolved by month to the
schedule's rows or the dates split at month ends, every component
with the days it covers, its method's observations made once over those days, and for a
financial settlement each component's payment day counted strictly after its last observation day
on the payment calendar. Then the kernel:
resolved_trades checks the first profile's rules and encoded turns the terms and the observations
into arrays, and the batch holds both. Nothing here reads a history, a price or a valuation date.
docs/library/trades/create-trades.md is the page."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.contract_codes import month_and_year
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import named
from goosedove.index_definitions.sheet_days import SHEET_LAST_DAY
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FIXED_FLOAT, FieldType
from goosedove.instruments.fields import FieldValues
from goosedove.trades.encoding import Encoded, encoded
from goosedove.trades.observations import Observations, observed
from goosedove.trades.template import (
    TradeTemplate,
    business_days_of,
    months_of,
    quantity_per_of,
    route_of,
    schedule_method_of,
    settlement_of,
)
from goosedove.trades.terms import (
    BASES,
    METHODS,
    PaymentTerms,
    ResolvedTrades,
    Route,
    Settlement,
    marketing_reserves,
    named_trade,
    reporting_lot_of,
    resolved_trades,
    trade_schedule_of,
    whole_trade_ids,
)

RESOLVED_OCCURRENCES = "resolved_occurrences"  # ticket rows completed and typed
RESOLVED_COMPONENTS = "resolved_components"  # contract months resolved to schedule rows
SCHEDULE_CODES_READ = "schedule_codes_read"  # codes of the index's schedule read for their month
# Distinct codes of the rows that book by code, read for their months, since #172: a row that
# books by its dates has its code, if any, read for nothing and counted here for nothing.
TICKET_CODES_READ = "ticket_codes_read"
PERIOD_FIELDS: Final = ("contract_code", "start_date", "end_date")

# The conditions of the fixed_float's required_when fields, as library rules: the field, the batch
# fact it depends on and the value that fact must have, rendered as the definition shows them,
# `route = cleared`; a field is present exactly when its condition holds.
CONDITIONS: Final[dict[str, tuple[str, Route | Settlement]]] = {
    "clearing_house": ("route", Route.CLEARED),
    "counterparty": ("route", Route.BILATERAL),  # since #NN
    "payment_time_lag": ("settlement_method", Settlement.FINANCIAL),
    "payment_holiday_calendar": ("settlement_method", Settlement.FINANCIAL),
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
    index: Index,
    ticket: FieldValues,
    template: TradeTemplate,
    units: UnitConversions,
    counter: WorkCounter,
) -> Trades:
    """The one way to make Trades: resolution, which makes the schedule method's observations on
    the way to the payment days, then encoding over the terms and those observations, the unit
    tables and the counter passed in and never looked up; a failure in any publishes nothing."""
    terms, observations, entered = resolved(index, ticket, template, counter)
    return Trades(terms, encoded(terms, observations, units, counter), *entered)


def resolved(
    index: Index, ticket: FieldValues, template: TradeTemplate, counter: WorkCounter
) -> tuple[ResolvedTrades, Observations, tuple[NDArray[np.bool_], tuple[str, ...]]]:
    """The resolution child: the terms of a batch from a template and a ticket, checked in this
    order, the first failure being the message, and then the kernel's own rules; with them the
    observations the schedule method gave the components, made once here and handed on to the
    encoding, since the payment days count from them, and what the rows entered for their codes,
    the rows that entered one and their texts.

    The ticket is bound against the template's instrument, the fixed_float, the one whose trades are
    built. No field is supplied by both, even to the same value. Every required field is present
    in one of them. The route and the settlement are one each, the template's value or a column
    every row agrees on; the quantity unit, the method and the basis are each row's own, the
    template's value for every row or the ticket's column, so that one batch mixes them row by
    row, each distinct text read once for its meaning in the order its first row comes: the
    quantity unit by name among the index's specifications, exactly as the index names them,
    the method and the basis from their lists, the route and the settlement likewise, each named
    with its row where the ticket supplied it, since the page promises a ticket's field its row,
    the unit, the method, the route, the settlement and the basis in that order. Each conditional
    field is present exactly when its
    condition holds, a clearing house with a cleared route, since #NN a counterparty with a
    bilateral one, and the two payment fields with a financial settlement, and absent otherwise,
    since a label for a clearing house a bilateral trade has not, a counterparty a cleared trade
    faces through its clearing house, or a payment a physical contract never makes, would say
    something false. Since #NN a marketing reserve may stand in either, a finite amount of zero
    or more per row, the template's one value booked once by every row or the ticket's column,
    the first bad row named, and none at all when neither supplies the field. The
    trade IDs, since #168, are whole numbers of at most 15 digits, the template's one read when
    the template was made and the ticket's column read here, the first bad row named. The
    index is a futures index or, since #167, an IFERC index, a Gas Daily one refused by name,
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
    the same way; on an IFERC index, since #167, the month's index on its publication day under
    lastday, the one method it takes, the first row of another refused by its method and row.
    For a financial settlement, each
    occurrence's lag is read once per distinct text and each component pays that many business days
    strictly after its anchor, on a futures index its last observation day and on an IFERC index
    its month's last trading day, counted on its occurrence's payment calendar with
    Monday to Friday eligible,
    that day itself rolled back first so that a day the payment calendar closes is not counted;
    the rule of the four methods.
    Then the kernel's rules, through resolved_trades: whole quantities, zero included, and finite
    prices, each named by its trade, a financial settlement with penultimate, last3day and asian,
    the first row of them named under a physical one, and each component's quantity formed once
    by the basis, the entered quantity times its covered days under calday.

    Work: one occurrence per ticket row, one component per contract month, one schedule code
    per row of the schedule and since #172 one ticket code per distinct code of the rows that book
    by code, none for a row that books by its dates, reported to the counter.
    """
    fields = _fields(template, ticket)
    _the_required(fields)
    specifications, by_unit = _each_distinct(
        fields, "quantity_unit", partial(_the_specification, index)
    )
    methods, by_method = _each_distinct(fields, "schedule_method", schedule_method_of)
    route = route_of(fields.where("route", 0), fields.one_text("route"))
    settlement = settlement_of(
        fields.where("settlement_method", 0), fields.one_text("settlement_method")
    )
    bases, by_basis = _each_distinct(fields, "quantity_per", quantity_per_of)
    _the_conditions(fields, route, settlement)
    specification = np.array(specifications, dtype=np.intp)[by_unit]
    schedule_method = np.array([METHODS.index(m) for m in methods], dtype=np.intp)[by_method]
    quantity_per = np.array([BASES.index(b) for b in bases], dtype=np.intp)[by_basis]
    schedule = trade_schedule_of(index)
    reporting_lot_of(index)
    months = schedule_months(schedule)
    counter.hit(SCHEDULE_CODES_READ, len(schedule.codes))
    periods = _the_periods(fields, months)
    counter.hit(TICKET_CODES_READ, periods.codes_read)
    occurrence, contract = periods.occurrence, periods.contract
    start, end = periods.start, periods.end
    trade_ids = fields.ids("trade_id")
    observations = observed(
        schedule_method[occurrence],
        index,
        contract,
        start,
        end,
        lambda k: named_trade(trade_ids, int(occurrence[k])),
    )
    # The anchors are handed over as a temporary, not held across the kernel's copies below.
    match schedule:
        case FuturesSchedule():
            payment = _the_payment_terms(
                settlement, fields, _last_days(observations, occurrence.size), occurrence
            )
        case IfercSchedule():
            # Since #167: the month's last trading day, the exchange's; the index prints later.
            payment = _the_payment_terms(
                settlement, fields, schedule.last_trading_date[contract], occurrence
            )
        case _:
            assert_never(schedule)
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
        trade_ids,
        fields.labels("clearing_house"),
        fields.labels("broker"),
        fields.dates("trade_date"),
        occurrence,
        contract,
        fields.numbers("quantity")[occurrence],
        start,
        end,
        fields.numbers("fixed_price")[occurrence],
        payment,
        counterparty=fields.labels("counterparty"),
        marketing_reserve=fields.amounts("marketing_reserve"),
    )
    return terms, observations, periods.entered


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

    def amounts(self, name: str) -> NDArray[np.float64] | None:
        """The marketing reserves per occurrence, finite amounts of zero or more since #NN, or None
        when neither supplied them: the template's one, read for the rule when the template was
        made and repeated here, or the ticket's column read for it now, the first bad row named
        by the field and the row."""
        if not self.has(name):
            return None
        if name in self.template.defaults:
            return np.full(self.rows, cast(float, self.template.defaults[name]))
        return marketing_reserves(self.ticket.numbers(name), lambda k: self.where(name, k))

    def numbers(self, name: str) -> NDArray[np.float64]:
        if name in self.template.defaults:
            return np.full(self.rows, cast(float, self.template.defaults[name]))
        return self.ticket.numbers(name)

    def dates(self, name: str) -> NDArray[np.datetime64]:
        if name in self.template.defaults:
            return np.full(self.rows, self.template.defaults[name], dtype="datetime64[D]")
        return self.ticket.dates(name)

    def objects(self, name: str) -> tuple[object, ...]:
        if name in self.template.defaults:
            return (self.template.defaults[name],) * self.rows
        return self.ticket.objects(name)

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
            case FieldType.HOLIDAY_CALENDAR:
                return named(self.objects(name)[0])
            case _:
                assert_never(self.ticket.field(name).type)


def _fields(template: TradeTemplate, ticket: FieldValues) -> _Fields:
    """The template's instrument the fixed_float, the ticket bound against it, and the two
    disjoint."""
    if template.instrument is not FIXED_FLOAT:
        raise ValueError(
            f"template is of instrument {template.instrument.name!r}, expected {FIXED_FLOAT.name}, "
            "the one instrument whose trades are built"
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


def _the_specification(index: Index, where: str, name: str) -> int:
    """The row of the index's specifications the quantity unit names, exactly: no trimming, no
    case folding, no alias and no first row taken for want of a match, the index's names being
    the choices, so a unit the tables know but the index does not define is refused like any
    other text."""
    names = index.specifications.names
    if name not in names:
        choices = ", ".join(repr(each) for each in names)
        raise ValueError(
            f"{where} is {name!r}, expected one of the index's specifications: {choices}"
        )
    return names.index(name)


# --- the contracts: every schedule code read, each ticket code resolved by month -------------


def schedule_months(schedule: FuturesSchedule | IfercSchedule) -> NDArray[np.int64]:
    """The month of every code of the schedule, as numpy counts months, one read per code: a
    code that is no contract code is refused by row, and so are two rows for one month, since a
    month resolved to two rows would name no contract. The resolution reads them once and
    resolves the ticket's periods against them."""
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
            f"both {_month(by_month[same[0]])}, expected one contract per month"
        )
    return months


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
class _Periods:
    """What the rows' periods resolved to: per component its occurrence, its schedule row and the
    first and the last day it covers, aligned; which rows entered a code, a read-only mask the
    batch owns, with the texts they entered in row order; and how many distinct codes were read
    for their months."""

    occurrence: NDArray[np.intp]
    contract: NDArray[np.intp]
    start: NDArray[np.datetime64]
    end: NDArray[np.datetime64]
    entered: tuple[NDArray[np.bool_], tuple[str, ...]]
    codes_read: int


def _the_periods(fields: _Fields, months: NDArray[np.int64]) -> _Periods:
    """Each occurrence's period chosen row by row and resolved to its components, one per
    calendar month it covers, in one pass over the components, since #172. A row with both dates
    books the days between them, a code beside them kept as entered text and never read; a row
    with neither books its code; a row with one date and not the other, or with no code and no
    pair, is refused, the first such row from the top, once every row's three fields are known
    and before any code is read. The dated rows' ends are held on or after their starts, by row.
    The codes of the rows that book by code are read once per distinct text, in the order their
    first rows come, so the first row from the top that breaks the grammar is the one named;
    then each row's first month and the month after its last, from the code's span or the
    dates' months, the components in row order whichever form each row took, each month looked
    up in the schedule's months, a month without a contract refused by the row and the month,
    and each component's days its month's, a dated row's first and last clipped to its dates.
    The month bounds are one conversion each over the components, the clipping one maximum and
    one minimum over the dated components, and the days are the kernel's to count."""
    rows = fields.rows
    code_on, codes = fields.period_texts("contract_code")
    start_on, starts = fields.period_dates("start_date")
    end_on, ends = fields.period_dates("end_date")
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
            f"{fields.where(given, i)} is {values[int(np.count_nonzero(on[:i]))]} without "
            f"{fields.where(other, i)}, expected both dates, the period's first and last day, or "
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
            f"{fields.where('end_date', i)} is {dated_ends[k]}, expected a day on or after "
            f"{fields.where('start_date', i)}, {dated_starts[k]}"
        )
    coded_rows = np.flatnonzero(~dated)  # each supplies a code, the rule above having passed
    coded_texts = np.array(codes, dtype=object)[rank_code[coded_rows]]
    spans, inverse = _distinct_texts(
        coded_texts, coded_rows, lambda i: fields.where("contract_code", i), months_of
    )
    bounds = np.array(spans, dtype=np.int64).reshape(-1, 2)[inverse]
    first = np.empty(rows, dtype=np.int64)
    after = np.empty(rows, dtype=np.int64)
    first[coded_rows], after[coded_rows] = bounds[:, 0], bounds[:, 1]
    first[dated_rows] = dated_starts.astype("datetime64[M]").astype(np.int64)
    after[dated_rows] = dated_ends.astype("datetime64[M]").astype(np.int64) + 1
    count = after - first
    occurrence = np.repeat(np.arange(rows, dtype=np.intp), count)
    offsets = np.cumsum(count) - count
    month = first[occurrence] + (np.arange(occurrence.size) - offsets[occurrence])

    def period_of(i: int) -> str:
        """A row's period as a refusal names it: its two dates, or the code it books by."""
        if dated[i]:
            k = int(rank_dated[i])
            return (
                f"{fields.where('start_date', i)} is {dated_starts[k]} and "
                f"{fields.where('end_date', i)} {dated_ends[k]}"
            )
        return f"{fields.where('contract_code', i)} is {codes[int(rank_code[i])]!r}"

    contract = _schedule_rows(months, month, occurrence, period_of)
    start, end = month_bounds(month)
    on = dated[occurrence]  # the dated rows' components, clipped to their rows' dates
    if on.any():
        k = rank_dated[occurrence[on]]
        start[on] = np.maximum(start[on], dated_starts[k])
        end[on] = np.minimum(end[on], dated_ends[k])
    entered = np.array(code_on, dtype=bool)  # the batch's own copy of which rows entered a code
    entered.setflags(write=False)
    return _Periods(occurrence, contract, start, end, (entered, codes), len(spans))


def _schedule_rows(
    months: NDArray[np.int64],
    month: NDArray[np.int64],
    occurrence: NDArray[np.intp],
    period_of: Callable[[int], str],
) -> NDArray[np.intp]:
    """Each component's month resolved to its schedule row, one lookup over the components; a
    month the schedule lacks is refused by the row that covers it and the month, in the words of
    the period form the row booked by."""
    low, high = int(months.min()), int(months.max())
    row_of = np.full(high - low + 1, -1, dtype=np.intp)
    row_of[months - low] = np.arange(months.size, dtype=np.intp)
    inside = (month >= low) & (month <= high)
    contract = np.where(inside, row_of[np.clip(month - low, 0, high - low)], -1)
    missing = contract < 0
    if missing.any():
        k = int(missing.argmax())
        raise ValueError(
            f"{period_of(int(occurrence[k]))}, expected months the index's schedule has a "
            f"contract for; it has none for {_month(month[k])}"
        )
    return contract.astype(np.intp)


def month_bounds(
    month: NDArray[np.int64],
) -> tuple[NDArray[np.datetime64], NDArray[np.datetime64]]:
    """The first and the last calendar day of each month given, as numpy counts months: the days a
    whole-month component covers, and the bounds an explicit period's components are clipped to,
    one conversion each way and one day subtracted."""
    first = month.astype("datetime64[M]").astype("datetime64[D]")
    after = (month + 1).astype("datetime64[M]").astype("datetime64[D]")
    last = cast(NDArray[np.datetime64], after - np.timedelta64(1, "D"))  # a day, not a span
    return first, last


def _month(count: object) -> str:
    """A month as numpy counts them, written as the sheet reads one: 2027-04."""
    return str(np.datetime64(int(cast(Any, count)), "M"))


# --- the payment days of a financial settlement ---------------------------------------------


def _last_days(observations: Observations, components: int) -> NDArray[np.datetime64]:
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
) -> PaymentTerms | None:
    """For a financial settlement, the payment terms: each occurrence's lag in business days and
    its payment calendar, retained, and each component's payment day, the lag counted strictly
    after its anchor, on a futures index its last observation day, the one day under lastday and
    penultimate, the third under last3day and the month's last pricing day under asian, and on
    an IFERC index since #167 its month's last trading day, the exchange's, the index printing
    later, on that calendar,
    Monday to Friday less the calendar's holidays, the anchor rolled back to the last eligible day
    on or before it first, so that a day the calendar closes is not itself counted; one busday
    offset over the components on each distinct calendar. Each day made is on or before the
    sheet's last day, 31 December 9999, since a later one could reach no cell: the first
    component paying past it is refused naming its lag, with the row when the ticket gave it,
    the anchor it was counted from and the day it reached, representability and no term of
    business. None for a physical settlement."""
    match settlement:
        case Settlement.PHYSICAL:
            return None
        case Settlement.FINANCIAL:
            lags, by_lag = _each_distinct(fields, "payment_time_lag", business_days_of)
            lag_days = np.array(lags, dtype=np.int64)[by_lag]
            lag = lag_days[occurrence]
            calendars = cast(
                tuple[HolidayCalendar, ...], fields.objects("payment_holiday_calendar")
            )
            ids = np.fromiter(map(id, calendars), dtype=np.int64, count=len(calendars))
            _, first_rows, inverse = np.unique(ids, return_index=True, return_inverse=True)
            pays = np.empty(anchors.size, dtype="datetime64[D]")
            for g, row in enumerate(first_rows):
                on = inverse[occurrence] == g
                pays[on] = np.busday_offset(
                    anchors[on], lag[on], roll="backward", holidays=calendars[int(row)].holiday
                )
            late = pays > SHEET_LAST_DAY
            if late.any():
                k = int(late.argmax())  # the first component paying past the sheet's last day
                row = int(occurrence[k])
                raise ValueError(
                    f"{fields.where('payment_time_lag', row)} is "
                    f"{fields.texts('payment_time_lag')[row]!r}, counted from {anchors[k]} to "
                    f"{pays[k]}, expected a payment day on or before {SHEET_LAST_DAY}, the last a "
                    "sheet can show"
                )
            return PaymentTerms(lag_days, calendars, pays)
        case _:
            assert_never(settlement)
