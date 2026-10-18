"""What an evaluation saves, and how a report selects from it, in the words of risk_report.py.
TradeResults is the snapshot `trade_results` in evaluation.py makes once for a batch against one
market: the preparation and
the market by reference, the values, the risk by contract and by date, the bilateral payment facts
and the booked reserves, read-only. risk_view and the helpers beside it are what _ReportRisk reads
from a saved result: a selection by reference, a copy through saved places where the axis is
shared, nothing summed, sorted, priced or discounted here. This module defines and selects; it
never calculates, so it imports the records that precede a result and nothing of evaluation,
aggregation or Excel. docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.market.market import Market
from goosedove.trades.contributions import CrossContribution, RateContribution, curve_words
from goosedove.trades.display_axes import EarlyRisk, PeriodAxis, Unit
from goosedove.trades.preparation import PreparedTrades
from goosedove.trades.reserves import Reserves
from goosedove.trades.risk_report import (
    NO_DAYS,
    NOTHING,
    Bucket,
    Period,
    Risk,
    RiskView,
    cross_gamma_label,
    delta_labels,
    dv01_label,
    placed,
)
from goosedove.trades.terms import Route


@dataclass(frozen=True, slots=True, kw_only=True)
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
    negative for an amount receivable.

    Since #186 early_delta, the facts refusing a month or a year report whose discounted lots
    stand in a period before the valuation day's, or none, a cleared result's the preparation's
    nominal facts, its lots being the same; a reader words them with the measure asked for and
    scans nothing.

    Since named-curves-slice-2.md the rate risk and the cross-gamma are kept per curve, as
    contributions, contributions.py: rate_contributions, one RateContribution per curve the
    batch was valued on, the DV01 by payment day, month and year, the groups' DV01s summed
    since #178 onto the payment-time axes the encoding made once, a paid group's nothing on
    its day, with its total and the facts refusing an early month or year; and
    cross_contributions, one CrossContribution per curve, since #197 single-curve-cross-gamma.md:
    the sensitivity of each contract's discounted lot delta to a rise of one basis point in
    that curve's continuously compounded zero rates, each live slot's discounted lots times
    -0.0001 times its payment's time fraction, summed by reference, by observation day and,
    by reference, onto the contract months and years, the discounted lots' own axes, since
    the payment supplies the time and not the axis, in lot_unit per basis point, negative for
    lots bought and paid for later, with its total and its early facts. One of each today,
    the batch being valued on one curve; none for a cleared batch, whose lots nothing
    discounts, the known zero and no buffer. The batch's dv01 and cross_gamma_total stay:
    the batch's risk with every used curve shifted by one basis point together, the one
    contribution's total today and the sum of the contributions' when a batch is valued on
    several, explicitly not the sensitivity to one curve alone."""

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
    early_delta: EarlyRisk
    cross_gamma_total: float
    rate_contributions: tuple[RateContribution, ...]
    cross_contributions: tuple[CrossContribution, ...]

    def report(self, risk: Risk, bucket: Bucket) -> RiskView:
        """The content of the risk report asked for, since #180: risk_view's selection of this
        result's saved vectors and totals by reference, what _ReportRisk formats for a result as for
        a collection, whose record answers the same question over its own saved views. Selects, and
        nothing else."""
        return risk_view(self, risk, bucket)

    def codes(self) -> tuple[str, ...]:
        """The axis spelled as the schedule spells its codes, one per contract of the batch."""
        schedule = self.prepared.encoded.terms.schedule
        return tuple([schedule.codes[int(row)] for row in self.contracts])


Labels = tuple[str, str, tuple[str, ...], tuple[str, ...]]


