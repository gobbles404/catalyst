"""A quote: one whole-period indicative fixed price for a contract or strip on one market from a
quote template's static terms, template-based-quoting.md. The period's months are resolved
against the market's schedule, each month's observations made by the template's method through
the batch pipeline's own builders, and each observation priced off the history where its day has
fixed and off the day's quotes where it has not, each distinct live contract read once; then each
month's floating price P, its relative quantity q, one for the month or its calendar days, and
its payment factor D, one for a cleared quote and for a bilateral payment on or before the
valuation day, the template's curve's factor on a later one, make the price

    K = sum(q D P) / sum(q D)

in the index's quote units, every month of the period in both sums whether its payment has
passed or not, the agreed full-period convention: a paid month at its realized price and factor
one, never dropped, renormalized or turned into a balance. Nothing is booked, retained or
reported. docs/library/quoting/quote.md is the page."""

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
from goosedove.index_definitions.kind import named
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
    last_days,
    month_bounds,
    schedule_rows,
)
from goosedove.trades.schedule_methods import METHODS, ScheduleMethod
from goosedove.trades.template import (
    months_of,
    payment_rule_of,
    quantity_per_of,
    route_of,
    schedule_method_of,
    settlement_of,
)
from goosedove.trades.terms import QuantityPer, Route, Settlement, trade_schedule_of

# The work a quote reports, beside the pipeline's own names where the fact is the same: the
# schedule's codes read, the fixings and the live prices read, the payment rules and shifts,
# the curve selected and the payment factors read.
TEMPLATE_FIELDS_READ: Final = "template_fields_read"  # the template's values read for the terms
MONTHS_RESOLVED: Final = "months_resolved"  # the period's months resolved to schedule rows
OBSERVATIONS_MADE: Final = "observations_made"  # observations made over the months
PAYMENT_DAYS_MADE: Final = "payment_days_made"  # one per month of a financial quote
PRICE_REDUCTIONS: Final = "price_reductions"  # the sums formed: the months' prices, the
# weights and the price


@dataclass(frozen=True, slots=True)
class _Terms:
    """The template's terms as the quote reads them: the four codes as their enums, the payment
    rule read whole with its text and its calendar for a financial settlement, and the curve key
    on the bilateral route."""

    route: Route
    settlement: Settlement
    method: ScheduleMethod
    quantity_per: QuantityPer
    payment_rule: tuple[Instruction, ...] | None
    payment_rule_text: str | None
    payment_calendar: HolidayCalendar | None
    key: str | None


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
    lastday alone; every month of the period is a contract of the schedule; the observations,
    their pricing contracts and their calendar rows by the pipeline's rules, a fixed day's price
    off the history and a live day's off the market's quotes; a financial quote's payments after
    each month's last observation, within the sheet's calendar, and a physical quote's contracts
    not yet expired; and the selected curve covering every payment after the valuation day.
    The price is a convex combination of the months' prices, each a convex combination of
    its observations' prices, so no product or sum runs past the largest number a finite
    input stays within, and a factor as small as the curve allows scales nothing away."""
    terms = _the_terms(template, counter)
    calendar = market.market_history.calendar
    index = calendar.index
    as_of = calendar.valuation_date.as_of
    curve = _the_curve(terms, curve_set, as_of, counter)
    schedule = trade_schedule_of(index)
    _the_method(terms, schedule)
    codes = schedule.codes
    contract, first, last = _the_months(contract_code, schedule, counter)
    n = contract.size

    def component(k: int) -> str:
        return codes[int(contract[k])]

    method = np.full(n, METHODS.index(terms.method), dtype=np.intp)
    observations = observed(method, index, contract, first, last, component)
    counter.hit(OBSERVATIONS_MADE, observations.component.size)
    references = observation_references(
        schedule, index.holiday_calendar, observations, contract, method, component
    )
    rows = calendar_rows(
        schedule, observations.date, calendar, lambda j: component(int(observations.component[j]))
    )
    is_fixed = calendar.is_fixed[rows]
    prices = _the_prices(market, references, rows, is_fixed, counter)
    monthly = np.bincount(observations.component, weights=observations.weight * prices, minlength=n)
    quantity = _the_quantities(terms.quantity_per, first, last)
    pays = _the_payments(terms, observations, n, component, counter)
    if pays is None:
        _not_expired(observations, is_fixed, as_of, component)
        factor = np.ones(n)
    else:
        factor = _the_factors(curve, terms.key, pays, as_of, component, counter)
    # Each month's share is its weight, quantity times factor, over the weights' sum, and the
    # price the shares' sum of the months' prices: a convex combination at each step, the
    # observations' weights summing to one and the shares to one, so no product or sum runs past
    # the largest number a finite input stays within, and a factor as small as the curve allows,
    # positive by its rule, scales nothing away: one month's share is one whatever its factor.
    weight = quantity * factor
    share = weight / weight.sum()
    counter.hit(PRICE_REDUCTIONS, 3)
    return float((share * monthly).sum())


# --- the terms ------------------------------------------------------------------------------------


def _the_terms(template: QuoteTemplate, counter: WorkCounter) -> _Terms:
    """The template's terms, complete for a quote: each field the definition always requires of a
    quote present, the four codes read as their enums, a physical settlement on the cleared route
    alone, and each conditional field present exactly when its condition holds, the condition
    the definition's own words; then the payment rule read whole for a financial settlement, with
    its calendar, and the key for a bilateral route. Work: the template's values, each read
    once."""
    values = template.values
    fields = template.instrument.fields
    for field in fields:
        if field.quote_required and field.name not in values:
            raise ValueError(f"{field.name} is missing, expected it in the quote template")
    route = route_of("route", _text(values, "route"))
    settlement = settlement_of("settlement_method", _text(values, "settlement_method"))
    method = schedule_method_of("schedule_method", _text(values, "schedule_method"))
    quantity_per = quantity_per_of("quantity_per", _text(values, "quantity_per"))
    if route is Route.BILATERAL and settlement is Settlement.PHYSICAL:
        raise ValueError(
            "settlement_method is 'physical', expected 'financial' with route = bilateral; a "
            "physical delivery has no payment to discount"
        )
    facts = {"route": route.value, "settlement_method": settlement.value}
    for field in fields:
        condition = field.quote_required_when
        if condition == NONE:
            continue
        fact, _, value = condition.partition(" = ")
        if facts[fact] == value:
            if field.name not in values:
                raise ValueError(
                    f"{field.name} is missing, expected it in the quote template when {condition}"
                )
        elif field.name in values:
            raise ValueError(
                f"{field.name} is {_shown(values[field.name])}, expected none in the quote "
                f"template unless {condition}"
            )
    counter.hit(TEMPLATE_FIELDS_READ, len(values))
    rule_text = rule = payment_calendar = None
    if settlement is Settlement.FINANCIAL:
        rule_text = _text(values, "payment_time_lag")
        rule = payment_rule_of("payment_time_lag", rule_text)
        payment_calendar = cast(HolidayCalendar, values["payment_holiday_calendar"])
    key = _text(values, "discount_curve_key") if route is Route.BILATERAL else None
    return _Terms(route, settlement, method, quantity_per, rule, rule_text, payment_calendar, key)


def _text(values: Mapping[str, object], name: str) -> str:
    return cast(str, values[name])


def _shown(value: object) -> str:
    """A template's value named in a refusal: text in quotes, an object by its kind."""
    return repr(value) if isinstance(value, str) else named(value)


