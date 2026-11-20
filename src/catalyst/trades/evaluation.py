"""The prepared batch evaluated against its markets, one per leg, one today since
two-index-fixed-float.md: the quotes of the leg's live references read off its market once
each, gathered onto the live slots and multiplied by their exposure, one multiplication and
one sum for the live amount, which the unsettled offsets and set amounts
complete into the mark; the cash as the preparation settled it; the risk by reference on the
batch's own axis, the price sensitivity in the settlement currency and the delta in lots of the
index's reporting lot with its total, shared with the preparation that settled them, since no
tick changes them; and DV01, zero by the undiscounted cleared model. One snapshot for the batch
as a whole,
immutable, retained with everything that explains it, the dated live contributions among it;
the batch's booked reserves, the encoding's, carried by reference since #170. Since #176 a bilateral
batch takes a discount curve: its live contributions summed onto the payment groups, each unpaid
group's amount discounted on the curve's factor for its payment day, the mark their sum, DV01 the
analytic sensitivity of that mark to a rise of one basis point, and the lots each live slot holds
weighted by its group's factor, summed onto the references and the days and, by reference since
#186, onto the contract months and years, beside the nominal vectors the preparation shares,
and since #197 the cross-gamma, each live slot's discounted lots times -0.0001 times its
group's time fraction, the sensitivity of the discounted lots to a rise of one basis point in
the rates, summed onto the same four axes with its total; a cleared batch takes no curve and
is as it was. The record this makes, TradeResults, and the
selection of its saved views are results.py's; this module calculates and nothing else.
docs/library/trades/kernel.md is the page."""

from collections.abc import Sequence
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from catalyst.globals.discount_curve import DiscountCurve
from catalyst.globals.discount_curve_set import DiscountCurveSet, curve_named, no_curve_named
from catalyst.globals.payments import compensated, curve_starts_on, discounted, factors_on
from catalyst.instrumentation.work_counts import KERNEL, WorkCounter
from catalyst.market.market import Market
from catalyst.trades.contributions import CrossContribution, RateContribution
from catalyst.trades.display_axes import EarlyRisk, early_risk
from catalyst.trades.encoding import CurveAxes, PaymentAxes, group_label
from catalyst.trades.preparation import PreparedLeg, PreparedTrades, UnpaidPayments
from catalyst.trades.results import LegResults, TradeResults
from catalyst.trades.terms import Route, Settlement, named_trade

LIVE_PRICES_READ = "live_prices_read"  # quotes read off the market, one per live reference
# The bilateral path's counts, since #176: factors read off the curve, one per distinct unpaid
# payment day; unpaid groups discounted, each with its time fraction and its DV01; live slots
# weighted by their group's factor; and the reductions, of the discounted lots onto the
# references, the days, the months and the years, since #178 of the groups' DV01s onto the
# payment days, their months and their years, and since #197 of the slots' cross-gammas onto
# the references, the days, the months and the years.
PAYMENT_FACTORS_READ = "payment_factors_read"
GROUPS_VALUED = "groups_valued"
SLOTS_DISCOUNTED = "slots_discounted"
RISK_REDUCTIONS = "risk_reductions"
# Since named-curves-slice-3.md: the keys bound to curves, one per distinct key; and the
# cross-gamma's product over the slots, each slot once whatever the number of curves, counted
# so that a pass per curve would show.
CURVES_SELECTED = "curves_selected"
SLOTS_WEIGHTED = "slots_weighted"


