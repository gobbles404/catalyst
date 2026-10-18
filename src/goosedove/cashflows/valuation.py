"""A batch of cashflows valued on a valuation day over a discount curve, cashflow-instrument.md:
each payment day after the valuation day discounted on the curve's factor for it, with the DV01
the trades' convention gives it, and each on or before it cash, the amount itself; the mark their
discounted sum, the cash the paid sum, the DV01 the sum, by payment day, month and year. The
arithmetic is the payments' the bilateral trades share, globals/payments.py; what is a payment,
which has paid and which the curve must cover are decided here, over the batch's distinct days.
docs/library/cashflows/evaluate-cashflows.md is the page."""

from dataclasses import dataclass
from typing import assert_never

import numpy as np
from numpy.typing import NDArray

from goosedove.cashflows.booking import Cashflows
from goosedove.globals.discount_curve import DiscountCurve
from goosedove.globals.payments import curve_starts_on, discounted, factors_on, time_fractions
from goosedove.globals.valuation_date import ValuationDate
from goosedove.instrumentation.work_counts import WorkCounter
from goosedove.trades.contributions import RateContribution
from goosedove.trades.display_axes import PeriodAxis, early_risk, period_axis
from goosedove.trades.risk_report import NO_DAYS, Bucket, Risk, RiskView, dv01_label, placed

PAYMENT_FACTORS_READ = "payment_factors_read"  # one per distinct unpaid payment day
PAYMENTS_VALUED = "payments_valued"  # unpaid payment days discounted, each with its DV01
RISK_REDUCTIONS = "risk_reductions"  # the three totals, and the DV01 onto the months and years


@dataclass(frozen=True, slots=True)
class CashflowResults:
    """The snapshot of a batch of cashflows on one valuation day over one curve, every array
    read-only: the batch and the curve by reference; as_of and the currency; mark, the discounted
    value of the unpaid payments in all; cash, the paid amounts in all; dv01, the unpaid payments'
    in all, in the currency per basis point. Then per distinct payment day of the batch,
    increasing, paid or not: is_paid; payment_factor, the curve's on an unpaid day and 1 on a
    paid one, read for nothing; npv, the day's amount times its factor, zero on a paid day;
    payment_cash, the amount on a paid day and zero on an unpaid one. Then the two display axes
    from the valuation day's period and, since named-curves-slice-2.md, the batch's one rate
    contribution, the curve's share of the DV01, the whole of it: the DV01 by payment day, month
    and year on the batch's saved axes, its total, and the facts refusing a month or a year
    report of it standing before the start, found once here; the collection sums it into its
    curve's group beside the trades'."""

    cashflows: Cashflows
    curve: DiscountCurve
    as_of: np.datetime64
    currency: str
    mark: float
    cash: float
    dv01: float
    is_paid: NDArray[np.bool_]
    payment_factor: NDArray[np.float64]
    npv: NDArray[np.float64]
    payment_cash: NDArray[np.float64]
    by_month: PeriodAxis
    by_year: PeriodAxis
    rate_contributions: tuple[RateContribution, ...]

    def report(self, risk: Risk, bucket: Bucket) -> RiskView:
        """The content of the risk report asked for, _ReportRisk's selection: the DV01 by payment
        day, the batch's distinct days with zero on a paid one, or by payment month or year
        through the display axis from the valuation day's period, a saved DV01 before the start
        refused in the words prepared where the vector was made; `all` the DV01 alone, a batch of
        cashflows having no commodity risk, and the three commodity selectors refused by name
        rather than shown over an index the batch has not. Selects, and nothing else."""
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
        contribution = self.rate_contributions[0]  # one curve values a batch of cashflows
        label = dv01_label(contribution.curve.name, self.currency)
        match bucket:
            case Bucket.DAY:
                return RiskView(
                    contribution.days, (label,), (self.dv01,), (contribution.dv01_by_day,)
                )
            case Bucket.MONTH | Bucket.YEAR:
                if bucket is Bucket.MONTH:
                    unit, axis, saved = "M", self.by_month, contribution.dv01_by_month
                else:
                    unit, axis, saved = "Y", self.by_year, contribution.dv01_by_year
                contribution.early_dv01.refuse("DV01", unit)
                column = placed(axis.dv01_rows, axis.paid_in, saved[axis.paid_from :])
                return RiskView(axis.periods[: axis.dv01_rows], (label,), (self.dv01,), (column,))
            case _:
                assert_never(bucket)


