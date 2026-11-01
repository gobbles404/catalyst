"""What a quote prices and how, defined once for the quote and the request for quote,
template-based-quoting.md, rfq-quoting.md and dated-quotes.md: the terms a quote template must
hold for a completed quote, the curve a bilateral quote discounts on, the terms against the
index's kind and the frequency's rules over them, the period a span of days resolves to under
the template's frequency, the months of a label or two dates under monthly and the one window
under onetime, the request made from it, the payments a template's day or rule gives the
components, and the pricing of a resolved request on a market:

    P_i = sum(weight_ij * price_ij)      each component's observations' weighted prices
    D_i = 1 cleared; 1 bilateral with payment_i <= as_of; curve(payment_i) otherwise
    K   = sum(q_i D_i P_i) / sum(q_i D_i)

in the index's quote units, every component in both sums whether its payment has passed or
not, the agreed full-period convention. A quote resolves its period to a request on each call
and prices it at once, quote.py; a request for quote retains one and prices it on each market,
rfq.py. docs/library/quoting/quote.md owns the calculation, docs/library/quoting/quote-by-dates.md
the dated quote and docs/library/quoting/rfq.md the request."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.globals.payments import curve_starts_on, factors_on
from goosedove.index_definitions.contract_codes import schedule_months
from goosedove.index_definitions.date_offsets import Instruction, shift_days
from goosedove.index_definitions.futures_schedule import FuturesSchedule
from goosedove.index_definitions.holiday_calendar import HolidayCalendar
from goosedove.index_definitions.iferc_schedule import IfercSchedule
from goosedove.index_definitions.index import Index
from goosedove.index_definitions.kind import Kind, named
from goosedove.index_definitions.sheet_days import SHEET_FIRST_DAY, SHEET_LAST_DAY
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.instruments.definitions import NONE
from goosedove.market.market import Market
from goosedove.quoting.template import QuoteTemplate
from goosedove.trades.encoding import observation_references
from goosedove.trades.evaluation import CURVES_SELECTED, LIVE_PRICES_READ, PAYMENT_FACTORS_READ
from goosedove.trades.observations import Observations, observed
from goosedove.trades.preparation import FIXINGS_READ, calendar_rows
from goosedove.trades.resolution import (
    PAYMENT_RULES_READ,
    PAYMENT_SHIFTS,
    SCHEDULE_CODES_READ,
    contract_days,
    last_days,
    schedule_rows,
    window_rows,
)
from goosedove.trades.schedule_methods import METHODS, ScheduleMethod
from goosedove.trades.template import (
    DayOrRule,
    payment_rule_of,
    quantity_per_of,
    route_of,
    schedule_method_of,
    settlement_frequency_of,
    settlement_of,
)
from goosedove.trades.terms import (
    BASES,
    FREQUENCIES,
    QuantityPer,
    Route,
    Settlement,
    SettlementFrequency,
    frequency_rules,
    month_bounds,
    payments_after_observations,
    period_words,
)

# The work a quote and a request report, beside the pipeline's own names where the fact is the
# same: the schedule's codes read, the fixings and the live prices read, the payment rules and
# shifts, the curve selected and the payment factors read.
TEMPLATE_FIELDS_READ: Final = "template_fields_read"  # the template's values read for the terms
MONTHS_RESOLVED: Final = "months_resolved"  # the months resolved to schedule rows
WINDOWS_RESOLVED: Final = "windows_resolved"  # the windows resolved to the contract pricing their
# first day, since dated-quotes.md
OBSERVATIONS_MADE: Final = "observations_made"  # observations made over the components
PAYMENT_DAYS_MADE: Final = "payment_days_made"  # one per month of a financial quote or request
PRICE_REDUCTIONS: Final = "price_reductions"  # the reductions formed: the months' prices,
# the largest weight's exponent, the weights and the price


@dataclass(frozen=True, slots=True)
class Terms:
    """The template's terms as a quote reads them: the five codes as their enums, since
    dated-quotes.md the frequency among them, monthly or onetime, read and held to the kernel's
    rules by the_frequency; for a financial settlement the payment day, since
    payment-day-date-or-rule.md a date as entered or a rule read whole with its text, the other
    None, and both None for a request paying on its own dates under a template without one,
    rfq-quoting.md, and the calendar; and the curve key on the bilateral route."""

    route: Route
    settlement: Settlement
    method: ScheduleMethod
    quantity_per: QuantityPer
    frequency: SettlementFrequency
    payment_day: np.datetime64 | None
    payment_rule: tuple[Instruction, ...] | None
    payment_rule_text: str | None
    payment_calendar: HolidayCalendar | None
    key: str | None


@dataclass(frozen=True, slots=True)
class Period:
    """The components a request prices, resolved once, since dated-quotes.md the one form a
    label's months, a span's months and a span's one window take: contract[k] the k-th
    component's row of the schedule, a month's own contract or the contract pricing a window's
    first day, read for nothing that prices; first[k] and last[k] the days it covers, a month's
    clipped to the span's; and window[k] whether it is a onetime window, named by its two dates
    where a month is named by its code."""

    contract: NDArray[np.intp]
    first: NDArray[np.datetime64]
    last: NDArray[np.datetime64]
    window: NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class Request:
    """What a quote prices, resolved once and read for nothing else: the index and its schedule,
    the terms, the period, each component a row of the schedule with the days it covers, the
    observations the method gives the components and each observation's pricing reference, each
    component's quantity, one or its calendar days for a quote and the row's own quantity for a
    request for quote, which the price weighs with the factor at any scale, and for a financial
    settlement each component's payment day, None for a physical one, which pays on no day. No
    history, price, factor or valuation day: those are the market's, read when the request is
    priced."""

    index: Index
    schedule: FuturesSchedule | IfercSchedule
    terms: Terms
    period: Period
    observations: Observations
    references: NDArray[np.intp]
    quantity: NDArray[np.float64]
    payment_date: NDArray[np.datetime64] | None

    def component(self, k: int) -> str:
        """The k-th component as a refusal names it: a month's contract code, the schedule's
        spelling, or a window's two dates."""
        return component_words(self.schedule.codes, self.period, k)


