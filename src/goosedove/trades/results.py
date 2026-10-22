"""What an evaluation saves, and how a report selects from it, in the words of risk_report.py.
TradeResults is the snapshot `trade_results` in evaluation.py makes once for a batch against its
markets, one per leg: the preparation by reference, the values, the bilateral payment facts and
the booked reserves, and per leg, LegResults since two-index-fixed-float.md, the leg's market by
reference and its risk by contract and by date, read-only. risk_view and the helpers beside it
are what _ReportRisk reads from a saved result: a selection by reference, a copy through saved
places where the axis is shared, nothing summed, sorted, priced or discounted here. This module
defines and selects; it never calculates, so it imports the records that precede a result and
nothing of evaluation, aggregation or Excel. docs/library/trades/kernel.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.market.market import Market
from goosedove.trades.contributions import (
    CLEARED,
    CrossContribution,
    RateContribution,
    curve_words,
)
from goosedove.trades.display_axes import EarlyRisk, PeriodAxis, Unit
from goosedove.trades.preparation import PreparedLeg, PreparedTrades
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
class LegResults:
    """One leg's side of a result, since two-index-fixed-float.md: the leg's preparation and the
    market it was valued against, by reference, and the snapshot they make, read-only.
    dated_live_contribution[i] is live slot i's exposure times its reference's quote, paired with
    the preparation's live_slot; their sum is the leg's live amount, and they allocate neither
    the offsets nor the mark among dates. contracts is the leg's axis, the schedule rows of its
    references in the schedule's order, the same whatever has fixed; price_sensitivity[r] is the
    change in mark for a move of one quote unit in contract r, the live exposure referencing it
    and zero where every slot of it has fixed, in price_sensitivity_unit, currency per quote
    currency per quote quantity unit; nominal_delta[r] is the exposure still to price in contract
    r counted in lots of the index's reporting specification, the sensitivity over the lot's
    coefficient, in lot_unit, `lots of LOT (1000 BBL)`, and nominal_delta_total their sum, the
    number the risk report shows as the delta; the three arrays are the preparation's own,
    shared and never written. delta[r], delta_total, discounted_price_sensitivity[r] and the
    discounted daily, monthly and yearly lots are, since #176, the nominal vectors weighted by
    each live slot's payment factor before the sums, the lots the desk hedges to; for a cleared
    batch they are the nominal arrays themselves, by reference, since nothing discounts. Since
    #186 early_delta, the facts refusing a month or a year report whose discounted lots stand in
    a period before the valuation day's, or none, a cleared result's the preparation's nominal
    facts, its lots being the same; a reader words them with the measure asked for and scans
    nothing. Since #197 single-curve-cross-gamma.md cross_contributions, one CrossContribution
    per curve the batch was valued on, in key order: the sensitivity of each contract's delta to
    a rise of one basis point in that curve's continuously compounded zero rates, each live
    slot's discounted lots times -0.0001 times its payment's time fraction, summed by reference,
    by observation day and, by reference, onto the contract months and years, the discounted
    lots' own axes, since the payment supplies the time and not the axis, in lot_unit per basis
    point, negative for lots bought and paid for later, with its total and its early facts, each
    the share of the groups on that curve, the vectors rows of arrays summed by curve at once;
    none for a cleared batch, whose lots nothing discounts, the known zero and no buffer. And
    cross_gamma_total the contributions' totals summed: the leg's cross-gamma with every used
    curve shifted by one basis point together, explicitly not the sensitivity to one curve
    alone, zero for a cleared batch.

    Since the ticket's second pull request the leg's values, retained so that a pair's legs
    are separable: mark, the leg's share of the batch's mark, for a cleared batch its unsettled
    fixed legs, set amounts and live amount, for a bilateral one its NPV; cash, its share of the
    cash, its settled fixed legs and set amounts; dv01, its share of the batch's DV01, the leg's
    DV01 by group summed, zero for a cleared batch; and per group payment_amount[g], the leg's
    fixed leg, set amount and live amount of the group together, npv_by_group[g] that amount
    times the group's factor, zero for a paid group, and dv01_by_group[g] -0.0001 times the
    group's time fraction times that NPV, the three None for a cleared batch; the trade's are
    the legs' summed, and with one leg the leg's are the trade's own, by reference."""

    prepared: PreparedLeg
    market: Market
    mark: float
    cash: float
    dv01: float
    dated_live_contribution: NDArray[np.float64]
    contracts: NDArray[np.intp]
    price_sensitivity: NDArray[np.float64]
    price_sensitivity_unit: str
    nominal_delta: NDArray[np.float64]
    nominal_delta_total: float
    lot_unit: str
    delta: NDArray[np.float64]
    delta_total: float
    discounted_price_sensitivity: NDArray[np.float64]
    discounted_daily_lots: NDArray[np.float64]
    discounted_monthly_lots: NDArray[np.float64]
    discounted_yearly_lots: NDArray[np.float64]
    payment_amount: NDArray[np.float64] | None
    npv_by_group: NDArray[np.float64] | None
    dv01_by_group: NDArray[np.float64] | None
    early_delta: EarlyRisk
    cross_gamma_total: float
    cross_contributions: tuple[CrossContribution, ...]

    def codes(self) -> tuple[str, ...]:
        """The axis spelled as the schedule spells its codes, one per contract of the leg."""
        schedule = self.prepared.encoded.leg.schedule
        return tuple([schedule.codes[int(row)] for row in self.contracts])


