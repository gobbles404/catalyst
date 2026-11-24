"""A quote: one whole-period indicative fixed price for a contract or strip on one market from a
quote template's static terms, template-based-quoting.md, and since dated-quotes.md one for the
days between two dates, the trade-month window among them. The period is resolved against the
market's schedule by request.py's one resolution under the template's frequency, a label's or a
span's months under monthly and the span's one window under onetime; each component's
observations are made by the template's method through the batch pipeline's own builders, its
quantity one or its calendar days and its payment day the template's; the request is priced at
once on the market by request.py's calculation, every component of the period in both sums
whether its payment has passed or not, the agreed full-period convention: a paid month at its
realized price and factor one, never dropped, renormalized or turned into a balance. Since
fit-to-curve-price.md every quote says which price it asks for, flat or ftc, the one fixed price
or the fit-to-curve one, the months' own prices averaged by quantity alone. Nothing is
booked, retained or reported. docs/library/quoting/quote.md and
docs/library/quoting/quote-by-dates.md are the pages."""

from collections.abc import Callable

import numpy as np

from catalyst.globals.discount_curve_set import DiscountCurveSet
from catalyst.index_definitions.periods import balance_of, end_date, start_date
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.market.market import Market
from catalyst.quoting.request import (
    Pricing,
    Terms,
    by_the_month,
    priced,
    pricing_of,
    the_curve,
    the_frequency,
    the_method,
    the_nearby,
    the_period,
    the_request,
    the_terms,
)
from catalyst.quoting.template import QuoteTemplate
from catalyst.trades.terms import trade_schedule_of

Span = tuple[np.datetime64, np.datetime64]


def quote(
    market: Market,
    contract_code: str,
    template: QuoteTemplate,
    pricing: str,
    curve_set: DiscountCurveSet | None,
    counter: WorkCounter,
) -> float:
    """The price of the period on the market under the template's terms, the rules in this
    order, the first failure being the message: since fit-to-curve-price.md the pricing is
    flat or ftc, read once; the template holds every term a completed quote requires and none
    it refuses, and the terms agree; the template's frequency is monthly, since a label names
    months and _QuoteByDates prices a window, and its basis month or calday, the kernel's rule;
    the collection is supplied for a bilateral quote and left out for a cleared one, under
    either pricing, the key bound to the curve of that exact name and the curve starting on the
    valuation day; the market's index takes the terms, a futures index the four methods and a
    published index asian, or lastday on a month of one print, with a financial settlement, a
    physical settlement lastday alone; the
    period, a label or since balance-of-period-quotes.md the balance of one from the valuation
    day, every month of it a contract of the schedule; the observations and their pricing
    contracts by the pipeline's rules; a financial quote's payments, the template's date on
    every month or its rule's day from each month's last observation, after each month's last
    observation, within the sheet's calendar; then the request priced on the market, its
    calendar rows, a fixed day's price off the history and a live day's off the market's quotes,
    a physical quote's contracts not yet expired, and under flat the selected curve covering
    every payment after the valuation day, which ftc, reading no factor, asks of no curve."""
    chosen = pricing_of(pricing)
    terms = the_terms(template, counter)
    by_the_month(terms, "a quote by contract code")
    return _priced(
        market,
        terms,
        chosen,
        curve_set,
        lambda as_of: _the_span(contract_code, as_of),
        lambda: f"contract_code is {contract_code!r}",
        counter,
        dated=balance_of(contract_code) is not None,
    )


def quote_by_dates(
    market: Market,
    start: np.datetime64,
    end: np.datetime64,
    template: QuoteTemplate,
    pricing: str,
    curve_set: DiscountCurveSet | None,
    counter: WorkCounter,
) -> float:
    """The price of the days from start to end on the market under the template's terms, since
    dated-quotes.md, the quote's rules in the quote's order but for the period, which the two
    dates give: the pricing flat or ftc, as a quote's; the terms complete and agreeing; the
    frequency with the terms it stands under,
    the kernel's rule, a onetime period on a futures index alone, financially settled, under
    asian and in a quantity of period or calday, and a monthly one in a quantity of month or
    calday; the collection as the route takes it; the index taking the terms; then the period,
    the end on or after the start, under monthly the days split at month ends into components,
    the first and the last month clipped to the days given, every month a contract of the
    schedule, as a dated booking row is split, and under onetime the one window whatever months
    it crosses, priced by the contract of its first day and the contracts the calendar gives its
    days, a window opening after the last day the schedule's contracts price refused; the
    observations, the payments, from the window's final observation under onetime, and the
    request priced as a quote's is. Under monthly the same dates quote a dated strip, each month
    its own average; under onetime one average over every pricing day of the window, one
    component, whose price is the same under either pricing."""
    chosen = pricing_of(pricing)
    terms = the_terms(template, counter)
    return _priced(
        market,
        terms,
        chosen,
        curve_set,
        lambda _: _the_dates(start, end),
        lambda: f"start_date is {start} and end_date {end}",
        counter,
        dated=True,
    )


def _priced(
    market: Market,
    terms: Terms,
    pricing: Pricing,
    curve_set: DiscountCurveSet | None,
    span: Callable[[np.datetime64], Span],
    period_of: Callable[[], str],
    counter: WorkCounter,
    dated: bool,
) -> float:
    """The steps a label and two dates share once the pricing and the terms are read: the
    frequency's rules, the curve, the index's kind, the span read with the valuation day,
    resolved under the frequency and priced under the pricing. `dated` says the span is a
    window of dates, two dates or the balance of a label, which runs from the valuation day,
    and not the months a label names: on a published index a window takes the prints dated
    in it and a label the prints whose rows name its months."""
    calendar = market.market_history.calendar
    index = calendar.index
    as_of = calendar.valuation_date.as_of
    the_frequency(terms, index.kind, "the quote")
    the_nearby(terms, index.kind, "the quote")
    curve = the_curve(terms, curve_set, as_of, counter)
    schedule = trade_schedule_of(index)
    the_method(terms, schedule)
    first_day, last_day = span(as_of)
    period = the_period(first_day, last_day, terms.frequency, schedule, period_of, counter)
    request = the_request(index, schedule, terms, period, counter, dated)
    return priced(request, market, curve, pricing, counter)


# --- the span ------------------------------------------------------------------------------------


def _the_span(contract_code: str, as_of: np.datetime64) -> Span:
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


def _the_dates(start: np.datetime64, end: np.datetime64) -> Span:
    """The two dates as given, the end on or after the start, as a dated booking row's are."""
    if end < start:
        raise ValueError(f"end_date is {end}, expected a day on or after start_date, {start}")
    return start, end