def component_words(codes: tuple[str, ...], period: Period, k: int) -> str:
    """The k-th component of a period in words, the one form period_words gives every reader of
    a period: its contract's code, `F27`, or a window's two dates, `2026-05-26 to 2026-06-25`."""
    at = slice(k, k + 1)
    return str(
        period_words(
            codes, period.contract[at], period.window[at], period.first[at], period.last[at]
        )[0]
    )


# --- the terms ------------------------------------------------------------------------------------


def the_terms(
    template: QuoteTemplate, counter: WorkCounter, request_dates: bool | None = None
) -> Terms:
    """The template's terms, complete for a quote: each field the definition always requires of a
    quote present, the four codes read as their enums, a physical settlement on the cleared route
    alone, and each conditional field present exactly when its condition holds, the condition
    the definition's own words; then the payment day for a financial settlement, a date as it is
    or a rule read whole, with its calendar, and the key for a bilateral route. For a request for
    quote, rfq-quoting.md, request_dates says whether the request pays on its own dates: with
    them the template's payment_day is read if held and not required, the calendar required
    still; without them a missing payment_day is refused naming the request's column as the
    other source. Work: the template's values, each read once."""
    values = template.values
    fields = template.instrument.fields
    for field in fields:
        if field.quote_required and field.name not in values:
            raise ValueError(f"{field.name} is missing, expected it in the quote template")
    route = route_of("route", _text(values, "route"))
    settlement = settlement_of("settlement_method", _text(values, "settlement_method"))
    method = schedule_method_of("schedule_method", _text(values, "schedule_method"))
    quantity_per = quantity_per_of("quantity_per", _text(values, "quantity_per"))
    frequency = settlement_frequency_of(
        "settlement_frequency", _text(values, "settlement_frequency")
    )
    if route is Route.BILATERAL and settlement is Settlement.PHYSICAL:
        raise ValueError(
            "settlement_method is 'physical', expected 'financial' with route = bilateral; a "
            "physical delivery has no payment to discount"
        )
    _the_conditions(template, route, settlement, request_dates)
    counter.hit(TEMPLATE_FIELDS_READ, len(values))
    payment_day = rule_text = rule = payment_calendar = None
    if settlement is Settlement.FINANCIAL:
        if "payment_day" in values:
            entered = cast(DayOrRule, values["payment_day"])
            payment_day = entered.day
            if entered.rule is not None:
                rule_text = entered.rule
                rule = payment_rule_of("payment_day", rule_text)
        payment_calendar = cast(HolidayCalendar, values["payment_holiday_calendar"])
    key = _text(values, "discount_curve_key") if route is Route.BILATERAL else None
    return Terms(
        route,
        settlement,
        method,
        quantity_per,
        frequency,
        payment_day,
        rule,
        rule_text,
        payment_calendar,
        key,
    )