def trade_results(
    prepared: PreparedTrades,
    markets: Sequence[Market],
    counter: WorkCounter,
    curve_set: DiscountCurveSet | None = None,
) -> TradeResults:
    """The one way to make TradeResults: the rules, checked once, in this order, the first failure
    being the message; then the quotes read, one kernel call, and the snapshot.

    The markets are one per leg of the trades, since two-index-fixed-float.md, matched to the
    legs by the history each is over whatever their order, else refused: one market more or
    fewer by the count, a market over none of the legs' histories or a second over one of them
    by its position. Each is over the history its leg was prepared against, the one object: a
    market over another history, a later valuation date or a corrected fixing, is refused, and
    the batch is prepared again outside, never silently here. Then the route, since #176. A
    cleared batch is undiscounted and takes no collection of curves: one supplied is refused
    by name, since its payments are margined as they come and discounting them would be a
    wrong number. A bilateral batch meets _the_curves' rules, since named-curves-slice-3.md:
    financial, since a physical delivery has no payment to discount; a collection supplied; each
    of its keys bound to the curve of that exact name in the collection; and each selected curve
    starting on the valuation date, a curve never being rebased, and covering every unpaid
    payment day of its own groups, a fixed-but-unpaid group and a group whose amount nets to
    nothing included, the first uncovered named by its contract, its day, its key and the
    curve's range.

    Each leg's market answers the quotes of the leg's live references in the leg's order, one
    per distinct contract, and refuses a contract past its coverage by name, as it does for
    every reader; the quotes are gathered onto the leg's live slots, and each slot's exposure
    times its reference's quote is its contribution, finite or refused by its slot and its
    quote since #190, reject-nonfinite-trade-arithmetic.md, before either route sums it. For a
    cleared batch each leg's live amount is its contributions' sum, the one reduction this
    route makes per leg, and the mark is the unsettled fixed legs, each leg's unsettled set
    amounts and each leg's live amount summed with Neumaier's compensation since
    two-index-one-price.md, the terms kept apart so that a small leg's dollar survives a strike
    that cancels the large leg's, finite or refused for the batch, since two finite floats add
    past the largest number without a word; the cash is the preparation's, the sensitivity, the
    nominal delta and its total each leg's preparation's, shared, the discounted vectors those same
    arrays, since nothing discounts, DV01 zero and no group vector kept; no value is a leg's
    since two-index-one-price.md, the payment being the trade's against its one fixed price. A
    bilateral batch is _discounted's. The reserves are the encoding's, by reference, summed
    when the batch was made and never here.

    Work: one kernel call, one quote per live reference of each leg, reported to the counter,
    and for a bilateral batch what _discounted reports; nothing of the encoding or the
    preparation is done again, and nothing per slot but the gather and the multiplication
    over the live ones.
    """
    terms = prepared.encoded.terms
    legs = prepared.legs
    if len(markets) != len(legs):
        raise ValueError(
            f"markets are {len(markets)}, expected {len(legs)}, one per leg of the trades"
        )
    matched = _the_markets(legs, markets)
    curves: tuple[DiscountCurve, ...] = ()
    match terms.route:
        case Route.CLEARED:
            if curve_set is not None:
                raise ValueError(
                    "discount_curve_set is supplied, expected none unless route = bilateral; a "
                    "cleared batch is undiscounted"
                )
        case Route.BILATERAL:
            curves = _the_curves(prepared, curve_set)
        case _:
            assert_never(terms.route)
    contributions: list[NDArray[np.float64]] = []
    quotes: list[NDArray[np.float64]] = []
    live_amounts: list[float] = []
    quotes_read = 0
    for leg, market in zip(legs, matched, strict=True):
        contribution, quote, live = _the_contributions(leg, market, not curves)
        contributions.append(contribution)
        quotes.append(quote)
        live_amounts.append(live)
        quotes_read += int(leg.live_references.size)
    counter.hit(KERNEL)
    counter.hit(LIVE_PRICES_READ, quotes_read)
    if curves:
        return _discounted(prepared, matched, curves, contributions, quotes, counter)
    currency = legs[0].encoded.leg.index.conventions.currency_unit
    # The cleared mark: the legs' live amounts, then the unsettled fixed legs and set amounts
    # added, each finite or refused for the batch; Python adds two finite floats past the
    # largest number without a word, so the rule looks.
    live = live_amounts[0]
    for amount in live_amounts[1:]:
        live = live + amount
    if not np.isfinite(live):
        raise ValueError(
            f"the batch has {live!r} of live amount in all, expected a finite amount of "
            f"{currency}; the live slots' contributions, each finite, sum past the largest number"
        )
    mark = float(compensated([prepared.offset_unsettled, *prepared.set_unsettled, *live_amounts]))
    if not np.isfinite(mark):
        raise ValueError(
            f"the batch has {mark!r} of mark in all, expected a finite amount of {currency}; its "
            "unsettled fixed legs, set amounts and live amount, each finite, sum past the largest "
            "number"
        )
    return TradeResults(
        prepared=prepared,
        legs=tuple(
            [
                _cleared_leg(leg, market, contribution, quote)
                for leg, market, contribution, quote in zip(
                    legs, matched, contributions, quotes, strict=True
                )
            ]
        ),
        route=terms.route,
        currency=currency,
        as_of=legs[0].history.calendar.valuation_date.as_of,
        mark=mark,
        cash=prepared.cash,
        dv01=0.0,  # the undiscounted model moves for no rate
        reserves=prepared.encoded.reserves,
        curves=(),
        # No payment group is valued and the DV01 has no dated axis.
        payment_amount=None,
        npv_by_group=None,
        dv01_by_group=None,
        payment_factor=None,
        rate_contributions=(),
    )


def _the_markets(legs: tuple[PreparedLeg, ...], markets: Sequence[Market]) -> tuple[Market, ...]:
    """Each leg's market among those given, in leg order: with one leg the one market, over the
    history the leg was prepared against, the one object, else refused; with two, since
    two-index-fixed-float.md, each market matched to the leg whose history it is over whatever
    the order given, a market over none of the legs' histories or a second over one of them
    refused by its position."""
    if len(legs) == 1:
        (market,) = markets
        if market.market_history is not legs[0].history:
            name = market.market_history.calendar.index.name
            raise ValueError(
                f"market is over another history of index {name!r}, "
                "expected the one the trades were prepared against"
            )
        return (market,)
    names = " and ".join(repr(leg.encoded.leg.index.name) for leg in legs)
    by_history: dict[int, tuple[int, Market]] = {}
    for k, market in enumerate(markets):
        history = market.market_history
        name = history.calendar.index.name
        if not any(history is leg.history for leg in legs):
            raise ValueError(
                f"market {k + 1} is over another history of index {name!r}, expected the ones "
                f"the trades were prepared against, of {names}"
            )
        seen = by_history.get(id(history))
        if seen is not None:
            raise ValueError(
                f"market {k + 1} is over the history of index {name!r} as market {seen[0] + 1} "
                "is, expected one market per history of the trades"
            )
        by_history[id(history)] = (k, market)
    return tuple([by_history[id(leg.history)][1] for leg in legs])


