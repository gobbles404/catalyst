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
from goosedove.globals.payments import curve_starts_on, discounted, factors_on
from goosedove.instrumentation.work_counts import KERNEL, WorkCounter
from goosedove.market.market import Market
from goosedove.trades.contributions import CrossContribution, RateContribution
from goosedove.trades.display_axes import EarlyRisk, early_risk
from goosedove.trades.encoding import PaymentAxes
from goosedove.trades.preparation import PreparedTrades, UnpaidPayments
from goosedove.trades.results import TradeResults
from goosedove.trades.terms import Route, Settlement

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


def trade_results(
    prepared: PreparedTrades,
    market: Market,
    counter: WorkCounter,
    curve: DiscountCurve | None = None,
) -> TradeResults:
    """The one way to make TradeResults: the rules, checked once, in this order, the first failure
    being the message; then the quotes read, one kernel call, and the snapshot.

    The market is over the history the batch was prepared against, the one object: a market over
    another history, a later valuation date or a corrected fixing, is refused, and the batch is
    prepared again outside, never silently here. Then the route, since #176. A cleared batch is
    undiscounted and takes no curve: one supplied is refused by name, since its payments are
    margined as they come and discounting them would be a wrong number. A bilateral batch meets
    _the_curve's rules: financial, since a physical delivery has no payment to discount; a curve
    supplied; the curve starting on the valuation date, a curve never being rebased; and the
    curve covering every unpaid payment day, a fixed-but-unpaid group and a group whose amount
    nets to nothing included, the first uncovered named by its contract, its day and the curve's
    range.

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
    match terms.route:
        case Route.CLEARED:
            if curve is not None:
                raise ValueError(
                    "discount_curve is supplied, expected none unless route = bilateral; a cleared "
                    "batch is undiscounted"
                )
        case Route.BILATERAL:
            curve = _the_curve(prepared, curve)
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
        live = float(dated_live_contribution.sum()) if curve is None else 0.0
    counter.hit(KERNEL)
    counter.hit(LIVE_PRICES_READ, int(prepared.live_references.size))
    dated_live_contribution.setflags(write=False)
    if curve is not None:
        return _discounted(prepared, market, curve, dated_live_contribution, counter)
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
        curve=None,
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


def _the_curve(prepared: PreparedTrades, curve: DiscountCurve | None) -> DiscountCurve:
    """A bilateral batch's rules, since #176, in this order, the first failure being the message:
    financial, since a physical delivery has no payment to discount; a curve supplied; the curve
    starting on the valuation date, never rebased; and the curve covering every unpaid payment
    day, the first uncovered group named by its contract, its day and the curve's range. A paid
    group needs no factor, so a curve of one day serves a batch paid in full."""
    encoded = prepared.encoded
    if encoded.terms.settlement is Settlement.PHYSICAL:
        raise ValueError(
            "settlement_method is 'physical', expected 'financial' with a bilateral batch; a "
            "physical delivery has no payment to discount"
        )
    if curve is None:
        raise ValueError(
            "discount_curve is missing, expected a discount curve with a bilateral batch, whose "
            "payments it discounts"
        )
    curve_starts_on(curve, prepared.history.calendar.valuation_date.as_of)
    payment_date = cast(NDArray[np.datetime64], encoded.payment_date)  # financial: the rule above
    uncovered = ~prepared.is_settled & (payment_date > curve.max_date)
    if uncovered.any():
        g = int(uncovered.argmax())
        code = encoded.terms.schedule.codes[int(encoded.group_contract[g])]
        raise ValueError(
            f"the payment of {code} on {payment_date[g]} is past the discount curve, which runs "
            f"from {curve.start_date} to {curve.max_date}; expected every unpaid payment day "
            "covered"
        )
    return curve


def _discounted(
    prepared: PreparedTrades,
    market: Market,
    curve: DiscountCurve,
    dated_live_contribution: NDArray[np.float64],
    counter: WorkCounter,
) -> TradeResults:
    """The bilateral snapshot, since #176, over the rules _the_curve checked. The live contributions
    are summed onto the payment groups, one bincount, and each group's amount is its entry-price
    offset, its set amount and its live amount together; a paid group's amount is cash already
    and is read for nothing. The unpaid groups, their distinct payment days, each one's place among
    them and its time fraction are the preparation's, made once when the batch was prepared, so
    the curve's factor is read here once per distinct unpaid payment day, by position, the curve
    being daily from its start, and placed on the groups with nothing sorted or counted; each
    unpaid group's NPV is its amount times its factor, the mark their sum, and its DV01 is -0.0001
    times its time fraction times its NPV, the analytic sensitivity to a rise of one basis point in
    the continuously compounded zero rates, the batch's DV01 their sum, negative for an amount
    receivable. The discounted lots are each slot's lots times its group's factor, a fixed slot's
    lots being zero, before any sum, since two slots of one day and one contract may pay on
    different days; summed over every slot onto the references and the days and, since #186, by
    reference onto the contract months and years exactly as the preparation sums the nominal
    lots, one path whether a slot is live or
    not and whether any is, since a sum over no slot is numpy's integer zeros and not a sum; and
    the discounted sensitivity the lots times the reporting lot's coefficient, the one conversion
    the index resolved. The arithmetic runs with numpy's flags down and the rules judge: every
    group's amount, the two totals, the discounted lots by reference and by bucket, the discounted
    sensitivity by reference and the lots' total are finite, else the first that is not is refused
    by its group, the batch, its contract or its bucket. Since #178 the groups' DV01s are summed
    too, onto the payment days, their months and their years, the axes the encoding made once, a
    paid group's nothing on its day, and each of the three views is finite or the first period
    that is not is refused. Since #197 the cross-gamma is _cross_gamma's, made from the
    discounted lots after every rule above and under its own.

    Work: one factor per distinct unpaid payment day, one group per unpaid group, one slot per
    slot and eleven reductions, reported to the counter; nothing per component or observation,
    nothing of the nominal risk done again, and no day sorted.
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
    )  # financial: _the_curve's rule
    pays = cast(UnpaidPayments, prepared.unpaid_payments)  # bilateral and financial: the same rule
    live_group = encoded.slot_group[prepared.live_slot]
    lot = terms.reporting_lot
    with np.errstate(over="ignore", invalid="ignore"):  # the rules below are the judge
        amount = (
            encoded.offset_of_group
            + prepared.set_amount
            + np.bincount(live_group, weights=dated_live_contribution, minlength=groups)
        )
        payment_factor = np.ones(groups)  # a paid group's policy factor, read for nothing
        payment_factor[pays.groups] = factors_on(curve, pays.days)[pays.day_of_group]
        npv = np.zeros(groups)
        dv01_by_group = np.zeros(groups)
        npv[pays.groups], dv01_by_group[pays.groups] = discounted(
            amount[pays.groups], payment_factor[pays.groups], pays.tau
        )
        mark = float(npv.sum())
        dv01 = float(dv01_by_group.sum())
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
        # axes the encoding made once, a paid group's nothing on its day, three bincounts.
        axes = cast(PaymentAxes, encoded.payment_axes)  # bilateral and financial: made with it
        dv01_by_day = np.bincount(
            axes.day_of_group, weights=dv01_by_group, minlength=axes.days.size
        )
        dv01_by_month = np.bincount(
            axes.month_of_day, weights=dv01_by_day, minlength=axes.months.size
        )
        dv01_by_year = np.bincount(
            axes.year_of_month, weights=dv01_by_month, minlength=axes.years.size
        )
    unfinished = ~np.isfinite(amount)
    if unfinished.any():
        g = int(unfinished.argmax())
        raise ValueError(
            f"the payment of {codes[int(encoded.group_contract[g])]} on {payment_date[g]} is "
            f"{float(amount[g])!r}, expected a finite amount of {currency}; its fixed, set and "
            "live legs sum past the largest number"
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
    for label, starts, amounts in (
        ("the payment day", axes.days, dv01_by_day),
        ("the payment month from", axes.months, dv01_by_month),
        ("the payment year from", axes.years, dv01_by_year),
    ):  # the three views, not the groups: a bucket's sum can outrun what its parts did not
        outrun = ~np.isfinite(amounts)
        if outrun.any():
            b = int(outrun.argmax())
            raise ValueError(
                f"{label} {starts[b]} has {float(amounts[b])!r} of DV01 in all, expected a finite "
                f"amount of {currency} per basis point; its groups' DV01s sum past the largest "
                "number"
            )
    # Since #197 the cross-gamma, after every rule above and under its own.
    cross_gamma, cross_by_day, cross_by_month, cross_by_year, cross_total, early_cross = (
        _cross_gamma(prepared, pays, discounted_lots, words, as_of)
    )
    # Since #186 the facts refusing a month or a year report of the discounted lots or the DV01
    # standing before the valuation day's period, found once here against the preparation's
    # display axes.
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
    early_dv01 = early_risk(
        f"{curve.name} {currency}",
        "payment",
        as_of,
        f"{currency} per basis point",
        axes.months,
        dv01_by_month,
        prepared.by_month.paid_from,
        axes.years,
        dv01_by_year,
        prepared.by_year.paid_from,
    )
    counter.hit(PAYMENT_FACTORS_READ, int(pays.days.size))
    counter.hit(GROUPS_VALUED, int(pays.groups.size))
    counter.hit(SLOTS_DISCOUNTED, int(encoded.slot_group.size))
    counter.hit(RISK_REDUCTIONS, 11)
    for array in (
        amount,
        npv,
        dv01_by_group,
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
        curve=curve,
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
        cross_gamma_total=cross_total,
        # The curve's share of the DV01 and of the cross-gamma, the whole of each here, by
        # reference to the vectors above and the axes they were summed onto.
        rate_contributions=(
            RateContribution(
                curve,
                currency,
                dv01,
                axes.days,
                dv01_by_day,
                axes.months,
                dv01_by_month,
                axes.years,
                dv01_by_year,
                early_dv01,
            ),
        ),
        cross_contributions=(
            CrossContribution(
                curve,
                encoded.references,
                cross_gamma,
                encoded.days,
                cross_by_day,
                encoded.contract_months,
                cross_by_month,
                encoded.contract_years,
                cross_by_year,
                cross_total,
                early_cross,
            ),
        ),
    )


def _cross_gamma(
    prepared: PreparedTrades,
    pays: UnpaidPayments,
    discounted_lots: NDArray[np.float64],
    words: str,
    as_of: np.datetime64,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    float,
    EarlyRisk,
]:
    """The cross-gamma, since #197, single-curve-cross-gamma.md: by reference, by day, by contract
    month, by contract year and in all, and the facts refusing a month or a year report of it
    standing before the valuation day's period. Each unpaid group's weight is -0.0001 times its
    time fraction, its factor's derivative over the factor for a rise of one basis point in the
    continuously compounded zero rates, the convention the DV01 moves by; a paid group's weight
    is nothing and its factor is read for nothing. The weight is gathered onto the slots as the
    factor was and multiplied into the discounted lots, each payment's own time applied before
    any sum, since two slots of one contract and one day may pay years apart, a fixed slot's lots
    nothing; then the slots are summed onto the references and the days and by reference onto
    the contract months and years, exactly as the discounted lots are, the payment supplying the
    time and never the axis, one path whether any slot is live. The arithmetic runs with numpy's
    flags down and the rules judge: the vector by reference, the three views and the total are
    finite, else the first that is not is refused by its contract, its bucket or the batch; the
    four arrays are frozen.

    Work: one weight per group, one product per slot and four reductions, counted by the caller;
    nothing sorted, no factor and no day read again.
    """
    encoded = prepared.encoded
    terms = encoded.terms
    codes = terms.schedule.codes
    with np.errstate(over="ignore", invalid="ignore"):  # the rules below are the judge
        weight = np.zeros(encoded.group_contract.size)
        weight[pays.groups] = -0.0001 * pays.tau
        by_slot = discounted_lots * weight[encoded.slot_group]
        by_reference = np.bincount(
            encoded.reference_of_slot, weights=by_slot, minlength=encoded.references.size
        )
        by_day = np.bincount(encoded.day_of_slot, weights=by_slot, minlength=encoded.days.size)
        by_month = np.bincount(
            encoded.contract_month_of_reference,
            weights=by_reference,
            minlength=encoded.contract_months.size,
        )
        by_year = np.bincount(
            encoded.contract_year_of_month,
            weights=by_month,
            minlength=encoded.contract_years.size,
        )
        total = float(by_reference.sum())
    per_bp = f"{words} per basis point"
    outrun = ~np.isfinite(by_reference)
    if outrun.any():
        r = int(outrun.argmax())
        raise ValueError(
            f"{codes[int(encoded.references[r])]} has {float(by_reference[r])!r} of cross-gamma, "
            f"expected a finite number of {per_bp}; its discounted lots, each weighted by its "
            "payment's time, sum past the largest number"
        )
    for label, starts, values in (
        ("the day", encoded.days, by_day),
        ("the contract month from", encoded.contract_months, by_month),
        ("the contract year from", encoded.contract_years, by_year),
    ):  # the views before the total: a bucket's sum can outrun what its parts did not
        outrun = ~np.isfinite(values)
        if outrun.any():
            b = int(outrun.argmax())
            raise ValueError(
                f"{label} {starts[b]} has {float(values[b])!r} of cross-gamma in all, expected a "
                f"finite number of {per_bp}; its slots' cross-gammas sum past the largest number"
            )
    if not np.isfinite(total):
        raise ValueError(
            f"the batch has {total!r} of cross-gamma in all, expected a finite number of "
            f"{per_bp}; the contracts' cross-gammas, each finite, sum past the largest number"
        )
    early = early_risk(
        f"index {terms.index.name!r}",
        "contract",
        as_of,
        per_bp,
        encoded.contract_months,
        by_month,
        prepared.by_month.contract_from,
        encoded.contract_years,
        by_year,
        prepared.by_year.contract_from,
    )
    for array in (by_reference, by_day, by_month, by_year):
        array.setflags(write=False)
    return by_reference, by_day, by_month, by_year, total, early