def by_the_month(terms: Terms, who: str) -> None:
    """A quote by contract code prices by the month, its label naming months, and so does a
    request for quote until dated-quotes.md's second slice: a template holding onetime is refused
    by name, since a label's span as one average is not what the label says and _QuoteByDates
    prices the window two dates name."""
    if terms.frequency is SettlementFrequency.ONETIME:
        raise ValueError(
            f"settlement_frequency is 'onetime', expected 'monthly'; {who} prices by the month, "
            "and _QuoteByDates prices a onetime period across two dates"
        )


def the_frequency(terms: Terms, kind: Kind, who: str) -> None:
    """The template's frequency with the terms it stands under, since dated-quotes.md the
    kernel's one rule, frequency_rules, over the template's one set of terms on one index,
    named as the quote or the request in a refusal: a onetime period on a futures index alone,
    financially settled, under the asian method and in a quantity of period or calday; under
    monthly a quantity of month or calday, period being a window's total."""
    frequency_rules(
        np.array([FREQUENCIES.index(terms.frequency)], dtype=np.intp),
        np.array([BASES.index(terms.quantity_per)], dtype=np.intp),
        np.array([METHODS.index(terms.method)], dtype=np.intp),
        terms.settlement,
        kind,
        False,
        lambda _: who,
    )


def _the_conditions(
    template: QuoteTemplate, route: Route, settlement: Settlement, request_dates: bool | None
) -> None:
    """Each conditional field of a quote present exactly when its condition holds, the condition
    the definition's own words over the route and the settlement; a request's own dates stand in
    for the template's payment_day, and a request without them is told of that other source."""
    values = template.values
    facts = {"route": route.value, "settlement_method": settlement.value}
    for field in template.instrument.fields:
        condition = field.quote_required_when
        if condition == NONE:
            continue
        fact, _, value = condition.partition(" = ")
        if facts[fact] != value:
            if field.name in values:
                raise ValueError(
                    f"{field.name} is {_shown(values[field.name])}, expected none in the quote "
                    f"template unless {condition}"
                )
            continue
        if field.name in values or (field.name == "payment_day" and request_dates is True):
            continue
        other = (
            ", or payment_dates with the request"
            if field.name == "payment_day" and request_dates is False
            else ""
        )
        raise ValueError(
            f"{field.name} is missing, expected it in the quote template when {condition}{other}"
        )


def _text(values: Mapping[str, object], name: str) -> str:
    return cast(str, values[name])


def _shown(value: object) -> str:
    """A template's value named in a refusal: text in quotes, a payment day as its day or its
    rule in quotes, an object by its kind."""
    if isinstance(value, DayOrRule):
        return repr(value.rule) if value.day is None else str(value.day)
    return repr(value) if isinstance(value, str) else named(value)