def _the_contributions(
    leg: PreparedLeg, market: Market, cleared: bool
) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """A leg's dated live contributions, each live slot's exposure times its reference's quote
    read off the leg's market, one gather and one multiplication, each finite or the first that
    is not refused by its slot and its quote; and for a cleared batch their sum, the leg's live
    amount, the one reduction the cleared route makes per leg, zero for a bilateral batch, whose
    route sums them by payment group. The arithmetic runs with numpy's flags down and the rules
    judge, since #190. The quotes come back beside them, frozen, since
    observation-prices-readback.md: one per live reference, the array the readback gathers each
    live slot's price from, read here once and never again."""
    quotes = market.live_prices(leg.live_references)
    currency = leg.encoded.leg.index.conventions.currency_unit
    with np.errstate(over="ignore", invalid="ignore"):
        dated_live_contribution = (
            leg.dated_live_exposure[leg.live_slot] * quotes[leg.reference_of_live_slot]
        )
        outrun = ~np.isfinite(dated_live_contribution)
        if outrun.any():
            i = int(outrun.argmax())
            quote = float(quotes[int(leg.reference_of_live_slot[i])])
            raise ValueError(
                f"{leg.encoded.named_slot(int(leg.live_slot[i]))}, quoted at {quote!r}, "
                f"has {float(dated_live_contribution[i])!r} of live contribution, expected a "
                f"finite amount of {currency}; its exposure times the quote outruns the largest "
                "number"
            )
        live = float(dated_live_contribution.sum()) if cleared else 0.0
    dated_live_contribution.setflags(write=False)
    quotes.setflags(write=False)
    return dated_live_contribution, quotes, live


def _cleared_leg(
    leg: PreparedLeg,
    market: Market,
    contribution: NDArray[np.float64],
    quote: NDArray[np.float64],
) -> LegResults:
    """A cleared leg's results: nothing discounts, so the valuation-adjusted risk is the nominal
    risk itself, the preparation's arrays by reference, no rate moves the lots, the known zero,
    no contribution and no buffer."""
    conventions = leg.encoded.leg.index.conventions
    return LegResults(
        prepared=leg,
        market=market,
        dated_live_contribution=contribution,
        quote=quote,
        contracts=leg.encoded.references,
        price_sensitivity=leg.price_sensitivity,
        price_sensitivity_unit=(
            f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
            f"{conventions.quote_quantity_unit}"
        ),
        nominal_delta=leg.nominal_delta,
        nominal_delta_total=leg.nominal_delta_total,
        lot_unit=leg.encoded.leg.reporting_lot.words,
        delta=leg.nominal_delta,
        delta_total=leg.nominal_delta_total,
        discounted_price_sensitivity=leg.price_sensitivity,
        discounted_daily_lots=leg.daily_lots,
        discounted_monthly_lots=leg.monthly_lots,
        discounted_yearly_lots=leg.yearly_lots,
        early_delta=leg.early_nominal,  # the same lots: worded as the delta when asked for
        cross_gamma_total=0.0,
        cross_contributions=(),
    )