@dataclass(frozen=True, slots=True, kw_only=True)
class TradeResults:
    """The preparation by reference, the legs, one LegResults per leg of the preparation in leg
    order, one today, each valued against its own market, and the snapshot the trade makes of
    them together, read-only, since two-index-fixed-float.md. The route and the currency name
    what the numbers are: for a cleared batch, mark is the undiscounted entry-to-current-price
    P&L of the groups not yet settled, live slots at their references' quotes and fixed slots at
    their settles, and cash the cumulative entry-to-final-price P&L of the groups settled by the
    valuation date, both in the settlement currency; dv01 is zero: the cleared model is
    undiscounted, so a rate move changes nothing, a result of the model and not a placeholder.
    as_of is the history's valuation day. reserves, since #170, is the batch's booked brokerage,
    clearing and since #175 marketing and their currency, the encoding's record by reference,
    which no tick changes, _ReportReserves spills and the results readback shows once.

    Since #176, the bilateral fields. curves, since named-curves-slice-3.md, are the exact curve
    objects the batch's keys selected from the collection it was evaluated with, in key order,
    the curves the contributions are owned by, and none for a cleared batch; the collection
    itself is not kept. payment_amount[g] is the group's offset, set amount and live amount
    together over every leg, npv_by_group[g] that amount times its payment factor, zero for a
    paid group, dv01_by_group[g] -0.0001 times the group's day count over 365 times its NPV, and
    payment_factor[g] the factor of the group's own curve, the one its key named, on the group's
    payment day, 1.0 for a paid group, the policy and no read; the four None for a cleared
    batch, which values no group. mark for a bilateral batch is the NPV of the unpaid groups and
    dv01 their sensitivity summed, negative for an amount receivable. Since
    named-curves-slice-2.md the rate risk is kept per curve, as contributions, contributions.py:
    rate_contributions, one RateContribution per curve the batch was valued on, the DV01 by
    payment day, month and year, the groups' DV01s summed since #178 onto the payment-time axes
    the encoding made once, a paid group's nothing on its day, with its total and the facts
    refusing an early month or year, in key order, each the share of the groups on that curve;
    none for a cleared batch. The batch's dv01 is the contributions' totals summed: the batch's
    risk with every used curve shifted by one basis point together, explicitly not the
    sensitivity to one curve alone. The commodity risk and the cross-gamma are each leg's own."""

    prepared: PreparedTrades
    legs: tuple[LegResults, ...]
    route: Route
    currency: str
    as_of: np.datetime64
    mark: float
    cash: float
    dv01: float
    reserves: Reserves
    curves: tuple[DiscountCurve, ...]
    payment_amount: NDArray[np.float64] | None
    npv_by_group: NDArray[np.float64] | None
    dv01_by_group: NDArray[np.float64] | None
    payment_factor: NDArray[np.float64] | None
    rate_contributions: tuple[RateContribution, ...]

    def report(self, risk: Risk, bucket: Bucket) -> RiskView:
        """The content of the risk report asked for, since #180: risk_view's selection of this
        result's saved vectors and totals by reference, what _ReportRisk formats for a result as for
        a collection, whose record answers the same question over its own saved views. Selects, and
        nothing else."""
        return risk_view(self, risk, bucket)


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
    leg = results.legs[0]  # one leg today: its index names the deltas and the cross-gamma
    leg_terms = leg.prepared.encoded.leg
    nominal_label, delta_label = delta_labels(leg_terms.index, leg_terms.reporting_lot)
    rates = results.rate_contributions
    crosses = leg.cross_contributions
    if rates or crosses:
        words = curve_words([c.curve for c in (*rates, *crosses)])
        dv01_labels = tuple([dv01_label(words[id(c.curve)], c.currency) for c in rates])
        cross_labels = tuple(
            [
                cross_gamma_label(leg_terms.index, words[id(c.curve)], leg_terms.reporting_lot)
                for c in crosses
            ]
        )
    else:
        # Cleared: no curve values, the one DV01 column and the one cross-gamma column of nothing.
        dv01_labels = (dv01_label(CLEARED, results.currency),)
        cross_labels = (cross_gamma_label(leg_terms.index, CLEARED, leg_terms.reporting_lot),)
    labels: Labels = (nominal_label, delta_label, dv01_labels, cross_labels)
    match bucket:
        case Bucket.DAY:
            return _day_view(results, risk, labels)
        case Bucket.MONTH | Bucket.YEAR:
            return _period_view(results, risk, bucket, labels)
        case _:
            assert_never(bucket)


