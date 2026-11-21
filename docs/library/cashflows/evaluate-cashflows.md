# _EvaluateCashflows

A batch of cashflows valued on a valuation day over a collection of named discount curves: each payment names its curve by `discount_curve_key`, since [cashflow-curve-keys.md](../../engineering-tickets/trade-valuation-pipeline/cashflow-curve-keys.md), and is valued on the collection's curve of that exact name, each payment group after the valuation day discounted on its own curve's factor for its day, with the DV01 the trades' convention gives it, and each on or before it cash, the amount itself; the mark their discounted value in all, the cash the paid amounts in all, the DV01 each curve's share by payment day, month and year. No commodity index, history, market or preparation is read, since every amount is known when the batch is booked; the curves and the valuation day are the changing inputs, and a new evaluation over the same batch is a new snapshot while an older held result stands. The arithmetic is the one the bilateral trades value a known payment by, `src/catalyst/globals/payments.py`, under the convention [evaluate-trades.md](../trades/evaluate-trades.md) owns, and a key is bound to its curve by the step every caller shares, [collect-discount-curves.md](../globals/collect-discount-curves.md#binding-a-key); what is a payment, which has paid and which days each curve must cover are decided here. The code is `src/catalyst/cashflows/valuation.py`, the record, its builder and its risk view, and `src/catalyst/excel/cashflows.py`, the worksheet function. [The ticket](../../engineering-tickets/trade-valuation-pipeline/cashflow-instrument.md) has the instrument's decisions and [cashflow-curve-keys.md](../../engineering-tickets/trade-valuation-pipeline/cashflow-curve-keys.md) the keys'.

## Worksheet contract

```python
def _EvaluateCashflows(
    cashflows: Handle[Cashflows],
    valuation_date: Handle[ValuationDate],
    discount_curve_set: Handle[DiscountCurveSet],
) -> Handle[CashflowResults]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 10 | `=_CreateValuationDate(DATE(2027,1,4),0.5)` | shows `30512:valuation_date:4` | | |
| 11 | `=_CreateDiscountCurve("SOFR",G1:H1,G2:H4)` | shows `30512:discount_curve:SOFR:5`, 1 on 4 January 2027, 0.95 a year out, 0.90 two years out | | |
| 12 | `=_CollectDiscountCurves(A11)` | shows `30512:discount_curve_set:6`, the one curve the batch's key names | | |
| 13 | `=_EvaluateCashflows(A8,A10,A12)` | shows `30512:cashflow_results:USD:7` | | |
| 14 | `=_ReportValues(A13)` | | | |
| | cashflow_mark | cashflow_cash | currency | as_of |
| | float64 | float64 | str | datetime64[D] |
| | 500 | 250 | USD | 4-Jan-2027 |
| 18 | `=_ReportRisk(A13,"dv01","year")` | 4-Jan-2027 | | |
| | period | SOFR USD dv01 [USD per basis point] | | |
| | str \| datetime64[D] | float64 | | |
| | Total | 0.85 | | |
| | 1-Jan-2027 | 0 | | |
| | 1-Jan-2028 | -0.95 | | |
| | 1-Jan-2029 | 1.8 | | |

The DV01 column's heading is the curve's word as [report-risk.md](../trades/report-risk.md) gives every heading, the name as created, or `cleared (curve_1)` for a curve named `cleared`, the same word a collection of the batch alone shows, and there is one column per curve the batch is valued on, in the order its rows first name the keys. Three handles, every one required: the batch, the cell showing [_CreateCashflows](create-cashflows.md)'s result; the valuation date, the cell showing `_CreateValuationDate`'s, which supplies `as_of` explicitly, the day's fraction elapsed read for nothing; and the collection, the cell showing [_CollectDiscountCurves](../globals/collect-discount-curves.md)'s, of one curve or several, a curve bumped by [util_BumpDiscountCurve](../utilities/bump-discount-curve.md) collected as any other; each resolved as any handle is and refused by its kind in the seam's words, a curve's own handle where the collection belongs among them, `discount_curve_set is discount curve handle '30512:discount_curve:SOFR:5', expected discount curve set handle`. A batch on one curve takes a collection of that one; no form takes a curve directly. The result is a handle, declared `Handle[CashflowResults]`, carrying the batch's currency, `30512:cashflow_results:USD:7`, and no new kind of reader or report: [_ReportValues](../trades/report-values.md) shows the mark and the cash under `cashflow_mark` and `cashflow_cash`, the cashflow mark being the discounted value of the unpaid payments, [_ReportRisk](../trades/report-risk.md) the DV01 by day, month or year, and `util_ReadHandle` the days. The worked example is the ticket's: 10,000 receivable a year out at 0.95 is 9,500 and -0.95 of DV01, 10,000 payable two years out at 0.90 is -9,000 and +1.80, and a rebate of 250 paid the day before is cash; the two nominal amounts net to nothing while their values and DV01s do not, since their days differ. Two curves in one batch, the keys' ticket's example: 10,000 received on `SOFR` and 10,000 paid on `FFOIS`, both on 4 January 2028, with SOFR at 0.95 and FFOIS at 0.90 for the day, are 9,500 less 9,000, a mark of 500 where one amount on one curve would be nothing; the DV01 is -0.95 under SOFR's heading and +0.90 under FFOIS's, -0.05 in all; and SOFR moved to 0.96 with FFOIS as it was is 600 and -0.96 in new results over the same batch, FFOIS's column as it was.

## The valuation

For each payment group of the batch, a distinct payment day `t` and key, with `as_of` the valuation day and `DF` the curve the group's key names:

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

The cutoff is the date's, the trades' rule: a payment on the valuation day has paid, whatever the day's fraction elapsed, and stays cash on every later day; it assumes payment on the scheduled day and confirms no transfer. Rows net before discounting within a group alone: two payments on one day under one key are one amount, and under two keys two, each on its own factor. The factor is the group's own curve's for the day, by position, the curve being daily from its start; `tau` is ACT/365F, weekends and leap days counted; the DV01 is the analytic sensitivity of the day's value to a rise of one basis point in the continuously compounded zero rates, negative for an amount receivable, the convention the trades' DV01 and cross-gamma move by. The mark, the cash and the DV01 are the sums over every group, whatever its curve; each curve's DV01 is summed onto the batch's payment days, months and years besides, axes every curve shares, zero where a curve pays nothing, and the month and year reports run from the valuation day's period through the last payment period, zero between, as the trades' do. A paid day holds no DV01, so nothing stands before the start. There is no commodity delta and no cross-gamma: nothing of the batch moves with a commodity price.

## The library checks

In this order, the first failure being the message; a failure publishes no handle.

| Rule | Refused as |
|---|---|
| each distinct key of the batch, in the order its rows first name them, names a curve of the collection by its exact name, the step [collect-discount-curves.md](../globals/collect-discount-curves.md#binding-a-key) owns, with no fallback to the first curve, a collection of one included; the first row booking the key is named, and the collection's order changes nothing | `discount_curve_key 'FFOIS' of trade at row 2 names no curve of the collection, which holds 'SOFR'; expected a curve of that name` |
| each selected curve, in key order, starts on the valuation day, never rebased, the rule the trades share; a curve nobody selects is read for nothing, and a batch paid in full still binds its keys and holds each selected curve to its start | `discount curve 'SOFR' starts on 2027-01-05, expected 2027-01-04, the valuation date; a curve is never rebased` |
| and covers its own unpaid payment days, another curve's days nothing to it, a curve's start and its cover both judged before the next curve's; a paid day needs no factor, so a curve of one day serves a key paid in full | `the payment on 2029-01-03 on SOFR is past the discount curve 'SOFR', which runs from 2027-01-04 to 2028-01-04; expected every unpaid payment day covered` |
| the mark, the cash and the DV01 are finite in all, under numpy's flags down | `the batch has inf of mark in all, expected a finite amount of USD; the payments, each finite, sum past the largest number` |
| each curve's DV01 by month and by year is finite in every period | `the payment month from 2028-01-01 has inf of DV01 on SOFR in all, expected a finite amount of USD per basis point; its payments' DV01s sum past the largest number` |
| each curve's own DV01 is finite in all, a rule of its own since the review of #260: the batch's DV01 does not answer for a curve's, a receipt on one curve against a payment on another cancelling in the batch's while each curve's sum runs past the largest number, and the reports and the collection read the curve's; the first curve in key order is named | `the batch has -inf of DV01 on SOFR in all, expected a finite amount of USD per basis point; the curve's payments' DV01s, each finite, sum past the largest number` |

`_ReportRisk` takes `dv01` by `day`, `month` or `year`, and `all`, which shows the DV01 alone, a column per curve on one date axis; `nominal_delta`, `delta` and `cross_gamma` are refused by name, `risk is 'delta', expected dv01 or all for a batch of cashflows, which has no commodity risk`, rather than shown over an index the batch has not. `_ReportReserves` and `_AggregateResults` take a batch of trades' results and refuse these by kind; the collection is the next ticket's.

## What it retains

The batch by reference and the curve each of its keys was bound to, in key order, `as_of` and the currency; the mark, the cash and the DV01; per payment group, a payment day and a key, in day order, paid or not, whether it has paid, its factor, its own curve's and 1 on a paid group, its value, its cash and its DV01; the two display axes from the valuation day's period; and one rate contribution per curve, `RateContribution` in `trades/contributions.py`, in key order, where the batch's one curve had one since [named-curves-slice-2.md](../../engineering-tickets/trade-valuation-pipeline/named-curves-slice-2.md): the curve's share of the DV01 by payment day, by month and by year on the batch's axes, which every curve shares, its total, and the facts refusing a month or a year report of a DV01 before the start, found once here and never found. The reports read the contributions and [_AggregateResults](../trades/aggregate-results.md) collects each into its curve's group. Nothing is valued again by a report.

## Reading it back

`util_ReadHandle` on the handle spills one row per payment group, a payment day and a key, in day order and within a day in the order the rows first name the keys, so a payment day on two keys is two rows and a batch on one key reads a row a day as it did: `payment_date`, `amount`, the group's rows' amounts summed, `is_paid`, `payment_factor`, `npv`, `cash` and `dv01`, with `currency` and `as_of` on every row so that a row reads whole; then the batch's totals once, on the first row and a dash below, `cashflow_mark`, `cashflow_cash` and `cashflow_dv01`, the numbers the reports show; and last `discount_curve_key`, the group's key and so its curve's name, after every column a sheet already read by its place; [read-handle.md](../utilities/read-handle.md).

## Tests

The worked example and the receipt of a hundred through a curve move, the payment day and the day after, the summing by day, the rules in order, the risk views and the centered check of the DV01 against two bumped evaluations are `tests/unit/test_cashflows.py`, and with them the two-curve example, the netting within a key and never across keys, the binding by exact name, each selected curve held to its own start and days, a mixed batch against its one-curve batches summed curve by curve, and a curve's own total past the largest number under a batch whose totals and periods are finite, refused before anything is published; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`; the results' life through a curve change and a roll is the `cashflows` group of `tools/excel_lifetime.ps1`, and the kept workbook's block from row 2864 holds the ticket's example with its curve move and its roll, and its block from row 3507 two curves in one batch, the move of one and the refusals. What a call costs is `tests/performance/test_cashflow_budgets.py`, one curve selected per key and one factor and one payment per unpaid group, the same functions at three days and at two thousand, a curve more a fixed few calls more, nothing per row of the batch.

## Not here

A collection of cashflow results with a batch of trades' through `_AggregateResults`: built as [named-curves-slice-2.md](../../engineering-tickets/trade-valuation-pipeline/named-curves-slice-2.md), the batch's one rate contribution joining the group of its curve and currency and no commodity group, [aggregate-results.md](../trades/aggregate-results.md). A default curve for a row with no key, a curve chosen by counterparty or currency, and a curve found by anything but its exact name: none. Another currency, FX, credit adjustments, an overdue balance, a partial payment, an intraday cutoff and actual payment reconciliation: outside this instrument. The curve's own rules are [discount-curve.md](../globals/discount-curve.md)'s and the convention [evaluate-trades.md](../trades/evaluate-trades.md)'s, said once there.