def _the_curves(
    prepared: PreparedTrades, curve_set: DiscountCurveSet | None
) -> tuple[DiscountCurve, ...]:
    """A bilateral batch's rules, since #176 and named-curves-slice-3.md, in this order, the first
    failure being the message: financial, since a physical delivery has no payment to discount; a
    collection of curves supplied; each distinct key of the batch bound to the curve of that exact
    name in the collection, in key order, by the step every caller shares since
    shared-curve-binding.md, curve_named, case and all and with no fallback to the first curve,
    a collection of one included, the first unbound refused in that step's one sentence with
    its key, the first row booking it and the names the collection holds; then each selected
    curve, in key order, starting on the valuation date, never rebased, and covering its own
    unpaid payment days, the first uncovered group named by its contract, its day, its key
    and the curve's range. A curve nobody selects is read for
    nothing, a paid group needs no factor, and a batch paid in full still binds its keys and
    checks each selected curve's start. The curves selected, in key order."""
    encoded = prepared.encoded
    terms = encoded.terms
    leg = prepared.legs[0]  # one leg today: its schedule names a group's contract
    if terms.settlement is Settlement.PHYSICAL:
        raise ValueError(
            "settlement_method is 'physical', expected 'financial' with a bilateral batch; a "
            "physical delivery has no payment to discount"
        )
    if curve_set is None:
        raise ValueError(
            "discount_curve_set is missing, expected a collection of discount curves with a "
            "bilateral batch, whose payments it discounts"
        )
    keyed = cast(tuple[str, ...], terms.discount_curve_key)  # bilateral: the kernel's rule
    curves: list[DiscountCurve] = []
    for key in encoded.keys:
        curve = curve_named(curve_set, key)  # the rule every caller binds a key by
        if curve is None:
            row = keyed.index(key)  # the first row booking the key
            raise no_curve_named(curve_set, key, named_trade(terms.trade_ids, row))
        curves.append(curve)
    as_of = leg.history.calendar.valuation_date.as_of
    pays = cast(UnpaidPayments, prepared.unpaid_payments)  # bilateral and financial: made with it
    payment_date = cast(NDArray[np.datetime64], encoded.payment_date)  # financial: the rule above
    for key, curve, keyed_pays in zip(encoded.keys, curves, pays.by_key, strict=True):
        curve_starts_on(curve, as_of)
        uncovered = keyed_pays.days > curve.max_date
        if uncovered.any():
            d = int(uncovered.argmax())
            g = int(keyed_pays.groups[int((keyed_pays.day_of_group == d).argmax())])
            label = group_label(encoded.terms, leg.encoded.leg, encoded.group_head, g)
            raise ValueError(
                f"the payment of {label} on {payment_date[g]} on "
                f"{key} is past the discount curve {curve.name!r}, which runs from "
                f"{curve.start_date} to {curve.max_date}; expected every unpaid payment day covered"
            )
    return tuple(curves)