def _day_view(results: TradeResults, risk: Risk, labels: Labels) -> RiskView:
    """The day report's content, by reference where the axis is the risk's own: the deltas
    and the cross-gamma the one leg's today, the DV01 the trade's."""
    leg = results.legs[0]
    prepared = leg.prepared
    encoded = prepared.encoded
    nominal_label, delta_label, dv01_labels, cross_labels = labels
    rates = results.rate_contributions
    crosses = leg.cross_contributions
    axes = results.prepared.encoded.payment_axes
    match risk:
        case Risk.NOMINAL_DELTA:
            return RiskView(
                encoded.days,
                (nominal_label,),
                (leg.nominal_delta_total,),
                (prepared.daily_lots,),
            )
        case Risk.DELTA:
            return RiskView(
                encoded.days,
                (delta_label,),
                (leg.delta_total,),
                (leg.discounted_daily_lots,),
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
                return RiskView(encoded.days, cross_labels, (leg.cross_gamma_total,), (zeros,))
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
                else (leg.cross_gamma_total,)
            )
            totals = (
                leg.nominal_delta_total,
                leg.delta_total,
                *dv01_totals,
                *cross_totals,
            )
            if axes is None:
                # Cleared: the observation days, the DV01 and the cross-gamma nothing on every row.
                columns = (
                    prepared.daily_lots,
                    leg.discounted_daily_lots,
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
                    placed(union.size, axes.observed_in_days, leg.discounted_daily_lots),
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
    leg = results.legs[0]  # one leg today: its lots, on its display axes
    prepared = leg.prepared
    nominal_label, delta_label, dv01_labels, cross_labels = labels
    rates = results.rate_contributions
    crosses = leg.cross_contributions
    unit, axis, nominal, discounted = _saved(leg, bucket)
    match risk:
        case Risk.NOMINAL_DELTA:
            prepared.early_nominal.refuse("nominal delta", unit)
            column = placed(axis.delta_rows, axis.contract_in, nominal[axis.contract_from :])
            return RiskView(
                axis.periods[: axis.delta_rows],
                (nominal_label,),
                (leg.nominal_delta_total,),
                (column,),
            )
        case Risk.DELTA:
            leg.early_delta.refuse("delta", unit)
            column = placed(axis.delta_rows, axis.contract_in, discounted[axis.contract_from :])
            return RiskView(
                axis.periods[: axis.delta_rows],
                (delta_label,),
                (leg.delta_total,),
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
                    (leg.cross_gamma_total,),
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
    leg = results.legs[0]
    prepared = leg.prepared
    nominal_label, delta_label, dv01_labels, cross_labels = labels
    rates = results.rate_contributions
    crosses = leg.cross_contributions
    prepared.early_nominal.refuse("nominal delta", unit)
    leg.early_delta.refuse("delta", unit)
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
        cross_on, cross_totals = [np.zeros(rows)], [leg.cross_gamma_total]
    return RiskView(
        axis.periods[:rows],
        (nominal_label, delta_label, *dv01_labels, *cross_labels),
        (
            leg.nominal_delta_total,
            leg.delta_total,
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
    results: LegResults, bucket: Period
) -> tuple[Unit, PeriodAxis, NDArray[np.float64], NDArray[np.float64]]:
    """A month or a year bucket's unit, the leg's display axis and the saved lot vectors it
    places, the nominal lots and the discounted lots; the DV01 and the cross-gamma are each
    contribution's."""
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
