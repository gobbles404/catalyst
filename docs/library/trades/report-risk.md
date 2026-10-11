# _ReportRisk

Built in #141 as ticket I5 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_ReportValues](report-values.md); the design is [readers](../../engineering-tickets/trade-valuation-pipeline/06-readers.md) and [result fields by route](../../engineering-tickets/trade-valuation-pipeline/result-fields-by-route.md).

The batch's risk from its results: both deltas, since #177, `nominal_delta`, since #164 the batch's exposure still to price counted in lots of the index's reporting specification, and `delta`, the same lots weighted by the route's valuation treatment, the nominal lots themselves for a cleared batch and each live slot's lots times its payment group's discount factor for a bilateral one, [bilateral-excel-integration.md](../../engineering-tickets/trade-valuation-pipeline/bilateral-excel-integration.md); their unit; the DV01, nothing for a cleared batch and the analytic signed sensitivity for a bilateral one; and the valuation day, as evaluation stored them. The DV01's unit is the report's own words, the settlement currency per basis point, composed here and stored nowhere. The delta by contract, in lots, and the price sensitivity by contract, the settlement currency the mark moves for a move of one unit of quote price, are retained in the result and not spilled here, `util_ReadHandle` on the results showing them on each slot the contract prices, its `pricing_contract` since #165, as `contract_lot_delta` and `contract_sensitivity` with `lot_unit` and `sensitivity_unit` beside them; the same lots by observation day, calendar month or calendar year are [_ReportDelta](report-delta.md)'s, since #166. A report values nothing, converts nothing and bumps nothing. The design is [lot-delta-reporting.md](../../engineering-tickets/trade-valuation-pipeline/lot-delta-reporting.md). The code is `src/goosedove/excel/trades.py`.

## Worksheet contract

```python
def _ReportRisk(results: Handle[TradeResults]) -> MixedArray: ...
```

| | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 17 | `=_ReportRisk(A12)` | | | | | |
| | nominal_delta | delta | delta_unit | dv01 | dv01_unit | as_of |
| | float64 | float64 | str | float64 | str | datetime64[D] |
| | 11 | 11 | lots of NYMEX NG (10000 MMBTU) | 0 | USD per basis point | 24-Nov-2026 |

One handle, required: the results, the cell showing `_EvaluateTrades`'s result or a name for it. The spill is three rows by six columns since #177, the sixth the former fifth's and the layout one everywhere, no `delta_total` kept beside it, so the formula sits at A17, below the values' three rows at A13:D15; at A14 it would spill into them and show `#SPILL!`, and a sheet that read the unit, the DV01 or the day by position reads them a column to the right. `nominal_delta` is the sum of the lot deltas by contract, each the live exposure referencing that contract over the reporting lot's coefficient, zero where every slot of it has fixed: for the NG example sixteen lots of Z26 less five of F27, eleven lots of NYMEX NG; its unit names the lot, `lots of NYMEX NG (10000 MMBTU)`, the specification the index was made with and its size, so eleven lots are 110,000 MMBTU still to price, and the sensitivity behind them, 110,000 dollars per dollar an MMBTU, a one-cent move in every contract moving the mark by 1,100 dollars, reads back on the results as `contract_sensitivity`. A lot entered as another specification, or as a bare unit, counts the same: on an index quoted in cents a gallon with a reporting lot of a thousand barrels, a lot, a thousand barrels and 42,000 gallons are one lot each, 420 dollars a cent a gallon of sensitivity, and 2,500 MMBTU against a 10,000 lot are a quarter; a lot half of whose observation weight has fixed is a half, and a fixed group, paid or not, nothing, whatever its mark. The lot is the index's choice, not the rows', and an index made without one prices no trades. `delta` is the same lots weighted by the route's valuation treatment: for a cleared batch the nominal lots again, the two columns equal, and for a bilateral batch each live slot's lots times the discount factor of its payment group's day before any sum, [kernel.md](kernel.md#the-bilateral-path), so that the ticket's two groups, +10 and -10 of F27 paying a year and two years out at 0.95 and 0.90, report no nominal delta and 0.5 of delta. `dv01` is the change for a rise of one basis point in rates: zero for the cleared route, the undiscounted model's own answer and not a placeholder; for the bilateral route since #177 the analytic signed sensitivity of the mark to a parallel rise of one basis point in the continuously compounded zero rates, ACT/365F, -0.0001 times each unpaid group's time to payment in years times its NPV, summed, negative for an amount receivable and positive for one payable, the two groups' +0.0085 and the one receivable's -0.01; no bump, no second evaluation. A settled group contributes to none of the three.

## Excel help

| Item | Text |
|---|---|
| Function | Reports the batch's risk from its results: the nominal and the discounted delta in lots of the index's reporting specification, with that unit, the DV01 with its unit, the currency per basis point, and the valuation day, as evaluation stored them. |
| results | The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name for it. |

## The library checks

Nothing: the result is complete when it is published.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trade_valuation.py` | the NG example's spill cell for cell, 11 lots of NYMEX NG under both deltas and a DV01 of zero; since #177 the bilateral example's 0, 0.5 and 0.0085, its tick's 0.00935 and its replacement curve's 0.4 and 0.0088, the one receivable's 10, 10 and -0.01, then 0, 0 and -0.0119671232876712, then nothing on the payment day, and its cleared twin's equal deltas and zero; three bilateral batches whose two deltas differ and each reconcile to the time report's columns and the readback's contract columns; -5 once Z26 has fixed; the total unchanged by a tick; one trade's -12; a blank refused; since #164 the ETE rows, a lot, a thousand barrels and 42,000 gallons one lot each and three together, the partial Asian period a lot and a half, the same lot one lot in every quote and settlement unit with the index's conversions read back, the lot the index's choice, 10,000 MMBTU one NYMEX lot or four ICE lots, every method and a strip, the lots gone as the weights fix and after payment, and signed, fractional, additive in any order |
| `tests/performance/test_trade_valuation_budgets.py` | one handle resolved, one row laid out, no kernel call, nothing published; 1,948 bytes, 2,079 since #177 with the sixth column |
| `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `tools/excel_lifetime.ps1 -Groups valuation`, `workbooks/handles.xlsx` | the chain's delta read through the report on a sheet, from the host, through the lifetime's roll since #155, 2 lots while n26 is live and 0 once it has fixed, #REF! while the market fails, and at the foot of the handles sheet, B1307 and the toy's seven states in M1342 to M1348, 11 lots while both contracts are live, -5 once Z26 has fixed, 0 once both have; the lifetime's two barrels 0.002 of a thousand-barrel lot; since #177 the bilateral block's 0, 0.5 and 0.0085 in the smoke, on the host and in the kept workbook, and the lifetime's bilateral lot of q26, its delta below its nominal and its DV01 read through TEXT |

## Not here

No delta by contract spilled, which the result retains and `util_ReadHandle` shows by slot in lots and in the settlement currency; no monetary total, the sensitivity by contract read back by slot and summed by no one here; no discounted sensitivity in currency, which the readback shows by contract as `contract_discounted_sensitivity`; no bump convention, no key-rate DV01, no scenario; no roll-off view of the dates on which delta leaves, which the dated slots support when it is wanted.