def _the_curve(
    terms: _Terms, curve_set: DiscountCurveSet | None, as_of: np.datetime64, counter: WorkCounter
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


def _the_method(terms: _Terms, schedule: FuturesSchedule | IfercSchedule) -> None:
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


# --- the period --------------------------------------------------------------------------------


def _the_months(
    contract_code: str, schedule: FuturesSchedule | IfercSchedule, counter: WorkCounter
) -> tuple[NDArray[np.intp], NDArray[np.datetime64], NDArray[np.datetime64]]:
    """The period's months as rows of the schedule, through the period grammar and the
    batch's own lookup, every schedule code read for its month, a month the schedule lacks
    refused by name; and each month's first and last calendar day, the days a whole-month
    component covers. Work: the codes read and the months resolved."""
    first_month, after = months_of("contract_code", contract_code)
    month = np.arange(first_month, after, dtype=np.int64)
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
    return contract, first, last


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


def _the_quantities(
    quantity_per: QuantityPer, first: NDArray[np.datetime64], last: NDArray[np.datetime64]
) -> NDArray[np.float64]:
    """Each month's relative quantity: one for a quantity per month, its calendar days, weekends
    and holidays included, for one per calendar day; a common scale cancels in the price."""
    match quantity_per:
        case QuantityPer.MONTH:
            return np.ones(first.size)
        case QuantityPer.CALDAY:
            return ((last - first).astype(np.int64) + 1).astype(np.float64)
        case _:
            assert_never(quantity_per)


# --- the payments ------------------------------------------------------------------------------


def _the_payments(
    terms: _Terms,
    observations: Observations,
    components: int,
    component: Callable[[int], str],
    counter: WorkCounter,
) -> NDArray[np.datetime64] | None:
    """A financial quote's payment days, the batch's rules: each month's rule applied to its last
    observation day, the expiry under lastday on a futures index and the publication day on an
    IFERC one, instruction by instruction on the payment calendar, within the sheet's calendar and
    after that last observation, when the month's final price exists; None for a physical
    settlement, which pays on no day. Work: the rule read, its instructions applied once over the
    months, and the payment days made."""
    if terms.payment_rule is None:
        return None
    anchors = last_days(observations, components)
    shifted = shift_days(anchors, terms.payment_rule, terms.payment_calendar)
    counter.hit(PAYMENT_RULES_READ, 1)
    counter.hit(PAYMENT_SHIFTS, len(terms.payment_rule))
    counter.hit(PAYMENT_DAYS_MADE, components)
    strayed = shifted.strayed_at >= 0
    if strayed.any():
        k = int(strayed.argmax())
        step = int(shifted.strayed_at[k])
        rule = terms.payment_rule
        at = "" if len(rule) == 1 else f" at instruction {step + 1}, {rule[step].text!r}"
        raise ValueError(
            f"payment_time_lag is {terms.payment_rule_text!r}, counted from {anchors[k]} to "
            f"{shifted.strayed_to[k]}{at}, expected a payment day within the sheet's calendar, "
            f"{SHEET_FIRST_DAY} to {SHEET_LAST_DAY}"
        )
    pays = shifted.days
    early = pays <= anchors
    if early.any():
        k = int(early.argmax())
        raise ValueError(
            f"{component(k)} pays on {pays[k]}, expected a day after its last observation, "
            f"{anchors[k]}, when its final price exists"
        )
    return pays


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