def _discounted(
    prepared: PreparedTrades,
    markets: tuple[Market, ...],
    curves: tuple[DiscountCurve, ...],
    contributions: list[NDArray[np.float64]],
    quotes: list[NDArray[np.float64]],
    counter: WorkCounter,
) -> TradeResults:
    """The bilateral snapshot, since #176, over the rules _the_curves checked, every leg beside
    the trade's preparation since two-index-fixed-float.md. Each leg's live contributions are
    summed onto the payment groups, one bincount per leg, and each group's amount is the trade's
    fixed leg, each leg's set amounts and each leg's live amounts summed with Neumaier's
    compensation, the terms kept apart so that a small leg's dollar survives a strike that
    cancels the large leg's, one payment both legs share and, since two-index-one-price.md, no
    leg's own, the fixed leg being the trade's against its one price; a paid group's amount is
    cash already and is read for nothing. The unpaid groups, their time fractions and, per key,
    their distinct
    payment days with each group's place are the preparation's, made once when the batch was
    prepared, so each key's curve is read here once per distinct unpaid payment day of that
    key's groups, by position, the curve being daily from its start, and placed on those groups
    with nothing sorted or counted, each group's factor its own curve's since
    named-curves-slice-3.md and one factor serving both legs of a group; each unpaid group's
    NPV is its amount times that factor and its DV01 -0.0001 times the group's time fraction
    times that NPV, the analytic sensitivity to a rise of one basis point in the continuously
    compounded zero rates of its curve, negative for an amount receivable, the mark the NPVs'
    sum and the batch's DV01 the groups' summed by curve and then together, every used curve
    shifted together. The
    discounted lots are each leg's slots' lots times their groups' factors, a fixed slot's lots
    being zero, before any sum, since two slots of one day and one contract may pay on
    different days; summed over the leg's slots onto its references and its days and, since
    #186, by reference onto its contract months and years exactly as the preparation sums the
    nominal lots, one path whether a slot is live or not and whether any is, one delta per leg
    in its own index's lots and never a sum across indexes; and the discounted sensitivity the
    lots times the leg's reporting lot's coefficient. Then the rate risk by curve, every curve at
    once: the groups' DV01s summed by curve for the totals and onto the payment days with each
    group's curve beside the axis in its key, a row per curve, since #178 the axes the encoding
    made once, the months and the years then summed from the rows, four bincounts over the
    groups and the rows. The arithmetic runs with numpy's flags down and the rules judge:
    every group's amount, the two totals, each leg's discounted lots by reference and by
    bucket, its discounted sensitivity by reference and its lots' total are finite, else the
    first that is not is refused by its group, the batch, the leg, its contract or its bucket;
    each curve's three DV01 views are finite or the first period that is not is refused with its
    curve. Since #197 each leg's cross-gamma is _cross_gamma's, made from its discounted lots
    after every rule above and under its own, every curve's row at once.

    Work: one curve per distinct key, one factor per distinct unpaid payment day of each key, one
    group per unpaid group, one slot per slot of each leg for the lots and once more for the
    cross-gamma, and the reductions, eight per leg and four for the batch whatever the number of
    curves, seven of the batch's and each leg's writing a row per curve, reported to the
    counter; nothing per component or observation, nothing of the nominal risk done again, no
    day sorted and no pass over the slots per curve.
    """
    encoded = prepared.encoded
    terms = encoded.terms
    legs = prepared.legs
    first = legs[0]
    first_terms = first.encoded.leg
    conventions = first_terms.index.conventions  # a pair settles in one unit, the kernel's rule
    currency = conventions.currency_unit
    as_of = first.history.calendar.valuation_date.as_of
    groups = encoded.offset_of_group.size
    payment_date = cast(
        NDArray[np.datetime64], encoded.payment_date
    )  # financial: _the_curves' rule
    pays = cast(UnpaidPayments, prepared.unpaid_payments)  # bilateral and financial: the same rule
    axes = cast(PaymentAxes, encoded.payment_axes)  # bilateral and financial: made with it
    places = cast(CurveAxes, first.encoded.curve_axes)  # the groups' places, every leg's alike
    key_of_group = cast(NDArray[np.intp], encoded.key_of_group)  # bilateral: keyed
    paired = len(legs) > 1
    curve_count = len(curves)
    days, months, years = axes.days.size, axes.months.size, axes.years.size
    factors_read = 0
    with np.errstate(over="ignore", invalid="ignore"):  # the rules below are the judge
        # Each group's amount: the trade's fixed leg, each leg's set amounts and each leg's live
        # contributions summed onto the groups, one bincount per leg, the terms kept apart and
        # summed with Neumaier's compensation, so that a small leg's dollar survives a strike
        # that cancels the large leg's; one payment both legs share, since
        # two-index-one-price.md the trade's alone.
        sides: list[NDArray[np.float64] | float] = [encoded.offset_of_group]
        for leg, contribution in zip(legs, contributions, strict=True):
            sides.append(leg.set_amount)
            sides.append(
                np.bincount(
                    leg.encoded.slot_group[leg.live_slot], weights=contribution, minlength=groups
                )
            )
        amount = compensated(sides)
        payment_factor = np.ones(groups)  # a paid group's policy factor, read for nothing
        for curve, keyed in zip(curves, pays.by_key, strict=True):
            payment_factor[keyed.groups] = factors_on(curve, keyed.days)[keyed.day_of_group]
            factors_read += int(keyed.days.size)
        npv = np.zeros(groups)
        dv01_by_group = np.zeros(groups)
        npv[pays.groups], dv01_by_group[pays.groups] = discounted(
            amount[pays.groups], payment_factor[pays.groups], pays.tau
        )
        mark = float(npv.sum())
        dv01_by_curve = np.bincount(key_of_group, weights=dv01_by_group, minlength=curve_count)
        dv01 = float(dv01_by_curve.sum())
        # Since #178, the DV01 by payment day, month and year, the groups' DV01s summed onto the
        # axes the encoding made once, a paid group's nothing on its day, three bincounts; since
        # named-curves-slice-3.md every curve's row at once, the group's curve in the key.
        dv01_by_day = np.bincount(
            places.group_payment_day, weights=dv01_by_group, minlength=curve_count * days
        )
        dv01_by_month = np.bincount(
            places.payment_month_of_day, weights=dv01_by_day, minlength=curve_count * months
        )
        dv01_by_year = np.bincount(
            places.payment_year_of_month, weights=dv01_by_month, minlength=curve_count * years
        )
        lots = [_the_lots_arrays(leg, payment_factor) for leg in legs]
    unfinished = ~np.isfinite(amount)
    if unfinished.any():
        g = int(unfinished.argmax())
        label = group_label(encoded.terms, first.encoded.leg, encoded.group_head, g)
        raise ValueError(
            f"the payment of {label} on {payment_date[g]} on "
            f"{encoded.keys[int(key_of_group[g])]} is {float(amount[g])!r}, expected a finite "
            f"amount of {currency}; its fixed, set and live legs sum past the largest number"
        )
    for label, total in (("mark", mark), ("DV01", dv01)):
        if not np.isfinite(total):
            raise ValueError(
                f"the batch has {total!r} of {label} in all, expected a finite amount of "
                f"{currency}; the groups' amounts, each finite, sum past the largest number"
            )
    for leg, each in zip(legs, lots, strict=True):
        _the_lots_checked(
            leg, each, f"index {leg.encoded.leg.index.name!r}" if paired else "the batch"
        )
    _each_period_finite(
        (
            ("the payment day", axes.days, dv01_by_day),
            ("the payment month from", axes.months, dv01_by_month),
            ("the payment year from", axes.years, dv01_by_year),
        ),
        curves,
        "DV01",
        f"amount of {currency} per basis point",
        "its groups' DV01s sum past the largest number",
    )
    # Since #197 each leg's cross-gamma, after every rule above and under its own.
    crosses = [
        _cross_gamma(
            leg,
            pays,
            discounted_lots,
            leg.encoded.leg.reporting_lot.words,
            as_of,
            curves,
            cast(CurveAxes, leg.encoded.curve_axes),
        )
        for leg, (discounted_lots, *_) in zip(legs, lots, strict=True)
    ]
    # Since #186 the facts refusing a month or a year report of the DV01 standing before the
    # valuation day's period, found once here against the display axes, per curve; each leg's
    # discounted lots' facts are its own, found with its lots.
    early_dv01 = tuple(
        [
            early_risk(
                f"{curve.name} {currency}",
                "payment",
                as_of,
                f"{currency} per basis point",
                axes.months,
                dv01_by_month[c * months : (c + 1) * months],
                first.by_month.paid_from,
                axes.years,
                dv01_by_year[c * years : (c + 1) * years],
                first.by_year.paid_from,
            )
            for c, curve in enumerate(curves)
        ]
    )
    counter.hit(CURVES_SELECTED, curve_count)
    counter.hit(PAYMENT_FACTORS_READ, factors_read)
    counter.hit(GROUPS_VALUED, int(pays.groups.size))
    slots = sum([int(leg.encoded.slot_group.size) for leg in legs])
    counter.hit(SLOTS_DISCOUNTED, slots)
    counter.hit(SLOTS_WEIGHTED, slots)
    counter.hit(RISK_REDUCTIONS, 8 * len(legs) + 4)
    for array in (
        amount,
        npv,
        dv01_by_group,
        dv01_by_curve,
        payment_factor,
        dv01_by_day,
        dv01_by_month,
        dv01_by_year,
    ):
        array.setflags(write=False)
    results = [
        _discounted_leg(leg, market, contribution, quote, each, cross, as_of, curves)
        for leg, market, contribution, quote, each, cross in zip(
            legs, markets, contributions, quotes, lots, crosses, strict=True
        )
    ]
    return TradeResults(
        prepared=prepared,
        legs=tuple(results),
        route=terms.route,
        currency=currency,
        as_of=as_of,
        mark=mark,
        cash=prepared.cash,
        dv01=dv01,
        reserves=encoded.reserves,
        curves=curves,
        payment_amount=amount,
        npv_by_group=npv,
        dv01_by_group=dv01_by_group,
        payment_factor=payment_factor,
        # Each curve's share of the DV01, its row of the arrays above by reference, on the axes
        # they were summed onto.
        rate_contributions=tuple(
            [
                RateContribution(
                    curve,
                    currency,
                    float(dv01_by_curve[c]),
                    axes.days,
                    dv01_by_day[c * days : (c + 1) * days],
                    axes.months,
                    dv01_by_month[c * months : (c + 1) * months],
                    axes.years,
                    dv01_by_year[c * years : (c + 1) * years],
                    early_dv01[c],
                )
                for c, curve in enumerate(curves)
            ]
        ),
    )


