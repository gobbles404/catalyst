"""A request for quote, rfq-quoting.md and since dated-quotes.md: a saved quantity and payment
schedule for quoting, one index and one quote template's terms over a ticket's rows, each row a
contract month or a strip by its code or the days between two dates, with its quantity, and
either the template's payment days or a column of the request's own dates, which takes
precedence over the template's day for this request alone. Created once: each row's period
chosen and resolved by the booking's own rule, a component per calendar month under monthly and
the row's whole period as one window under onetime, the quantities read and formed by the
template's basis, the observations made by the template's method with their pricing references,
the payment days made from the template or taken from the request, exactly and never shifted,
and the request's pricing form retained, request.py's, with no history, price, factor or
valuation day. Priced on any market over the request's exact index by the quote's own
calculation, each component at its quantity, the market supplying the day, the history and the
quotes on each call. Read back with its entered and resolved facts and the source of its payment
days, and nothing priced. docs/library/quoting/rfq.md is the page."""

from dataclasses import dataclass
from enum import Enum
from typing import Final, assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.index_definitions.contract_codes import schedule_months
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.fields import FieldValues
from goosedove.market.market import Market
from goosedove.quoting.request import (
    MONTHS_RESOLVED,
    OBSERVATIONS_MADE,
    PAYMENT_DAYS_MADE,
    WINDOWS_RESOLVED,
    Period,
    Request,
    component_words,
    priced,
    the_curve,
    the_frequency,
    the_method,
    the_payments,
    the_terms,
)
from goosedove.quoting.template import QuoteTemplate
from goosedove.trades.encoding import observation_references
from goosedove.trades.observations import observed
from goosedove.trades.resolution import (
    PAYMENT_RULES_READ,
    PAYMENT_SHIFTS,
    SCHEDULE_CODES_READ,
    TICKET_CODES_READ,
    contract_days,
    last_days,
    resolve_periods,
)
from goosedove.trades.schedule_methods import METHODS
from goosedove.trades.terms import (
    QuantityPer,
    Settlement,
    SettlementFrequency,
    payments_after_observations,
    trade_schedule_of,
)

# The fields a request's rows hold, of the fixed_float's definition and bound by its headers as a
# ticket's are: a period by code or by two dates, a quantity, and a payment day per row.
REQUEST_FIELDS: Final = ("contract_code", "start_date", "end_date", "quantity", "payment_day")


class PaymentSource(Enum):
    """Where a financial request's payment days came from: the template's day or rule applied
    to each component, or the request's own column taken exactly."""

    TEMPLATE = "template"
    REQUEST = "request"


@dataclass(frozen=True, slots=True)
class Rfq:
    """The request as the sheet entered it and as it was resolved, read-only: the template by
    reference; rows, how many the ticket held; occurrence[k] the entered row component k came
    from, in row order, a row one component or since dated-quotes.md a month each of the months
    it spans; quantity[i] the row's entered quantity, finite and zero or more, at least one
    positive, in one common unit the caller chose; component_quantity[k] the quantity the
    template's basis gives the component, the row's per month or per period and the row's times
    the component's calendar days per calendar day, formed once; the payment source, the
    template's or the request's, None for a physical request, which pays on no day; and the
    pricing form, the index, the terms, the period, the observations and their references, the
    quantities and the payment days, which every quote of the request reads and nothing
    rebuilds."""

    template: QuoteTemplate
    rows: int
    occurrence: NDArray[np.intp]
    quantity: NDArray[np.float64]
    component_quantity: NDArray[np.float64]
    payment_source: PaymentSource | None
    request: Request