def the_curve(
    terms: Terms, curve_set: DiscountCurveSet | None, as_of: np.datetime64, counter: WorkCounter
) -> DiscountCurve | None:
    """The curve a bilateral quote discounts on, bound once from the collection by the template's
    key, exactly, case and all, no fallback to the first curve, a collection of one included,
    and starting on the valuation day, never rebased; the collection is required with a bilateral
    quote and refused with a cleared one, which discounts nothing. Its coverage is checked once
    the payment days are known, and no other curve of the collection is read."""
    match terms.route:
        case Route.CLEARED:
            if curve_set is not None:
                raise ValueError(
                    f"discount_curve_set is a collection of {len(curve_set.curves)} "
                    f"{'curve' if len(curve_set.curves) == 1 else 'curves'}, expected none with "
                    "route = cleared; a cleared quote discounts nothing"
                )
            return None
        case Route.BILATERAL:
            key = cast(str, terms.key)  # bilateral: the terms' rule
            if curve_set is None:
                raise ValueError(
                    f"discount_curve_set is missing, expected a collection of discount curves "
                    f"holding {key!r} with route = bilateral, whose payments it discounts"
                )
            curve = next((each for each in curve_set.curves if each.name == key), None)
            if curve is None:
                raise ValueError(
                    f"discount_curve_key {key!r} names no curve of the collection, which holds "
                    f"{_listed(curve_set.names)}; expected a curve of that name"
                )
            counter.hit(CURVES_SELECTED, 1)
            curve_starts_on(curve, as_of)
            return curve
        case _:
            assert_never(terms.route)


def _listed(names: tuple[str, ...]) -> str:
    quoted = [repr(name) for name in names]
    if len(quoted) == 1:
        return quoted[0]
    return f"{', '.join(quoted[:-1])} and {quoted[-1]}"


def the_method(terms: Terms, schedule: FuturesSchedule | IfercSchedule) -> None:
    """The terms against the index's kind, the batch's rules: on an IFERC index a financial
    settlement and lastday, the month's index being published once; on a futures index a physical
    settlement with lastday alone, the other three methods settling on a price other than the
    expiry's settle."""
    method = terms.method
    match schedule:
        case IfercSchedule():
            if terms.settlement is Settlement.PHYSICAL:
                raise ValueError(
                    "settlement_method is 'physical', expected 'financial' on an IFERC index; an "
                    "IFERC basis future is cash settled on its month's published index"
                )
            if method is not ScheduleMethod.LASTDAY:
                raise ValueError(
                    f"schedule_method is {method.value!r}, expected 'lastday' on an IFERC index; "
                    "an IFERC month has one index, published once"
                )
        case FuturesSchedule():
            if terms.settlement is Settlement.FINANCIAL:
                return
            match method:
                case ScheduleMethod.LASTDAY:
                    return
                case ScheduleMethod.ASIAN:
                    settled = "the average of its month's pricing days"
                case ScheduleMethod.LAST3DAY:
                    settled = "the average of its last three pricing days"
                case ScheduleMethod.PENULTIMATE:
                    settled = "the business day before its contract's expiry"
                case _:
                    assert_never(method)
            raise ValueError(
                f"settlement_method is 'physical', expected 'financial' with the {method.value} "
                f"method; {'an' if method is ScheduleMethod.ASIAN else 'a'} {method.value} future "
                f"is cash settled on {settled}"
            )
        case _:
            assert_never(schedule)


# --- the period and the request -------------------------------------------------------------


