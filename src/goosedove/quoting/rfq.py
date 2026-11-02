"""A request for quote, rfq-quoting.md: a saved quantity and payment schedule for quoting, one
index and one quote template's terms over aligned columns of contract months and quantities,
and either the template's payment days or a complete column of the request's own, which takes
precedence over the template's day for this request alone. Created once: the months resolved
against the index's schedule, the quantities read and formed by the template's basis, the
observations made by the template's method with their pricing references, the payment days
made from the template or taken from the request, exactly and never shifted, and the request's
pricing form retained, request.py's, with no history, price, factor or valuation day. Priced on
any market over the request's exact index by the quote's own calculation, each month at its
quantity, the market supplying the day, the history and the quotes on each call. Read back
with its entered and resolved facts and the source of its payment days, and nothing priced.
docs/library/quoting/rfq.md is the page."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.index_definitions.contract_codes import month_and_year, schedule_months
from goosedove.index_definitions.index import Index
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market
from goosedove.quoting.request import (
    MONTHS_RESOLVED,
    OBSERVATIONS_MADE,
    PAYMENT_DAYS_MADE,
    Request,
    priced,
    the_curve,
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
    last_days,
    schedule_rows,
)
from goosedove.trades.schedule_methods import METHODS
from goosedove.trades.terms import (
    QuantityPer,
    Settlement,
    month_bounds,
    payments_after_observations,
    trade_schedule_of,
)


class PaymentSource(Enum):
    """Where a financial request's payment days came from: the template's day or rule applied
    to each month, or the request's own column taken exactly."""

    TEMPLATE = "template"
    REQUEST = "request"


@dataclass(frozen=True, slots=True)
class Rfq:
    """The request as the sheet entered it and as it was resolved, read-only: the template by
    reference; the contract codes as typed, one month per row, in the order given; quantity[k]
    the row's entered quantity, finite and zero or more, at least one positive, in one common
    unit the caller chose; component_quantity[k] the quantity the template's basis gives the
    month, the entered one per month and the entered one times the month's calendar days per
    calendar day, formed once; the payment source, the template's or the request's, None for a
    physical request, which pays on no day; and the pricing form, the index, the terms, the
    months as schedule rows, the observations and their references, the quantities and the
    payment days, which every quote of the request reads and nothing rebuilds."""

    template: QuoteTemplate
    contract_codes: tuple[str, ...]
    quantity: NDArray[np.float64]
    component_quantity: NDArray[np.float64]
    payment_source: PaymentSource | None
    request: Request


def rfq(
    index: Index,
    contract_codes: Sequence[str],
    quantities: NDArray[np.float64],
    template: QuoteTemplate,
    payment_dates: NDArray[np.datetime64] | None,
    counter: WorkCounter,
) -> Rfq:
    """The one way to make an Rfq, the rules in this order, the first failure being the message:
    the template holds every term a completed quote requires, a missing payment_day stood in for
    by the request's dates and otherwise refused naming both sources; the index takes the terms
    as a quote's market would; the columns align, one quantity and, when given, one date per
    contract code, none empty; a physical request takes no dates; each code one month, a letter
    and two digits in either case, no strip or balance, a contract of the index's schedule, any
    order and a month more than once allowed; each quantity finite and zero or more, one at
    least positive, and under calday its product with the month's days finite; the observations
    by the template's method and their pricing references by the pipeline's rules; the payment
    days, the template's date or rule on each month, or the request's dates exactly, never
    shifted, each after its month's last observation. Work: the template's values read, the
    schedule's codes read, the months resolved, the observations made, the payment rule read and
    applied or none for the request's dates, and the payment days made; no market, fixing or
    factor is read."""
    dated = payment_dates is not None
    terms = the_terms(template, counter, dated)
    schedule = trade_schedule_of(index)
    the_method(terms, schedule)
    n = len(contract_codes)
    if n == 0:
        raise ValueError("contract_codes has 0 rows, expected one or more, a month per row")
    _aligned("quantities", quantities.size, n)
    if payment_dates is not None:
        _aligned("payment_dates", payment_dates.size, n)
        if terms.settlement is Settlement.PHYSICAL:
            raise ValueError(
                "payment_dates is supplied, expected none with settlement_method = physical; a "
                "physical delivery pays on no day"
            )
    month = _the_months(contract_codes)
    months = schedule_months(schedule)
    counter.hit(SCHEDULE_CODES_READ, len(schedule.codes))
    contract = schedule_rows(
        months,
        month,
        np.arange(n, dtype=np.intp),
        lambda k: f"contract_codes row {k + 1} is {contract_codes[k]!r}",
    )
    contract.setflags(write=False)
    counter.hit(MONTHS_RESOLVED, n)
    first, last = month_bounds(month)
    quantity = _the_quantities(quantities)
    component_quantity = _the_component_quantities(terms.quantity_per, quantity, first, last)
    codes = schedule.codes

    def component(k: int) -> str:
        return codes[int(contract[k])]

    method = np.full(n, METHODS.index(terms.method), dtype=np.intp)
    observations = observed(method, index, contract, first, last, lambda k: f"row {k + 1}")
    counter.hit(OBSERVATIONS_MADE, observations.component.size)
    references = observation_references(
        schedule, index.holiday_calendar, observations, contract, method, component
    )
    references.setflags(write=False)

    def named(k: int) -> str:
        return f"{component(k)} of row {k + 1}"

    if payment_dates is None:
        pays = the_payments(terms, observations, n, named, counter)
        source = None if pays is None else PaymentSource.TEMPLATE
    else:
        pays = np.array(payment_dates, dtype="datetime64[D]")
        counter.hit(PAYMENT_RULES_READ, 0)
        counter.hit(PAYMENT_SHIFTS, 0)
        counter.hit(PAYMENT_DAYS_MADE, n)
        payments_after_observations(pays, last_days(observations, n), named)
        pays.setflags(write=False)
        source = PaymentSource.REQUEST
    request = Request(
        index, schedule, terms, contract, observations, references, component_quantity, pays
    )
    return Rfq(template, tuple(contract_codes), quantity, component_quantity, source, request)


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