def rfq(index: Index, ticket: FieldValues, template: QuoteTemplate, counter: WorkCounter) -> Rfq:
    """The one way to make an Rfq, the rules in this order, the first failure being the message:
    the ticket's headers among the five fields a request's rows hold, a quantity on every row and
    one row at least; the template holds every term a completed quote requires, a missing
    payment_day stood in for by the request's dates and otherwise refused naming both sources;
    the frequency with the terms it stands under, the kernel's rule, since dated-quotes.md a
    onetime request as a onetime booking; the index takes the terms as a quote's market would; a
    physical request takes no dates; each row's period by the booking's rule, both dates the
    days between them, neither the code, a code read once per distinct text through the period
    grammar, every month a contract of the index's schedule and a window the contract pricing
    its first day; each quantity finite and zero or more, one at least positive, and under
    calday its product with each component's days finite; the observations by the template's
    method and their pricing references by the pipeline's rules; the payment days, the
    template's date or rule on each component, or the request's dates exactly, a date on every
    row and never shifted, a row's date on each of its components, each after its component's
    last observation. Work: the template's values read, the schedule's codes read, the ticket's
    distinct codes read, the months or the windows resolved, the observations made, the payment
    rule read and applied or none for the request's dates, and the payment days made; no market,
    fixing or factor is read."""
    _the_fields(ticket)
    dated = ticket.has("payment_day")
    terms = the_terms(template, counter, dated)
    the_frequency(terms, index.kind, "the request")
    schedule = trade_schedule_of(index)
    the_method(terms, schedule)
    if dated and terms.settlement is Settlement.PHYSICAL:
        raise ValueError(
            "payment_day is supplied, expected none with settlement_method = physical; a "
            "physical delivery pays on no day"
        )
    n = ticket.rows
    onetime = terms.frequency is SettlementFrequency.ONETIME
    codes = schedule.codes
    counter.hit(SCHEDULE_CODES_READ, len(codes))
    code_on, code_texts = _texts_of(ticket, "contract_code")
    start_on, starts = _dates_of(ticket, "start_date")
    end_on, ends = _dates_of(ticket, "end_date")
    periods = resolve_periods(
        code_on,
        code_texts,
        start_on,
        starts,
        end_on,
        ends,
        _where,
        np.full(n, onetime, dtype=np.bool_),
        ((schedule_months(schedule), "the index's schedule"),),
        contract_days(schedule),
    )
    counter.hit(TICKET_CODES_READ, periods.codes_read)
    occurrence, contract = periods.occurrence, periods.contracts[0]
    start, end, window = periods.start, periods.end, periods.window
    components = occurrence.size
    counter.hit(WINDOWS_RESOLVED if onetime else MONTHS_RESOLVED, components)
    for column in (occurrence, contract, start, end, window):
        column.setflags(write=False)
    period = Period(contract, start, end, window)
    quantity = _the_quantities(ticket.numbers("quantity"))
    component_quantity = _the_component_quantities(
        terms.quantity_per, quantity, occurrence, start, end
    )

    def named(k: int) -> str:
        return f"row {int(occurrence[k]) + 1}"

    def booked(k: int) -> str:
        return "the window" if window[k] else codes[int(contract[k])]

    def component(k: int) -> str:
        return f"{component_words(codes, period, k)} of row {int(occurrence[k]) + 1}"

    method = np.full(components, METHODS.index(terms.method), dtype=np.intp)
    observations = observed(method, index, contract, start, end, named, booked=booked)
    counter.hit(OBSERVATIONS_MADE, observations.component.size)
    references = observation_references(
        schedule, index.holiday_calendar, observations, contract, method, component
    )
    references.setflags(write=False)
    if not dated:
        pays = the_payments(terms, observations, components, component, counter)
        source = None if pays is None else PaymentSource.TEMPLATE
    else:
        pays = _the_dates(ticket)[occurrence]
        counter.hit(PAYMENT_RULES_READ, 0)
        counter.hit(PAYMENT_SHIFTS, 0)
        counter.hit(PAYMENT_DAYS_MADE, components)
        payments_after_observations(pays, last_days(observations, components), component)
        pays.setflags(write=False)
        source = PaymentSource.REQUEST
    request = Request(
        index, schedule, terms, period, observations, references, component_quantity, pays
    )
    return Rfq(template, n, occurrence, quantity, component_quantity, source, request)


def quote_rfq(
    market: Market, request: Rfq, curve_set: DiscountCurveSet | None, counter: WorkCounter
) -> float:
    """The price of a saved request on a market: the market's index is the request's, the one
    object, before any data is gathered; the collection is supplied for a bilateral request and
    left out for a cleared one, the key bound to the curve of that exact name and the curve
    starting on the valuation day; then the retained form priced on the market by the quote's
    calculation, nothing of the period, the observations or the payments made again. Work: the
    curve selected, the fixings and live prices read and the factors read, as a quote's."""
    index = market.market_history.calendar.index
    mine = request.request.index
    if index is not mine:
        raise ValueError(
            f"market is over another index, {index.name!r}, expected the request's, {mine.name!r}"
        )
    as_of = market.market_history.calendar.valuation_date.as_of
    curve = the_curve(request.request.terms, curve_set, as_of, counter)
    return priced(request.request, market, curve, counter)


# --- the ticket --------------------------------------------------------------------------------


