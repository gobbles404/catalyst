# _EvaluateCashflows

A batch of cashflows valued on a valuation day over a discount curve: each payment day after the valuation day discounted on the curve's factor for it, with the DV01 the trades' convention gives it, and each on or before it cash, the amount itself; the mark their discounted value in all, the cash the paid amounts in all, the DV01 their sum by payment day, month and year. No commodity index, history, market or preparation is read, since every amount is known when the batch is booked; the curve and the valuation day are the changing inputs, and a new evaluation over the same batch is a new snapshot while an older held result stands. The arithmetic is the one the bilateral trades value a known payment by, `src/goosedove/globals/payments.py`, under the convention [evaluate-trades.md](../trades/evaluate-trades.md) owns; what is a payment, which has paid and which the curve must cover are decided here. The code is `src/goosedove/cashflows/valuation.py`, the record, its builder and its risk view, and `src/goosedove/excel/cashflows.py`, the worksheet function. [The ticket](../../engineering-tickets/trade-valuation-pipeline/cashflow-instrument.md) has the decisions.

## Worksheet contract

```python
def _EvaluateCashflows(
    cashflows: Handle[Cashflows],
    valuation_date: Handle[ValuationDate],
    discount_curve: Handle[DiscountCurve],
) -> Handle[CashflowResults]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 10 | `=_CreateValuationDate(DATE(2027,1,4),0.5)` | shows `30512:valuation_date:4` | | |
| 11 | `=_CreateDiscountCurve("SOFR",G1:H1,G2:H4)` | shows `30512:discount_curve:SOFR:5`, 1 on 4 January 2027, 0.95 a year out, 0.90 two years out | | |
| 12 | `=_EvaluateCashflows(A8,A10,A11)` | shows `30512:cashflow_results:USD:6` | | |
| 13 | `=_ReportValues(A12)` | | | |
| | cashflow_mark | cashflow_cash | currency | as_of |
| | float64 | float64 | str | datetime64[D] |
| | 500 | 250 | USD | 4-Jan-2027 |
| 17 | `=_ReportRisk(A12,"dv01","year")` | 4-Jan-2027 | | |
| | period | SOFR USD dv01 [USD per basis point] | | |
| | str \| datetime64[D] | float64 | | |
| | Total | 0.85 | | |
| | 1-Jan-2027 | 0 | | |
| | 1-Jan-2028 | -0.95 | | |
| | 1-Jan-2029 | 1.8 | | |

The DV01 column's heading is the curve's word as [report-risk.md](../trades/report-risk.md) gives every heading, the name as created, or `cleared (curve_1)` for a curve named `cleared`, the same word a collection of the batch alone shows. Three handles, every one required: the batch, the cell showing [_CreateCashflows](create-cashflows.md)'s result; the valuation date, the cell showing `_CreateValuationDate`'s, which supplies `as_of` explicitly, the day's fraction elapsed read for nothing; and the curve, the cell showing `_CreateDiscountCurve`'s or [util_BumpDiscountCurve](../utilities/bump-discount-curve.md)'s, each resolved as any handle is and refused by its kind in the seam's words. The result is a handle, declared `Handle[CashflowResults]`, carrying the batch's currency, `30512:cashflow_results:USD:6`, and no new kind of reader or report: [_ReportValues](../trades/report-values.md) shows the mark and the cash under `cashflow_mark` and `cashflow_cash`, the cashflow mark being the discounted value of the unpaid payments, [_ReportRisk](../trades/report-risk.md) the DV01 by day, month or year, and `util_ReadHandle` the days. The worked example is the ticket's: 10,000 receivable a year out at 0.95 is 9,500 and -0.95 of DV01, 10,000 payable two years out at 0.90 is -9,000 and +1.80, and a rebate of 250 paid the day before is cash; the two nominal amounts net to nothing while their values and DV01s do not, since their days differ.

## The valuation

For each distinct payment day `t` of the batch, with `as_of` the valuation day and `DF` the curve:

```text
if t > as_of:
    tau  = calendar_days(t - as_of) / 365
    npv  = amount * DF(t)
    cash = 0
    dv01 = -0.0001 * tau * npv
else:
    npv  = 0
    cash = amount
    dv01 = 0