DiscountedLots = tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    float,
]


def _the_lots_arrays(leg: PreparedLeg, payment_factor: NDArray[np.float64]) -> DiscountedLots:
    """A leg's discounted lots and the vectors summed from them, under the caller's flags: each
    slot's lots times its group's factor, the delta by reference, the discounted sensitivity,
    the lots by day and by contract month and year, and the delta's total; _the_lots_checked
    judges them."""
    encoded = leg.encoded
    lot = encoded.leg.reporting_lot
    discounted_lots = leg.dated_live_lots * payment_factor[encoded.slot_group]
    delta = np.bincount(
        encoded.reference_of_slot, weights=discounted_lots, minlength=encoded.references.size
    )
    discounted_price_sensitivity = delta * lot.coefficient
    daily = np.bincount(encoded.day_of_slot, weights=discounted_lots, minlength=encoded.days.size)
    monthly = np.bincount(
        encoded.contract_month_of_reference,
        weights=delta,
        minlength=encoded.contract_months.size,
    )
    yearly = np.bincount(
        encoded.contract_year_of_month, weights=monthly, minlength=encoded.contract_years.size
    )
    return (
        discounted_lots,
        delta,
        discounted_price_sensitivity,
        daily,
        monthly,
        yearly,
        float(delta.sum()),
    )


