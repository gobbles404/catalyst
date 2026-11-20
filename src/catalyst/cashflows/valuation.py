"""A batch of cashflows valued on a valuation day over a collection of named discount curves,
cashflow-instrument.md and, since cashflow-curve-keys.md, each payment group on the curve its
key names: each group after the valuation day discounted on its own curve's factor for its day,
with the DV01 the trades' convention gives it, and each on or before it cash, the amount itself;
the mark their discounted sum, the cash the paid sum, the DV01 the sum, and each curve's share
of the DV01 by payment day, month and year. The arithmetic is the payments' the bilateral trades
share, globals/payments.py, and a key is bound to its curve by the step every caller shares,
globals/discount_curve_set.py; what is a payment, which has paid and which days each curve must
cover are decided here, over the batch's groups.
docs/library/cashflows/evaluate-cashflows.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from catalyst.cashflows.booking import Cashflows
from catalyst.globals.discount_curve import DiscountCurve
from catalyst.globals.discount_curve_set import DiscountCurveSet, curve_named, no_curve_named
from catalyst.globals.payments import curve_starts_on, discounted, factors_on, time_fractions
from catalyst.globals.valuation_date import ValuationDate
from catalyst.instrumentation.work_counts import WorkCounter
from catalyst.trades.contributions import RateContribution, curve_words
from catalyst.trades.display_axes import PeriodAxis, early_risk, period_axis
from catalyst.trades.evaluation import CURVES_SELECTED  # one per distinct key bound to its curve
from catalyst.trades.risk_report import NO_DAYS, Bucket, Risk, RiskView, dv01_label, placed
from catalyst.trades.terms import named_trade

PAYMENT_FACTORS_READ = "payment_factors_read"  # one per unpaid payment group
PAYMENTS_VALUED = "payments_valued"  # unpaid payment groups discounted, each with its DV01
# The three totals, the DV01 by curve onto the days, the months and the years, and each curve's
# total: seven whatever the curves.
RISK_REDUCTIONS = "risk_reductions"


@dataclass(frozen=True, slots=True)
class CashflowResults:
    """The snapshot of a batch of cashflows on one valuation day over the curves its keys name,
    every array read-only: the batch by reference and, since cashflow-curve-keys.md, curves, the
    curve each of the batch's keys was bound to, in key order; as_of and the currency; mark, the
    discounted value of the unpaid payments in all; cash, the paid amounts in all; dv01, the
    unpaid payments' in all, in the currency per basis point. Then per payment group of the
    batch, a payment day and a key, paid or not: is_paid; payment_factor, the group's own
    curve's on an unpaid day and 1 on a paid one, read for nothing; npv, the group's amount
    times its factor, zero on a paid group; payment_cash, the amount on a paid group and zero
    on an unpaid one; group_dv01, the unpaid group's DV01 and zero on a paid one. Then the two
    display axes from the valuation day's period and the batch's rate contributions, one per
    curve in key order, each the curve's share of the DV01: by payment day, month and year on
    the batch's saved axes, which every curve shares, zero where the curve pays nothing, its
    total, and the facts refusing a month or a year report of it standing before the start,
    found once here; the collection sums each into its curve's group beside the trades'."""

    cashflows: Cashflows
    curves: tuple[DiscountCurve, ...]
    as_of: np.datetime64
    currency: str
    mark: float
    cash: float
    dv01: float
    is_paid: NDArray[np.bool_]
    payment_factor: NDArray[np.float64]
    npv: NDArray[np.float64]
    payment_cash: NDArray[np.float64]
    group_dv01: NDArray[np.float64]
    by_month: PeriodAxis
    by_year: PeriodAxis
    rate_contributions: tuple[RateContribution, ...]

    def report(self, risk: Risk, bucket: Bucket) -> RiskView:
        """The content of the risk report asked for, _ReportRisk's selection: one DV01 column
        per curve the batch is valued on, since cashflow-curve-keys.md, in key order, on one
        date axis; by payment day, the batch's distinct days with zero where a curve pays
        nothing or the day has paid, or by payment month or year through the display axis from
        the valuation day's period, a saved DV01 before the start refused in the words prepared
        where the vector was made; `all` the DV01 alone, a batch of cashflows having no
        commodity risk, and the three commodity selectors refused by name rather than shown
        over an index the batch has not. Selects, and nothing else."""
        match risk:
            case Risk.DV01 | Risk.ALL:
                pass
            case Risk.NOMINAL_DELTA | Risk.DELTA | Risk.CROSS_GAMMA:
                raise ValueError(
                    f"risk is {risk.value!r}, expected dv01 or all for a batch of cashflows, which "
                    "has no commodity risk"
                )
            case _:
                assert_never(risk)
        contributions = self.rate_contributions
        # Each curve's word as every report gives it, contributions.py: its name, or qualified
        # where the name is the cleared batch's word, the headings a collection of the batch
        # alone shows.
        words = curve_words([c.curve for c in contributions])
        labels = tuple([dv01_label(words[id(c.curve)], self.currency) for c in contributions])
        totals = tuple([c.dv01 for c in contributions])
        match bucket:
            case Bucket.DAY:
                return RiskView(
                    self.cashflows.payment_days,
                    labels,
                    totals,
                    tuple([c.dv01_by_day for c in contributions]),
                )
            case Bucket.MONTH | Bucket.YEAR:
                if bucket is Bucket.MONTH:
                    unit, axis = "M", self.by_month
                    saved = [c.dv01_by_month for c in contributions]
                else:
                    unit, axis = "Y", self.by_year
                    saved = [c.dv01_by_year for c in contributions]
                for c in contributions:
                    c.early_dv01.refuse("DV01", unit)
                columns = tuple(
                    [placed(axis.dv01_rows, axis.paid_in, each[axis.paid_from :]) for each in saved]
                )
                return RiskView(axis.periods[: axis.dv01_rows], labels, totals, columns)
            case _:
                assert_never(bucket)


def cashflow_results(
    batch: Cashflows,
    valuation_date: ValuationDate,
    curve_set: DiscountCurveSet,
    counter: WorkCounter,
) -> CashflowResults:
    """The one way to make CashflowResults: the rules, in this order, the first failure being
    the message; then the arithmetic, numpy's flags down and the rules the judge.

    Each distinct key of the batch, in key order, is bound to the collection's curve of that
    exact name by the step every caller shares since shared-curve-binding.md, curve_named, case
    and all and with no fallback to the first curve, a collection of one included; a key naming
    none is refused in that step's one sentence with the first row booking it. Then each
    selected curve, in key order, starts on the valuation day, never rebased, the rule the
    trades' evaluation shares, and covers its own unpaid payment days, the first it does not
    named with its key and the curve's range; a curve nobody selects is read for nothing, and a
    batch paid in full still binds its keys and checks each selected curve's start. A payment
    day after the valuation day is unpaid, one on or before it has paid, the date-based cutoff
    the trades use, the day's fraction elapsed moving nothing; a paid group needs no factor.

    An unpaid group's factor is its own curve's for its day, read by position, and its time
    fraction the calendar days from the valuation day over 365; the group's value is its amount
    times its factor and its DV01 -0.0001 times its time fraction times that value, negative
    for an amount receivable; a paid group's amount is cash, at factor 1, with no value and no
    DV01. The mark, the cash and the DV01 are the sums. Each curve's DV01 is summed onto the
    batch's days, months and years, one reduction a view for every curve at once, a row a
    curve, and each curve's total is its days' sum; each of the three totals and each curve's
    two period views is finite or the first that is not is refused, by the batch or by its
    period and its curve. The display axes run from the valuation day's month or year through
    the last payment period; a paid group holds no DV01, so nothing stands before the start.

    Work: one curve selected per distinct key, one factor read and one payment valued per
    unpaid group and seven reductions, reported to the counter; nothing per row of the batch,
    no market, history or index read.
    """
    as_of = valuation_date.as_of
    currency = batch.currency
    keys = batch.keys
    curves: list[DiscountCurve] = []
    for key in keys:
        curve = curve_named(curve_set, key)  # the rule every caller binds a key by
        if curve is None:
            row = batch.discount_curve_key.index(key)  # the first row booking the key
            raise no_curve_named(curve_set, key, named_trade(batch.trade_id, row))
        curves.append(curve)
    group_days = batch.payment_days[batch.group_day]
    group_key = batch.group_key
    unpaid = group_days > as_of
    factor = np.ones(group_days.size)  # a paid group's policy factor, read for nothing
    for k, (key, curve) in enumerate(zip(keys, curves, strict=True)):
        curve_starts_on(curve, as_of)
        mine = unpaid & (group_key == k)
        its_days = group_days[mine]
        uncovered = its_days > curve.max_date
        if uncovered.any():
            raise ValueError(
                f"the payment on {its_days[int(uncovered.argmax())]} on {key} is past the "
                f"discount curve {curve.name!r}, which runs from {curve.start_date} to "
                f"{curve.max_date}; expected every unpaid payment day covered"
            )
        factor[mine] = factors_on(curve, its_days)
    amounts = batch.group_amounts
    tau = np.zeros(group_days.size)
    tau[unpaid] = time_fractions(as_of, group_days[unpaid])
    days, months, years = batch.payment_days, batch.months, batch.years
    count = len(keys)
    rows = np.arange(count, dtype=np.intp)[:, None]
    with np.errstate(over="ignore", invalid="ignore"):  # the rules below are the judge
        npv, group_dv01 = discounted(np.where(unpaid, amounts, 0.0), factor, tau)
        payment_cash = np.where(unpaid, 0.0, amounts)
        mark = float(npv.sum())
        cash = float(payment_cash.sum())
        dv01 = float(group_dv01.sum())
        # Every curve's DV01 at once, a row a curve: the groups onto their curve's days, the
        # days onto its months and the months onto its years.
        dv01_by_day = np.bincount(
            group_key * days.size + batch.group_day, weights=group_dv01, minlength=count * days.size
        ).reshape(count, days.size)
        dv01_by_month = np.bincount(
            (rows * months.size + batch.month_of_day).ravel(),
            weights=dv01_by_day.ravel(),
            minlength=count * months.size,
        ).reshape(count, months.size)
        dv01_by_year = np.bincount(
            (rows * years.size + batch.year_of_month).ravel(),
            weights=dv01_by_month.ravel(),
            minlength=count * years.size,
        ).reshape(count, years.size)
        dv01_of_curve = dv01_by_day.sum(axis=1)
    for label, total, unit in (
        ("mark", mark, currency),
        ("cash", cash, currency),
        ("DV01", dv01, f"{currency} per basis point"),
    ):
        if not np.isfinite(total):
            raise ValueError(
                f"the batch has {total!r} of {label} in all, expected a finite amount of {unit}; "
                "the payments, each finite, sum past the largest number"
            )
    for label, starts, views in (
        ("the payment month from", months, dv01_by_month),
        ("the payment year from", years, dv01_by_year),
    ):  # the two views, not the days: a bucket's sum can outrun what its parts did not
        outrun = ~np.isfinite(views)
        if outrun.any():
            k, b = np.unravel_index(int(outrun.argmax()), outrun.shape)
            raise ValueError(
                f"{label} {starts[b]} has {float(views[k, b])!r} of DV01 on {curves[int(k)].name} "
                f"in all, expected a finite amount of {currency} per basis point; its payments' "
                "DV01s sum past the largest number"
            )
    by_month = period_axis(as_of, NO_DAYS, months, "M")
    by_year = period_axis(as_of, NO_DAYS, years, "Y")
    is_paid = ~unpaid
    for array in (
        is_paid, factor, npv, payment_cash, group_dv01, dv01_by_day, dv01_by_month, dv01_by_year,
    ):  # fmt: skip
        array.setflags(write=False)
    contributions = tuple(
        [
            RateContribution(
                curve,
                currency,
                float(dv01_of_curve[k]),
                days,
                dv01_by_day[k],
                months,
                dv01_by_month[k],
                years,
                dv01_by_year[k],
                early_risk(
                    f"{curve.name} {currency}",
                    "payment",
                    as_of,
                    f"{currency} per basis point",
                    months,
                    dv01_by_month[k],
                    by_month.paid_from,
                    years,
                    dv01_by_year[k],
                    by_year.paid_from,
                ),
            )
            for k, curve in enumerate(curves)
        ]
    )
    valued = int(np.count_nonzero(unpaid))
    counter.hit(CURVES_SELECTED, count)
    counter.hit(PAYMENT_FACTORS_READ, valued)
    counter.hit(PAYMENTS_VALUED, valued)
    counter.hit(RISK_REDUCTIONS, 7)
    return CashflowResults(
        batch,
        tuple(curves),
        as_of,
        currency,
        mark,
        cash,
        dv01,
        is_paid,
        factor,
        npv,
        payment_cash,
        group_dv01,
        by_month,
        by_year,
        contributions,
    )
