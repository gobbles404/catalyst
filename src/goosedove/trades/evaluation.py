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
weighted by its group's factor, summed onto the references, the days, the months and the years
beside the nominal vectors the preparation shares; a cleared batch takes no curve and is as it was.
docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.instrumentation.work_counts import KERNEL, WorkCounter
from goosedove.market.market import Market
from goosedove.trades.preparation import PreparedTrades, UnpaidPayments
from goosedove.trades.reserves import Reserves
from goosedove.trades.terms import Route, Settlement

LIVE_PRICES_READ = "live_prices_read"  # quotes read off the market, one per live reference
# The bilateral path's counts, since #176: factors read off the curve, one per distinct unpaid
# payment day; unpaid groups discounted, each with its time fraction and its DV01; live slots
# weighted by their group's factor; and the reductions of the discounted lots, onto the
# references, the days, the months and the years.
PAYMENT_FACTORS_READ = "payment_factors_read"
GROUPS_VALUED = "groups_valued"
SLOTS_DISCOUNTED = "slots_discounted"
RISK_REDUCTIONS = "risk_reductions"


@dataclass(frozen=True, slots=True)
class TradeResults:
    """The preparation and the market, by reference, and the snapshot they make, read-only. The
    route and the currency name what the numbers are: for a cleared batch, mark is the
    undiscounted entry-to-current-price P&L of the groups not yet settled, live slots at their
    references' quotes and fixed slots at their settles, and cash the cumulative
    entry-to-final-price P&L of the groups settled by the valuation date, both in the settlement
    currency. dated_live_contribution[i] is live slot i's exposure times its reference's quote,
    paired with the preparation's live_slot; their sum is the live amount, and they allocate
    neither the offsets nor the mark among dates. contracts is the batch's axis, the schedule
    rows of its references in the schedule's order, the same whatever has fixed;
    price_sensitivity[r] is the change in mark for a move of one quote unit in contract r, the
    live exposure referencing it and zero where every slot of it has fixed, in
    price_sensitivity_unit, currency per quote currency per quote quantity unit; lot_delta[r] is
    the exposure still to price in contract r counted in lots of the index's reporting
    specification, the sensitivity over the lot's coefficient, in lot_unit, `lots of LOT (1000
    BBL)`, and lot_delta_total their sum, the number the risk report shows as the delta; the
    three arrays are the preparation's own, shared and never written. dv01 is zero: the cleared
    model is undiscounted, so a rate move changes nothing, a result of the model and not a
    placeholder. as_of is the history's valuation day. reserves, since #170, is the batch's
    booked brokerage, clearing and since #175 marketing and their currency, the encoding's
    record by reference, which no tick changes, _ReportReserves spills and the results
    readback shows once.

    Since #176, the bilateral fields. curve is the discount curve the batch was valued on, None for
    a cleared batch. discounted_lot_delta[r], discounted_lot_delta_total,
    discounted_price_sensitivity[r] and the discounted daily, monthly and yearly lots are the
    nominal vectors weighted by each live slot's payment factor before the sums, the lots the desk
    hedges to; for a cleared batch they are
    the nominal arrays themselves, by reference, since nothing discounts. payment_amount[g] is the
    group's offset, set amount and live amount together, npv_by_group[g] that amount times its
    payment factor, zero for a paid group, dv01_by_group[g] -0.0001 times the group's day count over
    365 times its NPV, and payment_factor[g] the curve's factor on the group's payment day, 1.0 for
    a paid group, the policy and no read; the four None for a cleared batch, which values no group.
    mark for a bilateral batch is the NPV of the unpaid groups and dv01 their sensitivity summed,
    negative for an amount receivable."""

    prepared: PreparedTrades
    market: Market
    route: Route
    currency: str
    as_of: np.datetime64
    mark: float
    cash: float
    dated_live_contribution: NDArray[np.float64]
    contracts: NDArray[np.intp]
    price_sensitivity: NDArray[np.float64]
    price_sensitivity_unit: str
    lot_delta: NDArray[np.float64]
    lot_delta_total: float
    lot_unit: str
    dv01: float
    reserves: Reserves
    curve: DiscountCurve | None
    discounted_lot_delta: NDArray[np.float64]
    discounted_lot_delta_total: float
    discounted_price_sensitivity: NDArray[np.float64]
    discounted_daily_lots: NDArray[np.float64]
    discounted_monthly_lots: NDArray[np.float64]
    discounted_yearly_lots: NDArray[np.float64]
    payment_amount: NDArray[np.float64] | None
    npv_by_group: NDArray[np.float64] | None
    dv01_by_group: NDArray[np.float64] | None
    payment_factor: NDArray[np.float64] | None

    def codes(self) -> tuple[str, ...]:
        """The axis spelled as the schedule spells its codes, one per contract of the batch."""
        schedule = self.prepared.encoded.terms.schedule
        return tuple([schedule.codes[int(row)] for row in self.contracts])


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
    quotes are gathered onto the live slots, each slot's exposure times its reference's quote is
    its contribution, and the live amount is their sum. For a cleared batch the mark is the
    unsettled offsets and set amounts plus the live amount, the cash the preparation's, the
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
    dated_live_contribution = (
        prepared.dated_live_exposure[prepared.live_slot] * quotes[prepared.reference_of_live_slot]
    )
    live = float(dated_live_contribution.sum())
    counter.hit(KERNEL)
    counter.hit(LIVE_PRICES_READ, int(prepared.live_references.size))
    dated_live_contribution.setflags(write=False)
    if curve is not None:
        return _discounted(prepared, market, curve, dated_live_contribution, counter)
    conventions = terms.index.conventions
    return TradeResults(
        prepared,
        market,
        terms.route,
        conventions.currency_unit,
        prepared.history.calendar.valuation_date.as_of,
        prepared.offset_unsettled + prepared.set_unsettled + live,
        prepared.cash,
        dated_live_contribution,
        prepared.encoded.references,
        prepared.price_sensitivity,
        f"{conventions.currency_unit} per {conventions.quote_currency_unit}/"
        f"{conventions.quote_quantity_unit}",
        prepared.lot_delta,
        prepared.lot_delta_total,
        terms.reporting_lot.words,
        0.0,
        prepared.encoded.reserves,
        None,
        prepared.lot_delta,
        prepared.lot_delta_total,
        prepared.price_sensitivity,
        prepared.daily_lots,
        prepared.monthly_lots,
        prepared.yearly_lots,
        None,
        None,
        None,
        None,
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
    as_of = prepared.history.calendar.valuation_date.as_of
    if curve.start_date != as_of:
        raise ValueError(
            f"discount_curve starts on {curve.start_date}, expected {as_of}, the valuation date; "
            "a curve is never rebased"
        )
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
    receivable. The discounted lots are each live slot's lots times its group's factor, before any
    sum, since two slots of one day and one contract may pay on different days; summed onto the
    references, the days, the months and the years as the preparation sums the nominal lots, and
    the discounted sensitivity the lots times the reporting lot's coefficient, the one conversion
    the index resolved. The arithmetic runs with numpy's flags down and the rules judge: every
    group's amount, the two totals, the discounted lots by reference and by bucket, the discounted
    sensitivity by reference and the lots' total are finite, else the first that is not is refused
    by its group, the batch, its contract or its bucket.

    Work: one factor per distinct unpaid payment day, one group per unpaid group, one slot per
    live slot and four reductions, reported to the counter; nothing per component or observation,
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
        payment_factor[pays.groups] = curve.factors[(pays.days - curve.start_date).astype(np.intp)][
            pays.day_of_group
        ]
        npv = np.zeros(groups)
        npv[pays.groups] = amount[pays.groups] * payment_factor[pays.groups]
        dv01_by_group = np.zeros(groups)
        dv01_by_group[pays.groups] = -0.0001 * pays.tau * npv[pays.groups]
        mark = float(npv.sum())
        dv01 = float(dv01_by_group.sum())
        live_lots = prepared.dated_live_lots[prepared.live_slot] * payment_factor[live_group]
        discounted_lot_delta = np.bincount(
            encoded.reference_of_slot[prepared.live_slot],
            weights=live_lots,
            minlength=encoded.references.size,
        )
        discounted_price_sensitivity = discounted_lot_delta * lot.coefficient
        daily = np.bincount(
            encoded.day_of_slot[prepared.live_slot], weights=live_lots, minlength=encoded.days.size
        )
        monthly = np.bincount(encoded.month_of_day, weights=daily, minlength=encoded.months.size)
        yearly = np.bincount(encoded.year_of_month, weights=monthly, minlength=encoded.years.size)
        discounted_total = float(discounted_lot_delta.sum())
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
        ("the month from", encoded.months, monthly),
        ("the year from", encoded.years, yearly),
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
    counter.hit(PAYMENT_FACTORS_READ, int(pays.days.size))
    counter.hit(GROUPS_VALUED, int(pays.groups.size))
    counter.hit(SLOTS_DISCOUNTED, int(prepared.live_slot.size))
    counter.hit(RISK_REDUCTIONS, 4)
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
    ):
        array.setflags(write=False)
    return TradeResults(
        prepared,
        market,
        terms.route,
        currency,
        as_of,
        mark,
        prepared.cash,
        dated_live_contribution,
        encoded.references,
        prepared.price_sensitivity,
        f"{currency} per {conventions.quote_currency_unit}/{conventions.quote_quantity_unit}",
        prepared.lot_delta,
        prepared.lot_delta_total,
        words,
        dv01,
        encoded.reserves,
        curve,
        discounted_lot_delta,
        discounted_total,
        discounted_price_sensitivity,
        daily,
        monthly,
        yearly,
        amount,
        npv,
        dv01_by_group,
        payment_factor,
    )
