"""The prepared batch evaluated against one market: the quotes of its live references read off
the market once each, gathered onto the live slots and multiplied by their exposure, one
multiplication and one sum for the live amount, which the unsettled offsets and set amounts
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

from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.discount_curve_set import DiscountCurveSet
from goosedove.globals.payments import curve_starts_on, discounted, factors_on
from goosedove.instrumentation.work_counts import KERNEL, WorkCounter
from goosedove.market.market import Market
from goosedove.trades.contributions import CrossContribution, RateContribution
from goosedove.trades.display_axes import EarlyRisk, early_risk
from goosedove.trades.encoding import CurveAxes, PaymentAxes
from goosedove.trades.preparation import PreparedTrades, UnpaidPayments
from goosedove.trades.results import TradeResults
from goosedove.trades.terms import Route, Settlement, named_trade

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
    market: Market,
    counter: WorkCounter,
    curve_set: DiscountCurveSet | None = None,
) -> TradeResults:
    """The one way to make TradeResults: the rules, checked once, in this order, the first failure
    being the message; then the quotes read, one kernel call, and the snapshot.

    The market is over the history the batch was prepared against, the one object: a market over
    another history, a later valuation date or a corrected fixing, is refused, and the batch is
    prepared again outside, never silently here. Then the route, since #176. A cleared batch is
    undiscounted and takes no collection of curves: one supplied is refused by name, since its
    payments are margined as they come and discounting them would be a wrong number. A bilateral
    batch meets _the_curves' rules, since named-curves-slice-3.md: financial, since a physical
    delivery has no payment to discount; a collection supplied; each of its keys bound to the
    curve of that exact name in the collection; and each selected curve starting on the
    valuation date, a curve never being rebased, and covering every unpaid payment day of its
    own groups, a fixed-but-unpaid group and a group whose amount nets to nothing included, the
    first uncovered named by its contract, its day, its key and the curve's range.

    The market answers the quotes of the live references in the batch's order, one per distinct
    contract, and refuses a contract past its coverage by name, as it does for every reader; the
    quotes are gathered onto the live slots, and each slot's exposure times its reference's quote
    is its contribution, finite or refused by its slot and its quote since #190,
    reject-nonfinite-trade-arithmetic.md, before either route sums it. For a cleared batch the
    live amount is the contributions' sum, the one reduction this route makes, and the mark is
    the unsettled offsets and set amounts plus the live amount, each finite or refused for the
    batch, since two finite floats add past the largest number without a word; the cash is the
    preparation's, the
    sensitivity, the lot delta and its total the preparation's, shared, the discounted vectors
    those same arrays, since nothing discounts, DV01 zero and no group vector kept. A bilateral
    batch is _discounted's. The reserves are the encoding's, by reference, summed when the batch
    was made and never here.

    Work: one kernel call, one quote per live reference, reported to the counter, and for a
    bilateral batch what _discounted reports; nothing of the encoding or the preparation is done
    again, and nothing per slot but the gather and the multiplication over the live ones.
    """
    terms = prepared.encoded.terms
    if market.market_history is not prepared.history:
        name = market.market_history.calendar.index.name
        raise ValueError(
            f"market is over another history of index {name!r}, "
            "expected the one the trades were prepared against"
        )
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
    quotes = market.live_prices(prepared.live_references)
    conventions = terms.index.conventions
    currency = conventions.currency_unit
    # The arithmetic runs with numpy's flags down and the rules judge, since #190: each live
    # slot's contribution is finite before either route sums it, else the first that is not is
    # refused by its slot and its quote.
    with np.errstate(over="ignore", invalid="ignore"):
        dated_live_contribution = (
            prepared.dated_live_exposure[prepared.live_slot]
            * quotes[prepared.reference_of_live_slot]
        )
        outrun = ~np.isfinite(dated_live_contribution)
        if outrun.any():
            i = int(outrun.argmax())
            quote = float(quotes[int(prepared.reference_of_live_slot[i])])
            raise ValueError(
                f"{prepared.encoded.named_slot(int(prepared.live_slot[i]))}, quoted at {quote!r}, "
                f"has {float(dated_live_contribution[i])!r} of live contribution, expected a "
                f"finite amount of {currency}; its exposure times the quote outruns the largest "
                "number"
            )
        # The cleared route's one reduction, the live contributions summed, under the same
        # flags; the bilateral route sums them by payment group in _discounted instead.
        live = float(dated_live_contribution.sum()) if not curves else 0.0
    counter.hit(KERNEL)
    counter.hit(LIVE_PRICES_READ, int(prepared.live_references.size))
    dated_live_contribution.setflags(write=False)
    if curves:
        return _discounted(prepared, market, curves, dated_live_contribution, counter)
    # The cleared mark: the live amount, then the unsettled fixed legs and set amounts added,
    # each finite or refused for the batch; Python adds two finite floats past the largest
    # number without a word, so the rule looks.
    if not np.isfinite(live):
        raise ValueError(
            f"the batch has {live!r} of live amount in all, expected a finite amount of "
            f"{currency}; the live slots' contributions, each finite, sum past the largest number"
        )
    mark = prepared.offset_unsettled + prepared.set_unsettled + live
    if not np.isfinite(mark):
        raise ValueError(
            f"the batch has {mark!r} of mark in all, expected a finite amount of {currency}; its "
            "unsettled fixed legs, set amounts and live amount, each finite, sum past the largest "
            "number"
        )
    return TradeResults(
        prepared=prepared,
        market=market,
        route=terms.route,
        currency=currency,
        as_of=prepared.history.calendar.valuation_date.as_of,
        mark=mark,
        cash=prepared.cash,
        dated_live_contribution=dated_live_contribution,
        contracts=prepared.encoded.references,
        price_sensitivity=prepared.price_sensitivity,
        price_sensitivity_unit=(
            f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
            f"{conventions.quote_quantity_unit}"
        ),
        lot_delta=prepared.lot_delta,
        lot_delta_total=prepared.lot_delta_total,
        lot_unit=terms.reporting_lot.words,
        dv01=0.0,  # the undiscounted model moves for no rate
        reserves=prepared.encoded.reserves,
        curves=(),
        # Cleared: nothing discounts, so the valuation-adjusted risk is the nominal risk itself,
        # the preparation's arrays by reference.
        discounted_lot_delta=prepared.lot_delta,
        discounted_lot_delta_total=prepared.lot_delta_total,
        discounted_price_sensitivity=prepared.price_sensitivity,
        discounted_daily_lots=prepared.daily_lots,
        discounted_monthly_lots=prepared.monthly_lots,
        discounted_yearly_lots=prepared.yearly_lots,
        # No payment group is valued and the DV01 has no dated axis.
        payment_amount=None,
        npv_by_group=None,
        dv01_by_group=None,
        payment_factor=None,
        early_delta=prepared.early_nominal,  # the same lots: worded as the delta when asked for
        # Nothing discounts, so no rate moves the mark or the lots: the known zero, no
        # contribution and no buffer, as the DV01's axes are.
        cross_gamma_total=0.0,
        rate_contributions=(),
        cross_contributions=(),
    )


def _listed(names: tuple[str, ...]) -> str:
    """Names in a message: `SOFR`, `SOFR and FFOIS`, `SOFR, FFOIS and SONIA`."""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _the_curves(
    prepared: PreparedTrades, curve_set: DiscountCurveSet | None
) -> tuple[DiscountCurve, ...]:
    """A bilateral batch's rules, since #176 and named-curves-slice-3.md, in this order, the first
    failure being the message: financial, since a physical delivery has no payment to discount; a
    collection of curves supplied; each distinct key of the batch bound to the curve of that exact
    name in the collection, in key order, case and all, the first unbound named with its key, the
    first row booking it and the names the collection holds, no fallback to the first curve, a
    collection of one included; then each selected curve, in key order, starting on the valuation
    date, never rebased, and covering its own unpaid payment days, the first uncovered group named
    by its contract, its day, its key and the curve's range. A curve nobody selects is read for
    nothing, a paid group needs no factor, and a batch paid in full still binds its keys and
    checks each selected curve's start. The curves selected, in key order."""
    encoded = prepared.encoded
    terms = encoded.terms
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
    by_name = {curve.name: curve for curve in curve_set.curves}
    keyed = cast(tuple[str, ...], terms.discount_curve_key)  # bilateral: the kernel's rule
    curves: list[DiscountCurve] = []
    for key in encoded.keys:
        curve = by_name.get(key)
        if curve is None:
            row = keyed.index(key)  # the first row booking the key
            raise ValueError(
                f"discount_curve_key {key!r} of {named_trade(terms.trade_ids, row)} names no curve "
                f"of the collection, which holds {_listed(curve_set.names)}; expected a curve of "
                "that name"
            )
        curves.append(curve)
    as_of = prepared.history.calendar.valuation_date.as_of
    pays = cast(UnpaidPayments, prepared.unpaid_payments)  # bilateral and financial: made with it
    payment_date = cast(NDArray[np.datetime64], encoded.payment_date)  # financial: the rule above
    codes = terms.schedule.codes
    for key, curve, keyed_pays in zip(encoded.keys, curves, pays.by_key, strict=True):
        curve_starts_on(curve, as_of)
        uncovered = keyed_pays.days > curve.max_date
        if uncovered.any():
            d = int(uncovered.argmax())
            g = int(keyed_pays.groups[int((keyed_pays.day_of_group == d).argmax())])
            raise ValueError(
                f"the payment of {codes[int(encoded.group_contract[g])]} on {payment_date[g]} on "
                f"{key} is past the discount curve {curve.name!r}, which runs from "
                f"{curve.start_date} to {curve.max_date}; expected every unpaid payment day covered"
            )
    return tuple(curves)