def risk_view(results: TradeResults, risk: Risk, bucket: Bucket) -> RiskView:
    """The one way to read a risk report's content, since #178, _ReportRisk's selection. By day:
    the nominal delta and the delta are on the observation days, the preparation's vector and the
    result's, totalled by the saved scalars; the DV01 is on the payment days, one column per rate
    contribution, the contribution's vector on the axis the encoding made once, totalled by the
    contribution's DV01, a cleared result's a total of nothing over no dated row, its DV01 having
    no dated axis; since #197 the cross-gamma is on the observation days as the delta is, one
    column per cross contribution with its saved total, a cleared result's the known zero shown as
    a column of zeros on those days; all four are on the union of the two axes the encoding made,
    each vector copied through its saved places and zero where only the other kind has a date, a
    cleared result's all on the observation days with a DV01 column and a cross-gamma column of
    zeros. By month or by year, since #186, risk-contract-month-bucketing.md: the preparation's
    display axis, consecutive periods from the valuation day's, a delta or a cross-gamma report
    through the last contract period and a DV01 report through the last payment period, all four
    through the later, each saved vector copied through the places the preparation saved and zero
    between them; a saved value before the start refuses the report in the words prepared where
    the vector was made. The labels name the index and its reporting lot for the deltas, `UNIT
    delta [UNIT]`, the curve's name and the currency for a DV01, `SOFR USD dv01 [USD per basis
    point]`, `cleared USD dv01 [USD per basis point]` where no curve values, and the index, the
    curve's name and the lot per basis point for a cross-gamma, `UNIT SOFR cross_gamma [UNIT per
    basis point]`; a result on one curve names it bare, and two curves of one name on one result
    are two words, `SOFR (curve_1)` and `SOFR (curve_2)`.

    Work: a copy per column through the saved places, by reference where a day axis is the
    risk's own, a column of zeros for a cleared result's cross-gamma; nothing summed, nothing
    sorted, nothing discovered, the Total the scalar the evaluation stored.
    """
    terms = results.prepared.encoded.terms
    nominal_label, delta_label = delta_labels(terms.index, terms.reporting_lot)
    rates = results.rate_contributions
    crosses = results.cross_contributions
    if rates or crosses:
        words = curve_words([c.curve for c in (*rates, *crosses)])
        dv01_labels = tuple([dv01_label(words[id(c.curve)], c.currency) for c in rates])
        cross_labels = tuple(
            [
                cross_gamma_label(terms.index, words[id(c.curve)], terms.reporting_lot)
                for c in crosses
            ]
        )
    else:
        # Cleared: no curve values, the one DV01 column and the one cross-gamma column of nothing.
        dv01_labels = (dv01_label("cleared", results.currency),)
        cross_labels = (cross_gamma_label(terms.index, "cleared", terms.reporting_lot),)
    labels: Labels = (nominal_label, delta_label, dv01_labels, cross_labels)
    match bucket:
        case Bucket.DAY:
            return _day_view(results, risk, labels)
        case Bucket.MONTH | Bucket.YEAR:
            return _period_view(results, risk, bucket, labels)
        case _:
            assert_never(bucket)


