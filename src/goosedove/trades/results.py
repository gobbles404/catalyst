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
from typing import assert_never, cast

import numpy as np
from numpy.typing import NDArray

from goosedove.globals.discount_curve import DiscountCurve
from goosedove.market.market import Market
from goosedove.trades.display_axes import EarlyRisk, PeriodAxis, Unit
from goosedove.trades.preparation import PreparedTrades
from goosedove.trades.reserves import Reserves
from goosedove.trades.risk_report import NO_DAYS, NOTHING, Bucket, Period, Risk, RiskView, placed
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

    Since #178, dv01_by_day[d], dv01_by_month[m] and dv01_by_year[y]: the groups' DV01s summed
    onto the payment-time axes the encoding made once, the day a group's amount is paid, the
    calendar month it falls in and the calendar year, a paid group's nothing on its day, each
    view checked finite; None for a cleared batch, whose DV01 has no dated axis. _ReportRisk
    reads them by reference through risk_view. Since #186 early_delta and early_dv01, the facts
    refusing a month or a year report whose discounted lots or DV01 stand in a period before the
    valuation day's, or none, a cleared result's delta the preparation's nominal facts, its lots
    being the same, and its DV01 none; a reader words them with the measure asked for and
    scans nothing."""

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
    dv01_by_day: NDArray[np.float64] | None
    dv01_by_month: NDArray[np.float64] | None
    dv01_by_year: NDArray[np.float64] | None
    early_delta: EarlyRisk
    early_dv01: EarlyRisk

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


def risk_view(results: TradeResults, risk: Risk, bucket: Bucket) -> RiskView:
    """The one way to read a risk report's content, since #178, _ReportRisk's selection. By day:
    the nominal delta and the delta are on the observation days, the preparation's vector and the
    result's, totalled by the saved scalars; the DV01 is on the payment days, the result's vector
    the evaluation summed onto the axis the encoding made once, totalled by the saved DV01, a
    cleared result's a total of nothing over no dated row, its DV01 having no dated axis; all three
    are on the union of the two axes the encoding made, each vector copied through its saved
    places and zero where only the other kind has a date, a cleared result's all on the
    observation days with a DV01 column of zeros. By month or by year, since #186,
    risk-contract-month-bucketing.md: the preparation's display axis, consecutive periods from the
    valuation day's, a delta report through the last contract period and a DV01 report through
    the last payment period, all three through the later, each saved vector copied through the
    places the preparation saved and zero between them; a saved value before the start refuses the
    report in the words prepared where the vector was made. The labels name the index and its
    reporting lot for the deltas, `UNIT delta [UNIT]`, and the curve's group and the currency for
    the DV01, `curve_1 USD dv01 [USD per basis point]`, `cleared USD dv01 [USD per basis point]`
    where no curve values.

    Work: a copy per column through the saved places, by reference where a day axis is the
    risk's own; nothing summed, nothing sorted, nothing discovered, the Total the scalar the
    evaluation stored.
    """
    terms = results.prepared.encoded.terms
    currency = results.currency
    nominal_label = f"{terms.index.name} nominal_delta [{terms.reporting_lot.name}]"
    delta_label = f"{terms.index.name} delta [{terms.reporting_lot.name}]"
    group = "curve_1" if results.curve is not None else "cleared"
    dv01_label = f"{group} {currency} dv01 [{currency} per basis point]"
    labels = (nominal_label, delta_label, dv01_label)
    match bucket:
        case Bucket.DAY:
            return _day_view(results, risk, labels)
        case Bucket.MONTH | Bucket.YEAR:
            return _period_view(results, risk, bucket, labels)
        case _:
            assert_never(bucket)


def _day_view(results: TradeResults, risk: Risk, labels: tuple[str, str, str]) -> RiskView:
    """The day report's content, by reference where the axis is the risk's own."""
    prepared = results.prepared
    encoded = prepared.encoded
    nominal_label, delta_label, dv01_label = labels
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
            if axes is None:
                return RiskView(NO_DAYS, (dv01_label,), (results.dv01,), (NOTHING,))
            dv01 = cast(NDArray[np.float64], results.dv01_by_day)  # made with the axes
            return RiskView(axes.days, (dv01_label,), (results.dv01,), (dv01,))
        case Risk.ALL:
            totals = (results.lot_delta_total, results.discounted_lot_delta_total, results.dv01)
            if axes is None:
                # Cleared: the observation days, the DV01 nothing on every row.
                columns = (
                    prepared.daily_lots,
                    results.discounted_daily_lots,
                    np.zeros(encoded.days.size),
                )
                return RiskView(encoded.days, labels, totals, columns)
            union = axes.union_days
            return RiskView(
                union,
                labels,
                totals,
                (
                    placed(union.size, axes.observed_in_days, prepared.daily_lots),
                    placed(union.size, axes.observed_in_days, results.discounted_daily_lots),
                    placed(
                        union.size,
                        axes.paid_in_days,
                        cast(NDArray[np.float64], results.dv01_by_day),
                    ),
                ),
            )
        case _:
            assert_never(risk)


def _period_view(
    results: TradeResults, risk: Risk, bucket: Period, labels: tuple[str, str, str]
) -> RiskView:
    """The month or the year report's content, since #186: the preparation's display axis cut to
    the selected risks' rows, the saved vectors copied through the saved places from the first
    period on or after the start, a saved value before it refused from the saved facts, worded
    with the measure asked for."""
    prepared = results.prepared
    nominal_label, delta_label, dv01_label = labels
    unit, axis, nominal, discounted, dv01 = _saved(results, bucket)
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
            if dv01 is None:
                return RiskView(NO_DAYS, (dv01_label,), (results.dv01,), (NOTHING,))
            results.early_dv01.refuse("DV01", unit)
            column = placed(axis.dv01_rows, axis.paid_in, dv01[axis.paid_from :])
            return RiskView(
                axis.periods[: axis.dv01_rows], (dv01_label,), (results.dv01,), (column,)
            )
        case Risk.ALL:
            prepared.early_nominal.refuse("nominal delta", unit)
            results.early_delta.refuse("delta", unit)
            rows = max(axis.delta_rows, axis.dv01_rows)
            totals = (results.lot_delta_total, results.discounted_lot_delta_total, results.dv01)
            if dv01 is None:
                dv01_on = np.zeros(rows)
            else:
                results.early_dv01.refuse("DV01", unit)
                dv01_on = placed(rows, axis.paid_in, dv01[axis.paid_from :])
            return RiskView(
                axis.periods[:rows],
                labels,
                totals,
                (
                    placed(rows, axis.contract_in, nominal[axis.contract_from :]),
                    placed(rows, axis.contract_in, discounted[axis.contract_from :]),
                    dv01_on,
                ),
            )
        case _:
            assert_never(risk)


def _saved(
    results: TradeResults, bucket: Period
) -> tuple[Unit, PeriodAxis, NDArray[np.float64], NDArray[np.float64], NDArray[np.float64] | None]:
    """A month or a year bucket's unit, its display axis and the saved vectors it places: the
    nominal lots, the discounted lots and the DV01, None where the DV01 has no dated axis."""
    prepared = results.prepared
    match bucket:
        case Bucket.MONTH:
            return (
                "M",
                prepared.by_month,
                prepared.monthly_lots,
                results.discounted_monthly_lots,
                results.dv01_by_month,
            )
        case Bucket.YEAR:
            return (
                "Y",
                prepared.by_year,
                prepared.yearly_lots,
                results.discounted_yearly_lots,
                results.dv01_by_year,
            )
        case _:
            assert_never(bucket)