def the_period(
    first_day: np.datetime64,
    last_day: np.datetime64,
    frequency: SettlementFrequency,
    schedule: FuturesSchedule | IfercSchedule,
    period_of: Callable[[], str],
    counter: WorkCounter,
) -> Period:
    """The components of the days from first_day to last_day under the frequency, since
    dated-quotes.md the one resolution a quote's label and a quote's two dates share. Under
    monthly the span is split at month ends, the first and the last month clipped to the days
    the span covers and a month between them whole, as the resolution splits a dated row; every
    schedule code is read for its month, and a month the schedule lacks is refused by name in
    the period's words. Under onetime the span is one component, the window, whatever months it
    crosses, its schedule row the contract pricing its first day by window_rows, the one search
    a booking's windows take, a window opening after the last day the schedule's contracts price
    refused in the period's words. Work: the codes read and the months resolved, or the window
    resolved."""
    match frequency:
        case SettlementFrequency.MONTHLY:
            first_month = int(first_day.astype("datetime64[M]").astype(np.int64))
            last_month = int(last_day.astype("datetime64[M]").astype(np.int64))
            month = np.arange(first_month, last_month + 1, dtype=np.int64)
            months = schedule_months(schedule)
            counter.hit(SCHEDULE_CODES_READ, len(schedule.codes))
            contract = schedule_rows(
                months, month, np.arange(month.size, dtype=np.intp), lambda _: period_of()
            )
            counter.hit(MONTHS_RESOLVED, month.size)
            first, last = month_bounds(month)
            first[0] = max(first[0], first_day)
            last[-1] = min(last[-1], last_day)
            return Period(contract, first, last, np.zeros(month.size, dtype=np.bool_))
        case SettlementFrequency.ONETIME:
            opens = np.array([first_day], dtype="datetime64[D]")
            contract = window_rows(contract_days(schedule), opens, lambda _: period_of())
            counter.hit(WINDOWS_RESOLVED, 1)
            closes = np.array([last_day], dtype="datetime64[D]")
            return Period(contract, opens, closes, np.ones(1, dtype=np.bool_))
        case _:
            assert_never(frequency)


def the_request(
    index: Index,
    schedule: FuturesSchedule | IfercSchedule,
    terms: Terms,
    period: Period,
    counter: WorkCounter,
) -> Request:
    """A quote's request from its resolved period, the steps a label and two dates share: the
    observations by the template's method over each component's days, a window's over the whole
    of it, the quote named in a refusal and a component by what it is booked under, its code or
    `the window`; each observation's pricing reference by the pipeline's rules, a component named
    by its code or its two dates; each component's quantity, one or its calendar days; and a
    financial quote's payment days from the template, after each component's last observation.
    Work: the observations made, and the payments' as the_payments reports it."""
    n = period.contract.size
    codes = schedule.codes

    def booked(k: int) -> str:
        return "the window" if period.window[k] else codes[int(period.contract[k])]

    def component(k: int) -> str:
        return component_words(codes, period, k)

    method = np.full(n, METHODS.index(terms.method), dtype=np.intp)
    observations = observed(
        method,
        index,
        period.contract,
        period.first,
        period.last,
        lambda _: "the quote",
        booked=booked,
    )
    counter.hit(OBSERVATIONS_MADE, observations.component.size)
    references = observation_references(
        schedule, index.holiday_calendar, observations, period.contract, method, component
    )
    return Request(
        index,
        schedule,
        terms,
        period,
        observations,
        references,
        _the_quantities(terms.quantity_per, period.first, period.last),
        the_payments(terms, observations, n, component, counter),
    )


def _the_quantities(
    quantity_per: QuantityPer, first: NDArray[np.datetime64], last: NDArray[np.datetime64]
) -> NDArray[np.float64]:
    """Each component's quantity: one for a quantity per month, or per period, the window's
    total; its calendar days, weekends and holidays included, for one per calendar day; a
    common scale cancels in the price, and one component's share is one whatever its quantity."""
    match quantity_per:
        case QuantityPer.MONTH | QuantityPer.PERIOD:
            return np.ones(first.size)
        case QuantityPer.CALDAY:
            return ((last - first).astype(np.int64) + 1).astype(np.float64)
        case _:
            assert_never(quantity_per)


# --- the payments ------------------------------------------------------------------------------