def _day_view(results: TradeResults, risk: Risk, labels: Labels) -> RiskView:
    """The day report's content, by reference where the axis is the risk's own."""
    prepared = results.prepared
    encoded = prepared.encoded
    nominal_label, delta_label, dv01_labels, cross_labels = labels
    rates = results.rate_contributions
    crosses = results.cross_contributions
    axes = encoded.payment_axes
    match risk:
        case Risk.NOMINAL_DELTA:
            return RiskView(
                encoded.days, (nominal_label,), (results.lot_delta_total,), (prepared.daily_lots,)
            )
        case Risk.DELTA:
            return RiskView(
                encoded.days,
                (delta_label,),
                (results.discounted_lot_delta_total,),
                (results.discounted_daily_lots,),
            )
        case Risk.DV01:
            if not rates:
                return RiskView(NO_DAYS, dv01_labels, (results.dv01,), (NOTHING,))
            # Every contribution of a batch stands on the batch's payment days, made with them.
            return RiskView(
                rates[0].days,
                dv01_labels,
                tuple([c.dv01 for c in rates]),
                tuple([c.dv01_by_day for c in rates]),
            )
        case Risk.CROSS_GAMMA:
            if not crosses:
                # Cleared: the known zero on the observation days, the column made for the report.
                zeros = np.zeros(encoded.days.size)
                return RiskView(encoded.days, cross_labels, (results.cross_gamma_total,), (zeros,))
            return RiskView(
                encoded.days,
                cross_labels,
                tuple([c.cross_gamma_total for c in crosses]),
                tuple([c.cross_gamma_by_day for c in crosses]),
            )
        case Risk.ALL:
            every = (nominal_label, delta_label, *dv01_labels, *cross_labels)
            dv01_totals = tuple([c.dv01 for c in rates]) if rates else (results.dv01,)
            cross_totals = (
                tuple([c.cross_gamma_total for c in crosses])
                if crosses
                else (results.cross_gamma_total,)
            )
            totals = (
                results.lot_delta_total,
                results.discounted_lot_delta_total,
                *dv01_totals,
                *cross_totals,
            )
            if axes is None:
                # Cleared: the observation days, the DV01 and the cross-gamma nothing on every row.
                columns = (
                    prepared.daily_lots,
                    results.discounted_daily_lots,
                    *[np.zeros(encoded.days.size) for _ in dv01_totals],
                    *[np.zeros(encoded.days.size) for _ in cross_totals],
                )
                return RiskView(encoded.days, every, totals, columns)
            union = axes.union_days
            return RiskView(
                union,
                every,
                totals,
                (
                    placed(union.size, axes.observed_in_days, prepared.daily_lots),
                    placed(union.size, axes.observed_in_days, results.discounted_daily_lots),
                    *[placed(union.size, axes.paid_in_days, c.dv01_by_day) for c in rates],
                    *[
                        placed(union.size, axes.observed_in_days, c.cross_gamma_by_day)
                        for c in crosses
                    ],  # made with the observation days
                ),
            )
        case _:
            assert_never(risk)


def _period_view(results: TradeResults, risk: Risk, bucket: Period, labels: Labels) -> RiskView:
    """The month or the year report's content, since #186: the preparation's display axis cut to
    the selected risks' rows, the saved vectors copied through the saved places from the first
    period on or after the start, a saved value before it refused from the saved facts, worded
    with the measure asked for; since #197 the cross-gamma on the delta's rows and places, a
    cleared result's the known zero as a column of zeros; one column per contribution."""
    prepared = results.prepared
    nominal_label, delta_label, dv01_labels, cross_labels = labels
    rates = results.rate_contributions
    crosses = results.cross_contributions
    unit, axis, nominal, discounted = _saved(results, bucket)
    match risk:
        case Risk.NOMINAL_DELTA:
            prepared.early_nominal.refuse("nominal delta", unit)
            column = placed(axis.delta_rows, axis.contract_in, nominal[axis.contract_from :])
            return RiskView(
                axis.periods[: axis.delta_rows],
                (nominal_label,),
                (results.lot_delta_total,),
                (column,),
            )
        case Risk.DELTA:
            results.early_delta.refuse("delta", unit)
            column = placed(axis.delta_rows, axis.contract_in, discounted[axis.contract_from :])
            return RiskView(
                axis.periods[: axis.delta_rows],
                (delta_label,),
                (results.discounted_lot_delta_total,),
                (column,),
            )
        case Risk.DV01:
            if not rates:
                return RiskView(NO_DAYS, dv01_labels, (results.dv01,), (NOTHING,))
            for c in rates:
                c.early_dv01.refuse("DV01", unit)
            columns = tuple(
                [
                    placed(axis.dv01_rows, axis.paid_in, _dv01_of(c, bucket)[axis.paid_from :])
                    for c in rates
                ]
            )
            return RiskView(
                axis.periods[: axis.dv01_rows], dv01_labels, tuple([c.dv01 for c in rates]), columns
            )
        case Risk.CROSS_GAMMA:
            if not crosses:
                zeros = np.zeros(axis.delta_rows)  # cleared: the known zero over the delta rows
                return RiskView(
                    axis.periods[: axis.delta_rows],
                    cross_labels,
                    (results.cross_gamma_total,),
                    (zeros,),
                )
            for c in crosses:
                c.early_cross_gamma.refuse("cross-gamma", unit)
            columns = tuple(
                [
                    placed(
                        axis.delta_rows,
                        axis.contract_in,
                        _cross_of(c, bucket)[axis.contract_from :],
                    )
                    for c in crosses
                ]
            )
            return RiskView(
                axis.periods[: axis.delta_rows],
                cross_labels,
                tuple([c.cross_gamma_total for c in crosses]),
                columns,
            )
        case Risk.ALL:
            return _period_all(results, bucket, unit, axis, labels, nominal, discounted)
        case _:
            assert_never(risk)


