"""A quote: one whole-period indicative fixed price for a contract or strip on one market from a
quote template's static terms, template-based-quoting.md. The period's months are resolved
against the market's schedule, each month's observations made by the template's method through
the batch pipeline's own builders, each month's quantity one or its calendar days and
its payment day the template's, the request priced at once on the market by request.py's
calculation, every month of the period in both sums whether its payment has passed or not, the
agreed full-period convention: a paid month at its realized price and factor one, never
dropped, renormalized or turned into a balance. Nothing is booked, retained or reported.
docs/library/quoting/quote.md is the page."""

from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.index_definitions.contract_codes import schedule_months
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.periods import end_date, start_date
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.market.market import Market
from goosedove.quoting.request import (
    MONTHS_RESOLVED,
    OBSERVATIONS_MADE,
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
from goosedove.trades.resolution import SCHEDULE_CODES_READ, schedule_rows
from goosedove.trades.schedule_methods import METHODS
from goosedove.trades.terms import QuantityPer, month_bounds, trade_schedule_of


def quote(
    market: Market,
    contract_code: str,
    template: QuoteTemplate,
    curve_set: DiscountCurveSet | None,
    counter: WorkCounter,
) -> float:
    """The price of the period on the market under the template's terms, the rules in this
    order, the first failure being the message: the template holds every term a completed quote
    requires and none it refuses, and the terms agree; the collection is supplied for a bilateral
    quote and left out for a cleared one, the key bound to the curve of that exact name and the
    curve starting on the valuation day; the market's index takes the terms, a futures index the
    four methods and an IFERC index lastday with a financial settlement, a physical settlement
    lastday alone; the period, a label or since balance-of-period-quotes.md the balance of one
    from the valuation day, every month of it a contract of the schedule; the observations and
    their pricing contracts by the pipeline's rules; a financial quote's payments, the template's
    date on every month or its rule's day from each month's last observation, after each month's
    last observation, within the sheet's calendar; then the request priced on the market, its
    calendar rows, a fixed day's price off the history and a live day's off the market's quotes,
    a physical quote's contracts not yet expired, and the selected curve covering every payment
    after the valuation day."""
    terms = the_terms(template, counter)
    calendar = market.market_history.calendar
    index = calendar.index
    as_of = calendar.valuation_date.as_of
    curve = the_curve(terms, curve_set, as_of, counter)
    schedule = trade_schedule_of(index)
    the_method(terms, schedule)
    codes = schedule.codes
    contract, first, last = _the_period(contract_code, schedule, as_of, counter)
    n = contract.size

    def component(k: int) -> str:
        return codes[int(contract[k])]

    method = np.full(n, METHODS.index(terms.method), dtype=np.intp)
    observations = observed(method, index, contract, first, last, lambda _: "the quote")
    counter.hit(OBSERVATIONS_MADE, observations.component.size)
    references = observation_references(
        schedule, index.holiday_calendar, observations, contract, method, component
    )
    request = Request(
        index,
        schedule,
        terms,
        contract,
        observations,
        references,
        _the_quantities(terms.quantity_per, first, last),
        the_payments(terms, observations, n, component, counter),
    )
    return priced(request, market, curve, counter)


# --- the period --------------------------------------------------------------------------------


def _the_period(
    contract_code: str,
    schedule: FuturesSchedule | IfercSchedule,
    as_of: np.datetime64,
    counter: WorkCounter,
) -> tuple[NDArray[np.intp], NDArray[np.datetime64], NDArray[np.datetime64]]:
    """The period's months as rows of the schedule and the days each covers. The request is read
    through the readers the two date utilities use: a label's whole months whatever the day, and
    since balance-of-period-quotes.md a balance, BALZ26, from the later of the market's valuation
    day and the period's first day to its last, a period that has ended refused in the readers'
    own words. The span is split at month ends, the first and the last month clipped to the days
    the span covers and a month between them whole, as the resolution splits a dated row; every
    schedule code is read for its month, and a month the schedule lacks is refused by name.
    Work: the codes read and the months resolved, the balance's months among them."""
    first_day, last_day = _the_span(contract_code, as_of)
    first_month = int(first_day.astype("datetime64[M]").astype(np.int64))
    last_month = int(last_day.astype("datetime64[M]").astype(np.int64))
    month = np.arange(first_month, last_month + 1, dtype=np.int64)
    months = schedule_months(schedule)
    counter.hit(SCHEDULE_CODES_READ, len(schedule.codes))
    contract = schedule_rows(
        months,
        month,
        np.arange(month.size, dtype=np.intp),
        lambda _: f"contract_code is {contract_code!r}",
    )
    counter.hit(MONTHS_RESOLVED, month.size)
    first, last = month_bounds(month)
    first[0] = max(first[0], first_day)
    last[-1] = min(last[-1], last_day)
    return contract, first, last


def _the_span(contract_code: str, as_of: np.datetime64) -> tuple[np.datetime64, np.datetime64]:
    """The first and the last day the request covers, as util_StartDate and util_EndDate read a
    label with the valuation day: the grammar's refusal given again naming the argument as the
    sheet has it, and the balance's, which names the valuation day, in its own words."""
    try:
        return start_date(contract_code, as_of), end_date(contract_code, as_of)
    except ValueError as refusal:
        words = str(refusal)
        if not words.startswith("period is "):
            raise
        raise ValueError(f"contract_code{words[len('period') :]}") from None


def _the_quantities(
    quantity_per: QuantityPer, first: NDArray[np.datetime64], last: NDArray[np.datetime64]
) -> NDArray[np.float64]:
    """Each month's quantity: one for a quantity per month, its calendar days, weekends
    and holidays included, for one per calendar day; a common scale cancels in the price."""
    match quantity_per:
        case QuantityPer.MONTH:
            return np.ones(first.size)
        case QuantityPer.CALDAY:
            return ((last - first).astype(np.int64) + 1).astype(np.float64)
        case _:
            assert_never(quantity_per)