def _discounted(
    prepared: PreparedTrades,
    market: Market,
    curves: tuple[DiscountCurve, ...],
    dated_live_contribution: NDArray[np.float64],
    counter: WorkCounter,
) -> TradeResults:
    """The bilateral snapshot, since #176, over the rules _the_curves checked. The live
    contributions are summed onto the payment groups, one bincount, and each group's amount is
    its entry-price offset, its set amount and its live amount together; a paid group's amount
    is cash already and is read for nothing. The unpaid groups, their time fractions and, per
    key, their distinct
    payment days with each group's place are the preparation's, made once when the batch was
    prepared, so each key's curve is read here once per distinct unpaid payment day of that key's
    groups, by position, the curve being daily from its start, and placed on those groups with
    nothing sorted or counted, each group's factor its own curve's since named-curves-slice-3.md;
    each unpaid group's NPV is its amount times its factor, the mark their sum, and its DV01 is
    -0.0001 times its time fraction times its NPV, the analytic sensitivity to a rise of one basis
    point in the continuously compounded zero rates of its curve, negative for an amount
    receivable. The discounted lots are each slot's lots times its group's factor, a fixed slot's
    lots being zero, before any sum, since two slots of one day and one contract may pay on
    different days; summed over every slot onto the references and the days and, since #186, by
    reference onto the contract months and years exactly as the preparation sums the nominal
    lots, one path whether a slot is live or not and whether any is, since a sum over no slot is
    numpy's integer zeros and not a sum, one combined delta for the batch whatever its curves;
    and the discounted sensitivity the lots times the reporting lot's coefficient, the one
    conversion the index resolved. Then the risk by curve, every curve at once: the groups' DV01s
    summed by curve for the totals and onto the payment days with each group's curve beside the
    axis in its key, a row per curve, since #178 the axes the encoding made once, the months and
    the years then summed from the rows, four bincounts over the groups and the rows; the batch's
    DV01 the totals summed, every used curve shifted together. The arithmetic runs with numpy's
    flags down and the rules judge: every group's amount, the two totals, the discounted lots by
    reference and by bucket, the discounted sensitivity by reference and the lots' total are
    finite, else the first that is not is refused by its group, the batch, its contract or its
    bucket; each curve's three DV01 views are finite or the first period that is not is refused
    with its curve. Since #197 the cross-gamma is _cross_gamma's, made from the discounted lots
    after every rule above and under its own, every curve's row at once.

    Work: one curve per distinct key, one factor per distinct unpaid payment day of each key, one
    group per unpaid group, one slot per slot for the lots and once more for the cross-gamma,
    and twelve reductions whatever the number of curves, seven of them writing a row per curve,
    reported to the counter; nothing per component or observation, nothing of the nominal risk
    done again, no day sorted and no pass over the slots per curve.
    """
    encoded = prepared.encoded
    terms = encoded.terms
    conventions = terms.index.conventions
    currency = conventions.currency_unit
    codes = terms.schedule.codes
    as_of = prepared.history.calendar.valuation_date.as_of
    groups = encoded.group_contract.size
    payment_date = cast(
        NDArray[np.datetime64], encoded.payment_date
    )  # financial: _the_curves' rule
    pays = cast(UnpaidPayments, prepared.unpaid_payments)  # bilateral and financial: the same rule
    axes = cast(PaymentAxes, encoded.payment_axes)  # bilateral and financial: made with it
    places = cast(CurveAxes, encoded.curve_axes)  # the same
    key_of_group = cast(NDArray[np.intp], encoded.key_of_group)  # bilateral: keyed
    live_group = encoded.slot_group[prepared.live_slot]
    lot = terms.reporting_lot
    curve_count = len(curves)
    days, months, years = axes.days.size, axes.months.size, axes.years.size
    factors_read = 0
    with np.errstate(over="ignore", invalid="ignore"):  # the rules below are the judge
        amount = (
            encoded.offset_of_group
            + prepared.set_amount
            + np.bincount(live_group, weights=dated_live_contribution, minlength=groups)
        )
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
        discounted_lots = prepared.dated_live_lots * payment_factor[encoded.slot_group]
        discounted_lot_delta = np.bincount(
            encoded.reference_of_slot, weights=discounted_lots, minlength=encoded.references.size
        )
        discounted_price_sensitivity = discounted_lot_delta * lot.coefficient
        daily = np.bincount(
            encoded.day_of_slot, weights=discounted_lots, minlength=encoded.days.size
        )
        monthly = np.bincount(
            encoded.contract_month_of_reference,
            weights=discounted_lot_delta,
            minlength=encoded.contract_months.size,
        )
        yearly = np.bincount(
            encoded.contract_year_of_month, weights=monthly, minlength=encoded.contract_years.size
        )
        discounted_total = float(discounted_lot_delta.sum())
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
    unfinished = ~np.isfinite(amount)
    if unfinished.any():
        g = int(unfinished.argmax())
        raise ValueError(
            f"the payment of {codes[int(encoded.group_contract[g])]} on {payment_date[g]} on "
            f"{encoded.keys[int(key_of_group[g])]} is {float(amount[g])!r}, expected a finite "
            f"amount of {currency}; its fixed, set and live legs sum past the largest number"
        )
    for label, total in (("mark", mark), ("DV01", dv01)):
        if not np.isfinite(total):
            raise ValueError(
                f"the batch has {total!r} of {label} in all, expected a finite amount of "
                f"{currency}; the groups' amounts, each finite, sum past the largest number"
            )
    words = lot.words
    outrun = ~np.isfinite(discounted_lot_delta)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{codes[int(encoded.references[r])]} has {float(discounted_lot_delta[r])!r} of "
            f"discounted lot delta, expected a finite number of {words}; its discounted lots sum "
            "past the largest number"
        )
    outrun = ~np.isfinite(discounted_price_sensitivity)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{codes[int(encoded.references[r])]} has {float(discounted_price_sensitivity[r])!r} "
            f"of discounted price sensitivity, expected a finite amount of {currency} per "
            f"{conventions.quote_currency_unit}/{conventions.quote_quantity_unit}; its discounted "
            "lots times the lot's coefficient outrun the largest number"
        )
    for label, starts, lots in (
        ("the day", encoded.days, daily),
        ("the contract month from", encoded.contract_months, monthly),
        ("the contract year from", encoded.contract_years, yearly),
    ):
        outrun = ~np.isfinite(lots)
        if outrun.any():
            b = int(outrun.argmax())
            raise ValueError(
                f"{label} {starts[b]} has {float(lots[b])!r} of discounted lot delta in all, "
                f"expected a finite number of {words}; its discounted lots sum past the largest "
                "number"
            )
    if not np.isfinite(discounted_total):
        raise ValueError(
            f"the batch has {discounted_total!r} of discounted lot delta in all, expected a finite "
            f"number of {words}; the contracts' discounted deltas, each finite, sum past the "
            "largest number"
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
    # Since #197 the cross-gamma, after every rule above and under its own.
    cross_gamma, cross_by_day, cross_by_month, cross_by_year, cross_by_curve, early_cross = (
        _cross_gamma(prepared, pays, discounted_lots, words, as_of, curves, places)
    )
    # Since #186 the facts refusing a month or a year report of the discounted lots or the DV01
    # standing before the valuation day's period, found once here against the preparation's
    # display axes, the DV01's per curve.
    early_delta = early_risk(
        f"index {terms.index.name!r}",
        "contract",
        as_of,
        words,
        encoded.contract_months,
        monthly,
        prepared.by_month.contract_from,
        encoded.contract_years,
        yearly,
        prepared.by_year.contract_from,
    )
    early_dv01 = tuple(
        [
            early_risk(
                f"{curve.name} {currency}",
                "payment",
                as_of,
                f"{currency} per basis point",
                axes.months,
                dv01_by_month[c * months : (c + 1) * months],
                prepared.by_month.paid_from,
                axes.years,
                dv01_by_year[c * years : (c + 1) * years],
                prepared.by_year.paid_from,
            )
            for c, curve in enumerate(curves)
        ]
    )
    counter.hit(CURVES_SELECTED, curve_count)
    counter.hit(PAYMENT_FACTORS_READ, factors_read)
    counter.hit(GROUPS_VALUED, int(pays.groups.size))
    counter.hit(SLOTS_DISCOUNTED, int(encoded.slot_group.size))
    counter.hit(SLOTS_WEIGHTED, int(encoded.slot_group.size))
    counter.hit(RISK_REDUCTIONS, 12)
    for array in (
        amount,
        npv,
        dv01_by_group,
        dv01_by_curve,
        payment_factor,
        discounted_lot_delta,
        discounted_price_sensitivity,
        daily,
        monthly,
        yearly,
        dv01_by_day,
        dv01_by_month,
        dv01_by_year,
    ):
        array.setflags(write=False)
    references = encoded.references.size
    observed = encoded.days.size
    contract_months = encoded.contract_months.size
    contract_years = encoded.contract_years.size
    return TradeResults(
        prepared=prepared,
        market=market,
        route=terms.route,
        currency=currency,
        as_of=as_of,
        mark=mark,
        cash=prepared.cash,
        dated_live_contribution=dated_live_contribution,
        contracts=encoded.references,
        price_sensitivity=prepared.price_sensitivity,
        price_sensitivity_unit=(
            f"{currency} per {conventions.quote_currency_unit}/{conventions.quote_quantity_unit}"
        ),
        lot_delta=prepared.lot_delta,
        lot_delta_total=prepared.lot_delta_total,
        lot_unit=words,
        dv01=dv01,
        reserves=encoded.reserves,
        curves=curves,
        # Bilateral: the nominal risk weighted by each live slot's payment factor, made above.
        discounted_lot_delta=discounted_lot_delta,
        discounted_lot_delta_total=discounted_total,
        discounted_price_sensitivity=discounted_price_sensitivity,
        discounted_daily_lots=daily,
        discounted_monthly_lots=monthly,
        discounted_yearly_lots=yearly,
        payment_amount=amount,
        npv_by_group=npv,
        dv01_by_group=dv01_by_group,
        payment_factor=payment_factor,
        early_delta=early_delta,
        cross_gamma_total=float(cross_by_curve.sum()),
        # Each curve's share of the DV01 and of the cross-gamma, its row of the arrays above by
        # reference, on the axes they were summed onto.
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
                    early_cross[c],
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
    prepared: PreparedTrades,
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
    tuple[EarlyRisk, ...],
]:
    """The cross-gamma, since #197, single-curve-cross-gamma.md, and since named-curves-slice-3.md
    every curve's at once: by reference, by day, by contract month, by contract year, a row per
    curve in one array per axis, the totals by curve, and the facts refusing a month or a year
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
    curve; the four arrays are frozen.

    Work: one weight per group, one product per slot and four reductions, counted by the caller;
    nothing sorted, no factor and no day read again, no pass per curve.
    """
    encoded = prepared.encoded
    terms = encoded.terms
    codes = terms.schedule.codes
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
    early = tuple(
        [
            early_risk(
                f"index {terms.index.name!r} on {curve.name}",
                "contract",
                as_of,
                per_bp,
                encoded.contract_months,
                by_month[c * months : (c + 1) * months],
                prepared.by_month.contract_from,
                encoded.contract_years,
                by_year[c * years : (c + 1) * years],
                prepared.by_year.contract_from,
            )
            for c, curve in enumerate(curves)
        ]
    )
    for array in (by_reference, by_day, by_month, by_year, totals):
        array.setflags(write=False)
    return by_reference, by_day, by_month, by_year, totals, early