def _period_all(
    results: TradeResults,
    bucket: Period,
    unit: Unit,
    axis: PeriodAxis,
    labels: Labels,
    nominal: NDArray[np.float64],
    discounted: NDArray[np.float64],
) -> RiskView:
    """All four by month or by year: the two deltas, then a DV01 column per rate contribution and
    a cross-gamma column per cross contribution, a cleared result's one of each at zero, on the
    display axis through the later of the delta rows and the DV01 rows."""
    prepared = results.prepared
    nominal_label, delta_label, dv01_labels, cross_labels = labels
    rates = results.rate_contributions
    crosses = results.cross_contributions
    prepared.early_nominal.refuse("nominal delta", unit)
    results.early_delta.refuse("delta", unit)
    rows = max(axis.delta_rows, axis.dv01_rows)
    if rates:
        for c in rates:
            c.early_dv01.refuse("DV01", unit)
        dv01_on = [placed(rows, axis.paid_in, _dv01_of(c, bucket)[axis.paid_from :]) for c in rates]
        dv01_totals = [c.dv01 for c in rates]
    else:
        dv01_on, dv01_totals = [np.zeros(rows)], [results.dv01]
    if crosses:
        for c in crosses:
            c.early_cross_gamma.refuse("cross-gamma", unit)
        cross_on = [
            placed(rows, axis.contract_in, _cross_of(c, bucket)[axis.contract_from :])
            for c in crosses
        ]
        cross_totals = [c.cross_gamma_total for c in crosses]
    else:
        cross_on, cross_totals = [np.zeros(rows)], [results.cross_gamma_total]
    return RiskView(
        axis.periods[:rows],
        (nominal_label, delta_label, *dv01_labels, *cross_labels),
        (
            results.lot_delta_total,
            results.discounted_lot_delta_total,
            *dv01_totals,
            *cross_totals,
        ),
        (
            placed(rows, axis.contract_in, nominal[axis.contract_from :]),
            placed(rows, axis.contract_in, discounted[axis.contract_from :]),
            *dv01_on,
            *cross_on,
        ),
    )


def _saved(
    results: TradeResults, bucket: Period
) -> tuple[Unit, PeriodAxis, NDArray[np.float64], NDArray[np.float64]]:
    """A month or a year bucket's unit, its display axis and the saved lot vectors it places, the
    nominal lots and the discounted lots; the DV01 and the cross-gamma are each contribution's."""
    prepared = results.prepared
    match bucket:
        case Bucket.MONTH:
            return "M", prepared.by_month, prepared.monthly_lots, results.discounted_monthly_lots
        case Bucket.YEAR:
            return "Y", prepared.by_year, prepared.yearly_lots, results.discounted_yearly_lots
        case _:
            assert_never(bucket)


def _dv01_of(contribution: RateContribution, bucket: Period) -> NDArray[np.float64]:
    match bucket:
        case Bucket.MONTH:
            return contribution.dv01_by_month
        case Bucket.YEAR:
            return contribution.dv01_by_year
        case _:
            assert_never(bucket)


def _cross_of(contribution: CrossContribution, bucket: Period) -> NDArray[np.float64]:
    match bucket:
        case Bucket.MONTH:
            return contribution.cross_gamma_by_month
        case Bucket.YEAR:
            return contribution.cross_gamma_by_year
        case _:
            assert_never(bucket)