def the_payments(
    terms: Terms,
    observations: Observations,
    components: int,
    component: Callable[[int], str],
    counter: WorkCounter,
) -> NDArray[np.datetime64] | None:
    """A financial quote's payment days from its template, the batch's rules: since
    payment-day-date-or-rule.md the template's date on every month, as entered and never rolled,
    or each month's rule applied to its last observation day, the expiry under lastday on a
    futures index and the publication day on an IFERC one, instruction by instruction on the
    payment calendar, within the sheet's calendar; either way after each month's last
    observation, when the month's final price exists, the kernel's own rule for it, so a dated
    template serves any request whose last observation falls before its date; None for a
    physical settlement, which pays on no day. Work: the rule read and its instructions applied
    once over the months, none of either for a date, and the payment days made."""
    if terms.settlement is Settlement.PHYSICAL:
        return None
    anchors = last_days(observations, components)
    if terms.payment_day is not None:
        pays = np.full(components, terms.payment_day, dtype="datetime64[D]")
        counter.hit(PAYMENT_RULES_READ, 0)
        counter.hit(PAYMENT_SHIFTS, 0)
        counter.hit(PAYMENT_DAYS_MADE, components)
        payments_after_observations(pays, anchors, component)
        return pays
    rule = cast(tuple[Instruction, ...], terms.payment_rule)  # financial: the terms' rule
    shifted = shift_days(anchors, rule, terms.payment_calendar)
    counter.hit(PAYMENT_RULES_READ, 1)
    counter.hit(PAYMENT_SHIFTS, len(rule))
    counter.hit(PAYMENT_DAYS_MADE, components)
    strayed = shifted.strayed_at >= 0
    if strayed.any():
        k = int(strayed.argmax())
        step = int(shifted.strayed_at[k])
        at = "" if len(rule) == 1 else f" at instruction {step + 1}, {rule[step].text!r}"
        raise ValueError(
            f"payment_day is {terms.payment_rule_text!r}, counted from {anchors[k]} to "
            f"{shifted.strayed_to[k]}{at}, expected a payment day within the sheet's calendar, "
            f"{SHEET_FIRST_DAY} to {SHEET_LAST_DAY}"
        )
    pays = shifted.days
    payments_after_observations(pays, anchors, component)
    return pays


# --- the price ---------------------------------------------------------------------------------


def priced(
    request: Request, market: Market, curve: DiscountCurve | None, counter: WorkCounter
) -> float:
    """The price of a resolved request on a market, under the curve its terms bound: the
    observations' calendar rows on the market's calendar, a day before it refused by name; a
    fixed day's price off the history and a live day's off the market's quotes, each distinct
    live contract once; a physical request's contracts not yet expired; a financial one's
    payment factors, the selected curve covering every payment after the valuation day; then
    each month's price and its share. Each month's share is its weight, quantity times factor,
    over the weights' sum, and the price the shares' sum of the months' prices: a convex
    combination at each step, the observations' weights summing to one and the shares to one.
    The weights are formed from the mantissas and exponents of the quantities and the factors
    apart, shifted by one power of two from the largest weight's exponent, so that the largest
    weight is at least a quarter and none is above one: a power of two moves the exponent
    alone, so every share and price is as the plain products give it, while no quantity or
    factor the inputs allow, a quantity of 1e-100 beside 1e224 or a factor near the smallest
    number, which the curve accepts, drives a positive weight below the smallest number or the
    weights' sum above the largest; a month whose weight is negligible beside the largest
    counts for nothing, as it should, and one month's share is one whatever its factor."""
    calendar = market.market_history.calendar
    as_of = calendar.valuation_date.as_of
    observations = request.observations
    rows = calendar_rows(
        request.schedule,
        observations.date,
        calendar,
        lambda j: request.component(int(observations.component[j])),
    )
    is_fixed = calendar.is_fixed[rows]
    prices = _the_prices(market, request.references, rows, is_fixed, counter)
    n = request.period.contract.size
    monthly = np.bincount(observations.component, weights=observations.weight * prices, minlength=n)
    pays = request.payment_date
    if pays is None:
        _not_expired(observations, is_fixed, as_of, request.component)
        factor = np.ones(n)
    else:
        factor = _the_factors(curve, request.terms.key, pays, as_of, request.component, counter)
    # Each weight from the mantissas' product, a quarter to one for a month of something and
    # zero for a month of nothing, and the exponents' sum, shifted from the largest weight's: the
    # quantities hold at least one positive and the factors are all positive, so a largest
    # exists and the weights' sum is at least a quarter and at most the months.
    mantissa, exponent = np.frexp(request.quantity)
    scale, shift = np.frexp(factor)
    mantissa = mantissa * scale
    exponent = exponent + shift
    largest = exponent[mantissa > 0].max()
    weight = np.ldexp(mantissa, exponent - largest)
    share = weight / weight.sum()
    counter.hit(PRICE_REDUCTIONS, 4)
    return float((share * monthly).sum())