def _the_lots_checked(leg: PreparedLeg, lots: DiscountedLots, whose: str) -> None:
    """A leg's discounted vectors each finite, else the first that is not refused by its contract,
    its bucket or the leg, worded as whose it is; the five vectors frozen."""
    encoded = leg.encoded
    leg_terms = encoded.leg
    conventions = leg_terms.index.conventions
    currency = conventions.currency_unit
    codes = leg_terms.schedule.codes
    words = leg_terms.reporting_lot.words
    _, delta, discounted_price_sensitivity, daily, monthly, yearly, discounted_total = lots
    outrun = ~np.isfinite(delta)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{codes[int(encoded.references[r])]} has {float(delta[r])!r} of "
            f"delta, expected a finite number of {words}; its discounted lots sum "
            "past the largest number"
        )
    outrun = ~np.isfinite(discounted_price_sensitivity)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{codes[int(encoded.references[r])]} has "
            f"{float(discounted_price_sensitivity[r])!r} "
            f"of discounted price sensitivity, expected a finite amount of {currency} per "
            f"{conventions.quote_currency_unit}/{conventions.quote_quantity_unit}; its discounted "
            "lots times the lot's coefficient outrun the largest number"
        )
    for label, starts, values in (
        ("the day", encoded.days, daily),
        ("the contract month from", encoded.contract_months, monthly),
        ("the contract year from", encoded.contract_years, yearly),
    ):
        outrun = ~np.isfinite(values)
        if outrun.any():
            b = int(outrun.argmax())
            raise ValueError(
                f"{label} {starts[b]} has {float(values[b])!r} of delta in all, "
                f"expected a finite number of {words}; its discounted lots sum past the largest "
                "number"
            )
    if not np.isfinite(discounted_total):
        raise ValueError(
            f"{whose} has {discounted_total!r} of delta in all, expected a finite "
            f"number of {words}; the contracts' discounted deltas, each finite, sum past the "
            "largest number"
        )
    for array in (delta, discounted_price_sensitivity, daily, monthly, yearly):
        array.setflags(write=False)


def _discounted_leg(
    leg: PreparedLeg,
    market: Market,
    contribution: NDArray[np.float64],
    quote: NDArray[np.float64],
    lots: DiscountedLots,
    cross: tuple[
        NDArray[np.float64],
        NDArray[np.float64],
        NDArray[np.float64],
        NDArray[np.float64],
        NDArray[np.float64],
        float,
        tuple[EarlyRisk, ...],
    ],
    as_of: np.datetime64,
    curves: tuple[DiscountCurve, ...],
) -> LegResults:
    """A bilateral leg's results over what _discounted made for it: the nominal risk weighted by
    each live slot's payment factor and since #197 each curve's share of its cross-gamma, its
    row of the arrays by reference on the axes they were summed onto; and since #186 the facts
    refusing a month or a year report of the discounted lots standing before the valuation
    day's period, found once here against the leg's display axes. No value: since
    two-index-one-price.md the payments, NPVs and DV01s are the trade's."""
    encoded = leg.encoded
    leg_terms = encoded.leg
    conventions = leg_terms.index.conventions
    _, delta, discounted_price_sensitivity, daily, monthly, yearly, discounted_total = lots
    cross_gamma, cross_by_day, cross_by_month, cross_by_year, cross_by_curve, cross_total, early = (
        cross
    )
    words = leg_terms.reporting_lot.words
    early_delta = early_risk(
        f"index {leg_terms.index.name!r}",
        "contract",
        as_of,
        words,
        encoded.contract_months,
        monthly,
        leg.by_month.contract_from,
        encoded.contract_years,
        yearly,
        leg.by_year.contract_from,
    )
    references = encoded.references.size
    observed = encoded.days.size
    contract_months = encoded.contract_months.size
    contract_years = encoded.contract_years.size
    return LegResults(
        prepared=leg,
        market=market,
        dated_live_contribution=contribution,
        quote=quote,
        contracts=encoded.references,
        price_sensitivity=leg.price_sensitivity,
        price_sensitivity_unit=(
            f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
            f"{conventions.quote_quantity_unit}"
        ),
        nominal_delta=leg.nominal_delta,
        nominal_delta_total=leg.nominal_delta_total,
        lot_unit=words,
        delta=delta,
        delta_total=discounted_total,
        discounted_price_sensitivity=discounted_price_sensitivity,
        discounted_daily_lots=daily,
        discounted_monthly_lots=monthly,
        discounted_yearly_lots=yearly,
        early_delta=early_delta,
        cross_gamma_total=cross_total,
        cross_contributions=tuple(
            [
                CrossContribution(
                    curve,
                    encoded.references,
                    cross_gamma[c * references : (c + 1) * references],
                    encoded.days,
                    cross_by_day[c * observed : (c + 1) * observed],
                    encoded.contract_months,
                    cross_by_month[c * contract_months : (c + 1) * contract_months],
                    encoded.contract_years,
                    cross_by_year[c * contract_years : (c + 1) * contract_years],
                    float(cross_by_curve[c]),
                    early[c],
                )
                for c, curve in enumerate(curves)
            ]
        ),
    )


def _each_period_finite(
    views: tuple[tuple[str, NDArray[np.datetime64], NDArray[np.float64]], ...],
    curves: tuple[DiscountCurve, ...],
    what: str,
    unit: str,
    why: str,
) -> None:
    """Each curve's row of each view finite, the views before the totals since a bucket's sum
    can outrun what its parts did not, else the first period that is not is refused with its
    curve, the rows standing one per curve in each view."""
    for label, starts, values in views:
        outrun = ~np.isfinite(values)
        if outrun.any():
            c, b = divmod(int(outrun.argmax()), starts.size)
            raise ValueError(
                f"{label} {starts[b]} has {float(values[c * starts.size + b])!r} of {what} on "
                f"{curves[c].name} in all, expected a finite {unit}; {why}"
            )


