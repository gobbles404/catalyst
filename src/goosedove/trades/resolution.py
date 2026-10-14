"""The two children of _CreateTrades and the batch they make. Resolution completes a template's
shared values and a ticket's rows into the resolved terms of one batch on one index: every field
from exactly one of the two, the required fields present and the conditional ones present when
their condition holds, one route, settlement, method, quantity unit and basis for the batch, the
quantity unit naming one of the index's specifications, every code of the index's schedule read
for its month
once, each contract code or strip of the ticket resolved by month to the schedule's rows, the
schedule method's observations made once, and for a financial settlement each component's payment
day counted strictly after its observation day on the payment calendar. Then the kernel:
resolved_trades checks the first profile's rules and encoded turns the terms and the observations
into arrays, and the batch holds both. Nothing here reads a history, a price or a valuation date.
docs/library/trades/create-trades.md is the page."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.unit_conversions import UnitConversions
from goosedove.index_definitions.contract_codes import month_and_year
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import named
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import FUTURE, FieldType
from goosedove.instruments.fields import FieldValues
from goosedove.trades.encoding import Encoded, encoded
from goosedove.trades.observations import Observations, observed
from goosedove.trades.template import (
    SHEET_LAST_DAY,
    TradeTemplate,
    business_days_of,
    months_of,
    quantity_per_of,
    route_of,
    schedule_method_of,
    settlement_of,
)
from goosedove.trades.terms import (
    PaymentTerms,
    ResolvedTrades,
    Route,
    Settlement,
    futures_schedule_of,
    resolved_trades,
)

RESOLVED_OCCURRENCES = "resolved_occurrences"  # ticket rows completed and typed
RESOLVED_COMPONENTS = "resolved_components"  # contract months resolved to schedule rows
SCHEDULE_CODES_READ = "schedule_codes_read"  # codes of the index's schedule read for their month

# The fields a batch has one of: the template's value or a ticket column every row agrees on.
BATCH_FIELDS: Final = (
    "schedule_method",
    "route",
    "settlement_method",
    "quantity_unit",
    "quantity_per",
)
# The conditions of the future's required_when fields, as library rules: the field, the batch
# fact it depends on and the value that fact must have, rendered as the definition shows them,
# `route = cleared`; a field is present exactly when its condition holds.
CONDITIONS: Final[dict[str, tuple[str, Route | Settlement]]] = {
    "clearing_house": ("route", Route.CLEARED),
    "payment_time_lag": ("settlement_method", Settlement.FINANCIAL),
    "payment_holiday_calendar": ("settlement_method", Settlement.FINANCIAL),
}


@dataclass(frozen=True, slots=True)
class Trades:
    """A batch of trades as _CreateTrades publishes it: the resolved terms and their encoding, the
    encoding holding the terms by reference as well, so each fact is kept once and the two
    sections are read together or apart. Nothing of a market, a history or a valuation date is
    here; preparation and evaluation make their own records over this one."""

    resolved: ResolvedTrades
    encoded: Encoded


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
    terms, observations = resolved(index, ticket, template, counter)
    return Trades(terms, encoded(terms, observations, units, counter))


def resolved(
    index: Index, ticket: FieldValues, template: TradeTemplate, counter: WorkCounter
) -> tuple[ResolvedTrades, Observations]:
    """The resolution child: the terms of a batch from a template and a ticket, checked in this
    order, the first failure being the message, and then the kernel's own rules; with them the
    observations the schedule method gave the components, made once here and handed on to the
    encoding, since the payment days count from them.

    The ticket is bound against the template's instrument, the future, the one whose trades are
    built. No field is supplied by both, even to the same value. Every required field is present
    in one of them. The batch fields are one each, the template's value or a column every row
    agrees on, and each is read for its meaning: the quantity unit by name among the index's
    specifications, exactly as the index names them, the method, the route, the settlement and
    the basis from their lists, each named with its row where the ticket supplied it, since the
    page promises a ticket's field its row. Each conditional field
    is present exactly when its condition holds, a clearing house with a cleared route and the
    two payment fields with a financial settlement, and absent otherwise, since a label for a
    clearing house a bilateral trade has not, or a payment a physical contract never makes, would
    say something false. The index is a futures index, and every code of its schedule is read for
    its month, the rows the ticket does not use included, a label that is no contract code and
    two rows for one month refused by row. Each contract code of the ticket is read once per
    distinct text, in the order the sheet first shows each, so that the first row that breaks the
    grammar is the one named, through the period grammar, in either case, for the months it
    spans, and each
    month is resolved to its schedule row, a month the schedule lacks refused by the trade's row
    and the month; a strip makes one component per month, in order, all on the one occurrence.
    The schedule method gives each component its observation day, the expiry under lastday and
    the business day before it under penultimate. For a financial settlement, each occurrence's
    lag is read once per distinct text and each component pays that many business days strictly
    after its observation day, counted on its occurrence's payment calendar with Monday to Friday
    eligible, the observation day itself rolled back first so that a day the payment calendar
    closes is not counted; the rule of the two methods built, a later method stating its own.
    Then the kernel's rules, through resolved_trades: whole quantities, zero included, and finite
    prices, each named by its trade, and a financial settlement with penultimate.

    Work: one occurrence per ticket row, one component per contract month and one schedule code
    per row of the schedule, reported to the counter.
    """
    fields = _fields(template, ticket)
    _the_required(fields)
    specification = _the_specification(
        index, fields.where("quantity_unit", 0), fields.one_text("quantity_unit")
    )
    schedule_method = schedule_method_of(
        fields.where("schedule_method", 0), fields.one_text("schedule_method")
    )
    route = route_of(fields.where("route", 0), fields.one_text("route"))
    settlement = settlement_of(
        fields.where("settlement_method", 0), fields.one_text("settlement_method")
    )
    quantity_per = quantity_per_of(fields.where("quantity_per", 0), fields.one_text("quantity_per"))
    _the_conditions(fields, route, settlement)
    schedule = futures_schedule_of(index)
    months = _the_schedule_months(schedule)
    counter.hit(SCHEDULE_CODES_READ, len(schedule.codes))
    occurrence, contract = _the_contracts(fields, months)
    observations = observed(schedule_method, index, contract)
    payment = _the_payment_terms(settlement, fields, observations.date, occurrence)
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
        fields.labels("trade_id"),
        fields.labels("clearing_house"),
        fields.labels("broker"),
        fields.dates("trade_date"),
        occurrence,
        contract,
        fields.numbers("quantity")[occurrence],
        fields.numbers("fixed_price")[occurrence],
        payment,
    )
    return terms, observations


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
        return name in self.template.defaults or self.ticket.has(name)

    def where(self, name: str, row: int) -> str:
        """A field named in a message: with the row when the ticket supplied it, since each row
        has its own value, and alone when the template did, since every row has the same."""
        if name in self.template.defaults:
            return name
        return f"{name} row {row + 1}"

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
    """The template's instrument the future, the ticket bound against it, and the two disjoint."""
    if template.instrument is not FUTURE:
        raise ValueError(
            f"template is of instrument {template.instrument.name!r}, expected {FUTURE.name}, "
            "the one instrument whose trades are built"
        )
    if ticket.instrument is not template.instrument:
        raise ValueError(
            f"ticket is of instrument {ticket.instrument.name!r}, expected the template's, "
            f"{template.instrument.name!r}"
        )
    for name in ticket.names:
        if name in template.defaults:
            raise ValueError(
                f"{name} is supplied by the template and by the ticket, expected by one of them"
            )
    return _Fields(template, ticket)