def _the_prices(
    market: Market,
    references: NDArray[np.intp],
    rows: NDArray[np.intp],
    is_fixed: NDArray[np.bool_],
    counter: WorkCounter,
) -> NDArray[np.float64]:
    """Each observation's price: a fixed day's settle off the history, which holds one for every
    fixed priced day of the calendar, one search over its rows; a live day's quote off the market
    for its pricing contract, each distinct contract asked for once, the market refusing one
    outside its coverage by name. A fixed observation asks nothing of the market, so an expired
    contract is never requested. Work: the fixings read, one per fixed observation, and the live
    prices read, one per distinct live contract."""
    history = market.market_history
    prices = np.empty(rows.size)
    fixed_rows = rows[is_fixed]
    prices[is_fixed] = history.fixing_prices[np.searchsorted(history.fixed_rows, fixed_rows)]
    counter.hit(FIXINGS_READ, fixed_rows.size)
    live = ~is_fixed
    distinct, inverse = np.unique(references[live], return_inverse=True)
    prices[live] = market.live_prices(distinct)[inverse]
    counter.hit(LIVE_PRICES_READ, distinct.size)
    return prices


def _not_expired(
    observations: Observations,
    is_fixed: NDArray[np.bool_],
    as_of: np.datetime64,
    component: Callable[[int], str],
) -> None:
    """A physical quote's contracts have not expired: under lastday, the one method a physical
    settlement takes, each month's one observation is its contract's expiry day, so a fixed
    observation is an expired contract, refused as the batch refuses one; the expiry day itself
    is live, as the calendar says."""
    if is_fixed.any():
        j = int(is_fixed.argmax())
        raise ValueError(
            f"{component(int(observations.component[j]))} expired {observations.date[j]}, before "
            f"valuation date {as_of}; a physical fixed_float after its expiry is not supported"
        )


def _the_factors(
    curve: DiscountCurve | None,
    key: str | None,
    pays: NDArray[np.datetime64],
    as_of: np.datetime64,
    component: Callable[[int], str],
    counter: WorkCounter,
) -> NDArray[np.float64]:
    """Each month's payment factor: one on a cleared quote, which discounts nothing; on a
    bilateral quote one for a payment on or before the valuation day, the quote's convention and
    no read of the curve, and the selected curve's factor on a later day, each distinct day read
    once, the first day past the curve refused with its month and the curve's range. Work: the
    factors read, one per distinct payment day after the valuation day."""
    if curve is None:
        return np.ones(pays.size)
    future = pays > as_of
    days = np.unique(pays[future])
    uncovered = days > curve.max_date
    if uncovered.any():
        d = int(uncovered.argmax())
        k = int((pays == days[d]).argmax())
        raise ValueError(
            f"the payment of {component(k)} on {days[d]} on {key} is past the discount curve "
            f"{curve.name!r}, which runs from {curve.start_date} to {curve.max_date}; expected "
            "every payment day after the valuation date covered"
        )
    read = factors_on(curve, days)
    counter.hit(PAYMENT_FACTORS_READ, days.size)
    factor = np.ones(pays.size)
    factor[future] = read[np.searchsorted(days, pays[future])]
    return factor
