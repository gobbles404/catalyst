# _ReportValues

Built in #141 as ticket I5 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_ReportRisk](report-risk.md); the design is [readers](../../engineering-tickets/trade-valuation-pipeline/06-readers.md) and [result fields by route](../../engineering-tickets/trade-valuation-pipeline/result-fields-by-route.md).

The batch's values from its results, as evaluation stored them: the mark and the cash under the route's labels, the currency and the valuation day. A report selects and labels; it values nothing, reads no market and infers no settlement, so a report of an older result stands after a later tick, and two reports of one result agree. The code is `src/goosedove/excel/trades.py`.

## Worksheet contract

```python
def _ReportValues(results: Handle[TradeResults] | Handle[CashflowResults]) -> MixedArray: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 13 | `=_ReportValues(A12)` | | | |
| | cleared_mark | cleared_cash | currency | as_of |
| | float64 | float64 | str | datetime64[D] |
| | 7000 | 0 | USD | 24-Nov-2026 |

One handle, required: the results, the cell showing `_EvaluateTrades`'s result or a name for it, A12 in the example, whose history and market handles sit in I11 and I12 beside the index in I3, outside this three-by-four spill at A13:D15 and the risk report's at A17:E19; a cell of another kind fails in the seam's words, `results is prepared trades handle '30512:prepared_trades:Henry Hub NYMEX:43', expected trade results or cashflow results handle`. The spill is three rows by four columns, a table as every reader spills one: the headers, the types and one row. The labels are the route's, `cleared_mark` and `cleared_cash`, or `bilateral_mark` and `bilateral_cash` since #177, the bilateral mark the unpaid payment groups' NPV on the curve `_EvaluateTrades` took and the bilateral cash the nominal paid amounts, undiscounted as the cleared cash is, [kernel.md](kernel.md#the-bilateral-path); the other route's fields are not shown as zeros. Since #200 a batch of cashflows' results, [evaluate-cashflows.md](../cashflows/evaluate-cashflows.md), show under `cashflow_mark` and `cashflow_cash`, the mark the discounted value of the unpaid payments and the cash the paid amounts, one declaration of two kinds, [inputs.md](../../seam/inputs.md) decision 45, the word before the labels the result's own. The mark is a currency amount, the undiscounted entry-to-current-price P&L of the payment groups not yet settled, live slots at their quotes and fixed slots at their settles; the cash the cumulative entry-to-final-price P&L of the groups settled by the valuation day, the payment day on or before it, undiscounted, every settled group of the batch through that day; neither is a bank reconciliation, and margining is outside the model. The day is the history's valuation day, a date as the sheet formats one.

## Excel help

| Item | Text |
|---|---|
| Function | Reports the batch's values from its results: the mark and the cash under the route's labels, or under cashflow for a batch of cashflows, the currency and the valuation day, as evaluation stored them. |
| results | The results handle: the cell showing _EvaluateTrades's or _EvaluateCashflows's result, such as A12, or a name for it. |

## The library checks

Nothing: the result is complete when it is published or it is not published, so a report finds every field it shows.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trade_valuation.py` | the NG example's spill cell for cell, 7,000 and 0 in USD on 24 November; since #177 the bilateral labels over the kernel's example, 5 of mark and no cash, 5.5 on a tick, 4 on a replacement curve, the one receivable's 100, then 120 fixed and unpaid, then 0 beside 120 of cash; the toy's seven states, 7,000 of mark and no cash to no mark and 14,300 of cash, each pair summing to the page's total; a report of the old results unmoved by a tick; one trade's -18,000; a blank and a prepared-trades handle refused |
| `tests/performance/test_trade_valuation_budgets.py` | one handle resolved, one row laid out, no kernel call, nothing published; 1,967 bytes |
| `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `tools/excel_lifetime.ps1 -Groups trades,valuation`, `workbooks/handles.xlsx` | the chain's mark read through the report on a sheet, from the host, through a tick, through the valuation day's roll past n26's expiry, 5,000 of cash and a mark of 0, and through the market's failure, the report spilled showing the failure in the creator's words and a read through INDEX showing #REF!, since #155, and at the foot of the handles sheet, B1304 and the toy's seven states in K1342 to L1348 |

## Not here

No delta or DV01, [_ReportRisk](report-risk.md), by time since #178. No value per trade, no decomposition into offsets, set and live amounts, no cash over a chosen interval, no NPV by payment group, which the readback shows as `group_npv`: a new view is a new function over a result that holds what it needs, and `util_ReadHandle` on the results handle is the debugging spill of the dated contents meanwhile.