```

The cutoff is the date's, the trades' rule: a payment on the valuation day has paid, whatever the day's fraction elapsed, and stays cash on every later day; it assumes payment on the scheduled day and confirms no transfer. The factor is the curve's for the day, by position, the curve being daily from its start; `tau` is ACT/365F, weekends and leap days counted; the DV01 is the analytic sensitivity of the day's value to a rise of one basis point in the continuously compounded zero rates, negative for an amount receivable, the convention the trades' DV01 and cross-gamma move by. The mark, the cash and the DV01 are the sums; the DV01 is summed onto the batch's payment months and years besides, and the month and year reports run from the valuation day's period through the last payment period, zero between, as the trades' do. A paid day holds no DV01, so nothing stands before the start. There is no commodity delta and no cross-gamma: nothing of the batch moves with a commodity price.

## The library checks

In this order, the first failure being the message; a failure publishes no handle.

| Rule | Refused as |
|---|---|
| the curve starts on the valuation day, never rebased, the rule the trades share, the words naming the curve since the named-curve arc's slice 3 | `discount curve 'SOFR' starts on 2027-01-05, expected 2027-01-04, the valuation date; a curve is never rebased` |
| the curve covers every unpaid payment day; a paid day needs no factor, so a curve of one day serves a batch paid in full | `the payment on 2029-01-03 is past the discount curve, which runs from 2027-01-04 to 2028-01-04; expected every unpaid payment day covered` |
| the mark, the cash and the DV01 are finite in all, under numpy's flags down | `the batch has inf of mark in all, expected a finite amount of USD; the payments, each finite, sum past the largest number` |
| the DV01 by month and by year is finite in every period | `the payment month from 2028-01-01 has inf of DV01 in all, expected a finite amount of USD per basis point; its payments' DV01s sum past the largest number` |

`_ReportRisk` takes `dv01` by `day`, `month` or `year`, and `all`, which shows the DV01 alone; `nominal_delta`, `delta` and `cross_gamma` are refused by name, `risk is 'delta', expected dv01 or all for a batch of cashflows, which has no commodity risk`, rather than shown over an index the batch has not. `_ReportReserves` and `_AggregateResults` take a batch of trades' results and refuse these by kind; the collection is the next ticket's.

## What it retains

The batch and the curve by reference, `as_of` and the currency; the mark, the cash and the DV01; per distinct payment day, increasing, paid or not, whether it has paid, its factor, 1 on a paid day, its value, its cash and its DV01; the DV01 by payment month and by year on the batch's axes; the two display axes from the valuation day's period; and the facts refusing a month or a year report of a DV01 before the start, found once here and never found; since [named-curves-slice-2.md](../../engineering-tickets/trade-valuation-pipeline/named-curves-slice-2.md) the DV01 by day, by month and by year with their axes, the total and those facts are held as the curve's one rate contribution, `RateContribution` in `trades/contributions.py`, the same arrays by reference, which the reports read and [_AggregateResults](../trades/aggregate-results.md) collects. Nothing is valued again by a report.

## Reading it back

`util_ReadHandle` on the handle spills one row per distinct payment day, increasing: `payment_date`, `amount`, the rows' amounts summed on the day, `is_paid`, `payment_factor`, `npv`, `cash` and `dv01`, with `currency` and `as_of` on every row so that a row reads whole; then the batch's totals once, on the first row and a dash below, `cashflow_mark`, `cashflow_cash` and `cashflow_dv01`, the numbers the reports show; [read-handle.md](../utilities/read-handle.md).

## Tests

The worked example and the receipt of a hundred through a curve move, the payment day and the day after, the summing by day, the rules in order, the risk views and the centered check of the DV01 against two bumped evaluations are `tests/unit/test_cashflows.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`; the results' life through a curve change and a roll is the `cashflows` group of `tools/excel_lifetime.ps1`, and the kept workbook's block from row 2864 holds the ticket's example with its curve move and its roll. What a call costs is `tests/performance/test_cashflow_budgets.py`, one factor and one payment per unpaid day, the same functions at three days and at two thousand, nothing per row of the batch.

## Not here

A collection of cashflow results with a batch of trades' through `_AggregateResults`: built as [named-curves-slice-2.md](../../engineering-tickets/trade-valuation-pipeline/named-curves-slice-2.md), the batch's one rate contribution joining the group of its curve and currency and no commodity group, [aggregate-results.md](../trades/aggregate-results.md). Another currency, FX, credit adjustments, several curves within one batch, an overdue balance, a partial payment, an intraday cutoff and actual payment reconciliation: outside this instrument. The curve's own rules are [discount-curve.md](../globals/discount-curve.md)'s and the convention [evaluate-trades.md](../trades/evaluate-trades.md)'s, said once there.