# --- the columns -------------------------------------------------------------------------------


def _aligned(name: str, size: int, rows: int) -> None:
    if size != rows:
        raise ValueError(f"{name} has {size} rows, expected {rows}, one per contract code")


def _the_months(contract_codes: Sequence[str]) -> NDArray[np.int64]:
    """Each row's month as numpy counts months, read by the one reader of a contract code, in
    either case; a strip, a balance or any other text is refused by its row in the reader's
    words, since a row of a request is one month with its own quantity and payment."""
    month = np.empty(len(contract_codes), dtype=np.int64)
    for k, code in enumerate(contract_codes):
        try:
            m, year = month_and_year(code)
        except ValueError as refusal:
            words = str(refusal)
            if not words.startswith("contract is "):
                raise
            raise ValueError(
                f"contract_codes row {k + 1} is {words[len('contract is ') :]}"
            ) from None
        month[k] = (year - 1970) * 12 + m - 1
    return month


def _the_quantities(quantities: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each quantity finite and zero or more, the first that is not refused by its row, and at
    least one positive, since a request of nothing has no price: a weighted quote, not a spread
    or a net position; copied once and frozen."""
    bad = ~np.isfinite(quantities) | (quantities < 0)
    if bad.any():
        k = int(bad.argmax())
        raise ValueError(
            f"quantities row {k + 1} is {float(quantities[k])!r}, expected a finite number of "
            "zero or more; a request is a weighted quote, not a spread or a net position"
        )
    if not (quantities > 0).any():
        raise ValueError(
            "quantities are all zero, expected at least one positive; a request of nothing has "
            "no price"
        )
    held = np.array(quantities, dtype=np.float64)
    held.setflags(write=False)
    return held


def _the_component_quantities(
    quantity_per: QuantityPer,
    quantity: NDArray[np.float64],
    first: NDArray[np.datetime64],
    last: NDArray[np.datetime64],
) -> NDArray[np.float64]:
    """Each month's quantity by the template's basis: the entered quantity per month, by
    reference, and the entered quantity times the month's calendar days, weekends and holidays
    included, per calendar day, formed once here and checked finite where it is made, since a
    finite quantity times its days can outrun the largest number; frozen."""
    match quantity_per:
        case QuantityPer.MONTH:
            return quantity
        case QuantityPer.CALDAY:
            days = ((last - first).astype(np.int64) + 1).astype(np.float64)
            with np.errstate(over="ignore"):  # the overflow is this rule's to catch, below
                component = quantity * days
            outrun = ~np.isfinite(component)
            if outrun.any():
                k = int(outrun.argmax())
                raise ValueError(
                    f"quantities row {k + 1} is {float(quantity[k])!r} per calendar day, expected "
                    f"a finite quantity for the month; times its {int(days[k])} days it outruns "
                    "the largest number"
                )
            component.setflags(write=False)
            return component
        case QuantityPer.PERIOD:  # refused by the terms, since onetime-averaging.md; never monthly
            raise ValueError(
                "quantity_per is 'period', expected 'month' or 'calday'; period is the total of "
                "a onetime period, which a request for quote does not price"
            )
        case _:
            assert_never(quantity_per)