def _cross_gamma(
    leg: PreparedLeg,
    pays: UnpaidPayments,
    discounted_lots: NDArray[np.float64],
    words: str,
    as_of: np.datetime64,
    curves: tuple[DiscountCurve, ...],
    places: CurveAxes,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    float,
    tuple[EarlyRisk, ...],
]:
    """The cross-gamma, since #197, single-curve-cross-gamma.md, and since named-curves-slice-3.md
    every curve's at once: by reference, by day, by contract month, by contract year, a row per
    curve in one array per axis, the totals by curve and their sum, the leg's cross-gamma with
    every used curve shifted together, and the facts refusing a month or a year
    report of each curve's standing before the valuation day's period. Each unpaid group's
    weight is -0.0001 times its time fraction, its factor's derivative over the factor for a rise
    of one basis point in the continuously compounded zero rates of its own curve, the convention
    the DV01 moves by; a paid group's weight is nothing and its factor is read for nothing. The
    weight is gathered onto the slots as the factor was and multiplied into the discounted lots,
    each slot once whatever the number of curves, each payment's own time applied before any sum,
    since two slots of one contract and one day may pay years apart, a fixed slot's lots nothing;
    then the slots are summed onto the references and the days with each slot's curve beside the
    axis in its key, writing every curve's row, and by reference onto the contract months and
    years, exactly as the discounted lots are, the payment supplying the time and the curve and
    never the axis, one path whether any slot is live. The arithmetic runs with numpy's flags
    down and the rules judge: each curve's vector by reference, three views and total are finite,
    else the first that is not is refused by its contract, its bucket or the batch, with its
    curve, and the curves' totals sum finite, else the batch's cross-gamma is refused as its
    DV01 is, two finite totals adding past the largest number without a word; the four arrays
    are frozen.

    Work: one weight per group, one product per slot and four reductions, counted by the caller;
    nothing sorted, no factor and no day read again, no pass per curve.
    """
    encoded = leg.encoded
    leg_terms = encoded.leg
    codes = leg_terms.schedule.codes
    curve_count = len(curves)
    references = encoded.references.size
    days = encoded.days.size
    months = encoded.contract_months.size
    years = encoded.contract_years.size
    with np.errstate(over="ignore", invalid="ignore"):  # the rules below are the judge
        weight = np.zeros(encoded.group_contract.size)
        weight[pays.groups] = -0.0001 * pays.tau
        by_slot = discounted_lots * weight[encoded.slot_group]
        by_reference = np.bincount(
            places.slot_reference, weights=by_slot, minlength=curve_count * references
        )
        by_day = np.bincount(places.slot_day, weights=by_slot, minlength=curve_count * days)
        by_month = np.bincount(
            places.contract_month_of_reference,
            weights=by_reference,
            minlength=curve_count * months,
        )
        by_year = np.bincount(
            places.contract_year_of_month, weights=by_month, minlength=curve_count * years
        )
        totals = by_reference.reshape(curve_count, references).sum(axis=1)
        total = float(totals.sum())  # the batch's, judged below with the curves' own
    per_bp = f"{words} per basis point"
    outrun = ~np.isfinite(by_reference)
    if outrun.any():
        c, r = divmod(int(outrun.argmax()), references)
        raise ValueError(
            f"{codes[int(encoded.references[r])]} has {float(by_reference[c * references + r])!r} "
            f"of cross-gamma on {curves[c].name}, expected a finite number of {per_bp}; its "
            "discounted lots, each weighted by its payment's time, sum past the largest number"
        )
    _each_period_finite(
        (
            ("the day", encoded.days, by_day),
            ("the contract month from", encoded.contract_months, by_month),
            ("the contract year from", encoded.contract_years, by_year),
        ),
        curves,
        "cross-gamma",
        f"number of {per_bp}",
        "its slots' cross-gammas sum past the largest number",
    )
    outrun = ~np.isfinite(totals)
    if outrun.any():
        c = int(outrun.argmax())
        raise ValueError(
            f"the batch has {float(totals[c])!r} of cross-gamma on {curves[c].name} in all, "
            f"expected a finite number of {per_bp}; the contracts' cross-gammas, each finite, sum "
            "past the largest number"
        )
    if not np.isfinite(total):
        raise ValueError(
            f"the batch has {total!r} of cross-gamma in all, expected a finite number of {per_bp}; "
            "the curves' cross-gammas, each finite, sum past the largest number"
        )
    early = tuple(
        [
            early_risk(
                f"index {leg_terms.index.name!r} on {curve.name}",
                "contract",
                as_of,
                per_bp,
                encoded.contract_months,
                by_month[c * months : (c + 1) * months],
                leg.by_month.contract_from,
                encoded.contract_years,
                by_year[c * years : (c + 1) * years],
                leg.by_year.contract_from,
            )
            for c, curve in enumerate(curves)
        ]
    )
    for array in (by_reference, by_day, by_month, by_year, totals):
        array.setflags(write=False)
    return by_reference, by_day, by_month, by_year, totals, total, early