def _the_fields(ticket: FieldValues) -> None:
    """The ticket's headers each one of the five a request's rows hold, the first other named by
    the field it is; a quantity column, since every row has one; and one row at least."""
    for name in ticket.names:
        if name not in REQUEST_FIELDS:
            raise ValueError(
                f"{name} is a field of booking alone, expected one a request's rows hold: "
                f"{', '.join(REQUEST_FIELDS)}"
            )
    if not ticket.has("quantity"):
        raise ValueError("quantity is missing, expected a column of the request, one per row")
    if ticket.rows == 0:
        raise ValueError("rows has 0 rows, expected one or more, a period and a quantity per row")


def _where(name: str, row: int) -> str:
    """A field of a row named in a message, every value a request holds being a row's own."""
    return f"{name} row {row + 1}"


def _texts_of(ticket: FieldValues, name: str) -> tuple[NDArray[np.bool_], tuple[str, ...]]:
    """A period field's texts and which rows supplied them: the column over the rows whose cells
    held a value, in row order, or nothing when the ticket has no such column."""
    if ticket.has(name):
        return ticket.supplied_rows(name), ticket.texts(name)
    return np.zeros(ticket.rows, dtype=np.bool_), ()


def _dates_of(ticket: FieldValues, name: str) -> tuple[NDArray[np.bool_], NDArray[np.datetime64]]:
    """A period field's days and which rows supplied them, as _texts_of gives texts."""
    if ticket.has(name):
        return ticket.supplied_rows(name), ticket.dates(name)
    return np.zeros(ticket.rows, dtype=np.bool_), np.empty(0, dtype="datetime64[D]")


def _the_quantities(quantities: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each row's quantity finite and zero or more, the first that is not refused by its row, and
    at least one positive, since a request of nothing has no price: a weighted quote, not a
    spread or a net position; copied once and frozen."""
    bad = ~np.isfinite(quantities) | (quantities < 0)
    if bad.any():
        k = int(bad.argmax())
        raise ValueError(
            f"quantity row {k + 1} is {float(quantities[k])!r}, expected a finite number of zero "
            "or more; a request is a weighted quote, not a spread or a net position"
        )
    if not (quantities > 0).any():
        raise ValueError(
            "quantity is zero on every row, expected at least one positive; a request of nothing "
            "has no price"
        )
    held = np.array(quantities, dtype=np.float64)
    held.setflags(write=False)
    return held


def _the_component_quantities(
    quantity_per: QuantityPer,
    quantity: NDArray[np.float64],
    occurrence: NDArray[np.intp],
    start: NDArray[np.datetime64],
    end: NDArray[np.datetime64],
) -> NDArray[np.float64]:
    """Each component's quantity by the template's basis: its row's entered quantity per month,
    or per period, a window's total, the entered column itself by reference where every row is
    one component and one gather where a row spans months; and the row's quantity times the
    component's calendar days, weekends and holidays included, per calendar day, formed once
    here and checked finite where it is made, since a finite quantity times its days can outrun
    the largest number; frozen."""
    match quantity_per:
        case QuantityPer.MONTH | QuantityPer.PERIOD:
            if occurrence.size == quantity.size:  # every row one component: the column itself
                return quantity
            held = quantity[occurrence]
            held.setflags(write=False)
            return held
        case QuantityPer.CALDAY:
            days = ((end - start).astype(np.int64) + 1).astype(np.float64)
            with np.errstate(over="ignore"):  # the overflow is this rule's to catch, below
                component = quantity[occurrence] * days
            outrun = ~np.isfinite(component)
            if outrun.any():
                k = int(outrun.argmax())
                row = int(occurrence[k])
                raise ValueError(
                    f"quantity row {row + 1} is {float(quantity[row])!r} per calendar day, "
                    f"expected a finite quantity for the period; times its {int(days[k])} days it "
                    "outruns the largest number"
                )
            component.setflags(write=False)
            return component
        case _:
            assert_never(quantity_per)


def _the_dates(ticket: FieldValues) -> NDArray[np.datetime64]:
    """The request's own payment days, a date on every row: the column as the seam typed it, a
    date or a text per cell, a text, which would be a rule, refused by its first row, since a
    request's rows pay on dates and a rule is the template's to hold; copied once."""
    entered = ticket.dates_or_texts("payment_day")
    if not entered.is_date.all():
        k = int(np.flatnonzero(~entered.is_date)[0])
        text = entered.texts[int(np.count_nonzero(~entered.is_date[:k]))]
        raise ValueError(
            f"payment_day row {k + 1} is {text!r}, expected a date; a request's rows pay on "
            "dates, and a rule is the template's to hold"
        )
    return np.array(entered.dates, dtype="datetime64[D]")
