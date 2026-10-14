# _ReportRisk

Built in #141 as ticket I5 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_ReportValues](report-values.md); the design is [readers](../../engineering-tickets/trade-valuation-pipeline/06-readers.md) and [result fields by route](../../engineering-tickets/trade-valuation-pipeline/result-fields-by-route.md).

The batch's risk from its results, as evaluation stored them: the total delta, the change in mark for a move of one quote unit in every contract at once, with its unit; the DV01 with its unit; and the valuation day. The delta by contract on the batch's axis is retained in the result and not spilled here, `util_ReadHandle` on the results showing it on each slot of the contract as `contract_delta`. A report values nothing and bumps nothing. The code is `src/goosedove/excel/trades.py`.

## Worksheet contract

```python
def _ReportRisk(results: Handle[TradeResults]) -> MixedArray: ...
```

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 14 | `=_ReportRisk(A12)` | | | | |
| | delta_total | delta_unit | dv01 | dv01_unit | as_of |
| | float64 | str | float64 | str | datetime64[D] |
| | 110000 | USD per USD/MMBTU | 0 | USD per basis point | 24-Nov-2026 |

One handle, required: the results, the cell showing `_EvaluateTrades`'s result or a name for it. The spill is three rows by five columns. `delta_total` is the sum of the deltas by contract, each the live exposure referencing that contract, zero where every slot of it has fixed: for the NG example 160,000 less 50,000; its unit is the settlement currency per quote unit, `USD per USD/MMBTU`, so a one-cent move in every contract changes the mark by 1,100 dollars. `dv01` is the change for a one basis point move in rates: zero for the cleared route, the undiscounted model's own answer and not a placeholder, and the bilateral route, whose DV01 needs a curve, a bump and a sign convention, is refused at evaluation rather than reported as zero. The delta's value basis is the route's mark; a settled group contributes to neither.

## Excel help

| Item | Text |
|---|---|
| Function | Reports the batch's risk from its results: the total delta, the change in mark for a move of one quote unit in every contract, with its unit, the DV01 with its unit, and the valuation day, as evaluation stored them. |
| results | The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name for it. |

## The library checks

Nothing: the result is complete when it is published.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trade_valuation.py` | the NG example's spill cell for cell, 110,000 USD per USD/MMBTU and a DV01 of zero; -50,000 once Z26 has fixed; the total unchanged by a tick; one trade's -120,000; a blank refused |
| `tests/performance/test_trade_valuation_budgets.py` | one handle resolved, one row laid out, no kernel call, nothing published; 1,948 bytes |
| `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `workbooks/handles.xlsx` | the chain's delta read through the report on a sheet, from the host, and at the foot of the handles sheet, B1307 and the toy's seven states in M1342 to M1348, 110,000 while both contracts are live, -50,000 once Z26 has fixed, 0 once both have |

## Not here

No delta by contract spilled, which the result retains and `util_ReadHandle` shows by slot; no bilateral DV01, no bump convention, no scenario; no roll-off view of the dates on which delta leaves, which the dated slots support when it is wanted.