def cashflow_results(
    batch: Cashflows, valuation_date: ValuationDate, curve: DiscountCurve, counter: WorkCounter
) -> CashflowResults:
    """The one way to make CashflowResults: the rules, in this order, the first failure being
    the message; then the arithmetic, numpy's flags down and the rules the judge.

    The curve starts on the valuation day, never rebased, the rule the trades' evaluation
    shares; a payment day after the valuation day is unpaid, one on or before it has paid,
    the date-based cutoff the trades use, the day's fraction elapsed moving nothing; and the curve
    covers every unpaid day, the first it does not named with the curve's range, a paid day
    needing no factor, so a curve of one day serves a batch paid in full. An unpaid day's factor
    is the curve's for that day, read by position, and its time fraction the calendar days from
    the valuation day over 365; the day's value is its amount times its factor and its DV01
    -0.0001 times its time fraction times that value, negative for an amount receivable; a paid
    day's amount is cash, at factor 1, with no value and no DV01. The mark, the cash and the DV01
    are the sums; the DV01 is summed onto the batch's months and years besides, and each of the
    three totals and the two views is finite or the first that is not is refused, by the batch
    or by its period. The display axes run from the valuation day's month or year through the
    last payment period; a paid day holds no DV01, so nothing stands before the start.

    Work: one factor read and one payment valued per distinct unpaid day and five reductions,
    reported to the counter; nothing per row of the batch, no market, history or index read.
    """
    as_of = valuation_date.as_of
    currency = batch.currency
    curve_starts_on(curve, as_of)
    days = batch.payment_days
    unpaid = days > as_of
    uncovered = unpaid & (days > curve.max_date)
    if uncovered.any():
        k = int(uncovered.argmax())
        raise ValueError(
            f"the payment on {days[k]} is past the discount curve, which runs from "
            f"{curve.start_date} to {curve.max_date}; expected every unpaid payment day covered"
        )
    amounts = batch.payment_amounts
    unpaid_days = days[unpaid]
    factor = np.ones(days.size)  # a paid day's policy factor, read for nothing
    factor[unpaid] = factors_on(curve, unpaid_days)
    tau = np.zeros(days.size)
    tau[unpaid] = time_fractions(as_of, unpaid_days)
    with np.errstate(over="ignore", invalid="ignore"):  # the rules below are the judge
        npv, dv01_by_day = discounted(np.where(unpaid, amounts, 0.0), factor, tau)
        payment_cash = np.where(unpaid, 0.0, amounts)
        mark = float(npv.sum())
        cash = float(payment_cash.sum())
        dv01 = float(dv01_by_day.sum())
        dv01_by_month = np.bincount(
            batch.month_of_day, weights=dv01_by_day, minlength=batch.months.size
        )
        dv01_by_year = np.bincount(
            batch.year_of_month, weights=dv01_by_month, minlength=batch.years.size
        )
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
    for label, starts, amounts_in in (
        ("the payment month from", batch.months, dv01_by_month),
        ("the payment year from", batch.years, dv01_by_year),
    ):  # the two views, not the days: a bucket's sum can outrun what its parts did not
        outrun = ~np.isfinite(amounts_in)
        if outrun.any():
            b = int(outrun.argmax())
            raise ValueError(
                f"{label} {starts[b]} has {float(amounts_in[b])!r} of DV01 in all, expected a "
                f"finite amount of {currency} per basis point; its payments' DV01s sum past the "
                "largest number"
            )
    by_month = period_axis(as_of, NO_DAYS, batch.months, "M")
    by_year = period_axis(as_of, NO_DAYS, batch.years, "Y")
    early_dv01 = early_risk(
        f"{curve.name} {currency}",
        "payment",
        as_of,
        f"{currency} per basis point",
        batch.months,
        dv01_by_month,
        by_month.paid_from,
        batch.years,
        dv01_by_year,
        by_year.paid_from,
    )
    is_paid = ~unpaid
    for array in (is_paid, factor, npv, payment_cash, dv01_by_day, dv01_by_month, dv01_by_year):
        array.setflags(write=False)
    valued = int(np.count_nonzero(unpaid))
    counter.hit(PAYMENT_FACTORS_READ, valued)
    counter.hit(PAYMENTS_VALUED, valued)
    counter.hit(RISK_REDUCTIONS, 5)
    return CashflowResults(
        batch,
        curve,
        as_of,
        currency,
        mark,
        cash,
        dv01,
        is_paid,
        factor,
        npv,
        payment_cash,
        by_month,
        by_year,
        (
            RateContribution(
                curve,
                currency,
                dv01,
                days,
                dv01_by_day,
                batch.months,
                dv01_by_month,
                batch.years,
                dv01_by_year,
                early_dv01,
            ),
        ),
    )