def _the_required(fields: _Fields) -> None:
    """Every field the definition always requires, present in one of the two."""
    for field in fields.template.instrument.fields:
        if field.required and not fields.has(field.name):
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


def _the_schedule_months(schedule: FuturesSchedule) -> NDArray[np.int64]:
    """The month of every code of the schedule, as numpy counts months, one read per code: a
    code that is no contract code is refused by row, and so are two rows for one month, since a
    month resolved to two rows would name no contract."""
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


def _each_distinct[T](
    fields: _Fields, name: str, read: Callable[[str, str], T]
) -> tuple[list[T], NDArray[np.intp]]:
    """A text field read once per distinct text, the first row holding each named in a refusal,
    and the position of each occurrence's text among the distinct ones. The texts are read in
    the order their first rows come, not the order they sort in, so the first row from the top
    that breaks the grammar is the one named; the values are kept in the sorted order the
    positions index."""
    texts = np.array(fields.texts(name))
    distinct, first_rows, inverse = np.unique(texts, return_index=True, return_inverse=True)
    by_row = np.argsort(first_rows)  # the distinct texts in the order their first rows come
    read_values = {
        int(i): read(fields.where(name, int(first_rows[i])), str(distinct[i])) for i in by_row
    }
    return [read_values[i] for i in range(distinct.size)], inverse.astype(np.intp)


def _the_contracts(
    fields: _Fields, months: NDArray[np.int64]
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    """Each occurrence's contract code read for its months and each month resolved to its
    schedule row, in one pass over the components: the occurrence of each component and the
    schedule row of its contract, aligned."""
    spans, inverse = _each_distinct(fields, "contract_code", months_of)
    bounds = np.array(spans, dtype=np.int64).reshape(-1, 2)[inverse]
    first, after = bounds[:, 0], bounds[:, 1]
    count = after - first
    occurrence = np.repeat(np.arange(fields.rows, dtype=np.intp), count)
    starts = np.cumsum(count) - count
    month = first[occurrence] + (np.arange(occurrence.size) - starts[occurrence])
    low, high = int(months.min()), int(months.max())
    row_of = np.full(high - low + 1, -1, dtype=np.intp)
    row_of[months - low] = np.arange(months.size, dtype=np.intp)
    inside = (month >= low) & (month <= high)
    contract = np.where(inside, row_of[np.clip(month - low, 0, high - low)], -1)
    missing = contract < 0
    if missing.any():
        k = int(missing.argmax())
        i = int(occurrence[k])
        raise ValueError(
            f"{fields.where('contract_code', i)} is {fields.texts('contract_code')[i]!r}, "
            "expected months the index's schedule has a contract for; "
            f"it has none for {_month(month[k])}"
        )
    return occurrence, contract.astype(np.intp)


def _month(count: object) -> str:
    """A month as numpy counts them, written as the sheet reads one: 2027-04."""
    return str(np.datetime64(int(cast(Any, count)), "M"))


# --- the payment days of a financial settlement ---------------------------------------------


def _the_payment_terms(
    settlement: Settlement,
    fields: _Fields,
    anchors: NDArray[np.datetime64],
    occurrence: NDArray[np.intp],
) -> PaymentTerms | None:
    """For a financial settlement, the payment terms: each occurrence's lag in business days and
    its payment calendar, retained, and each component's payment day, the lag counted strictly
    after its anchor, its one observation day under the two methods built, on that calendar,
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
