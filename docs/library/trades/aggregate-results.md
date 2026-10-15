# _AggregateResults

Built in #180 as the ticket [aggregate-risk-excel-integration.md](../../engineering-tickets/trade-valuation-pipeline/aggregate-risk-excel-integration.md), the third of the [risk reporting and aggregation series](../../engineering-tickets/trade-valuation-pipeline/aggregate-evaluated-results.md), over the collector built privately in #179 as [aggregate-risk-kernel.md](../../engineering-tickets/trade-valuation-pipeline/aggregate-risk-kernel.md). One or many evaluated batches' saved risk collected into one handle, the lots by index and the DV01 by curve and currency, nothing valued, discounted or converted again, which [_ReportRisk](report-risk.md) reports as it reports one batch's.

## Worksheet contract

```python
def _AggregateResults(result_handles: Handles[TradeResults]) -> Handle[AggregateResults]: ...
```

| | A | B | D |
|---|---|---|---|
| 2 | HNG cleared +10 lots | `=_EvaluateTrades(B22,B14)` showing `1234:trade_results:HNG:21` | `=_AggregateResults(B2:B5)` showing `1234:aggregate_results:25` |
| 3 | HNG bilateral +10 lots | `1234:trade_results:HNG:22` | |
| 4 | WTI cleared +2 lots | `1234:trade_results:WTI:23` | |
| 5 | WTI bilateral +4 lots | `1234:trade_results:WTI:24` | |

One argument, required and without a default: a cell, a row or a column of cells each showing `_EvaluateTrades`'s result or a name for one, [inputs.md](../../engineering-tickets/trade-valuation-pipeline/../../seam/inputs.md) decision 44. The seam holds the range to one cell, one row or one column before any cell is looked at, a true two-dimensional range refused by its shape, `result_handles is 2x2 array, expected one cell, one row or one column of trade results handles`, a blank, a number or a left-out argument as any scalar is, `result_handles is missing, expected trade results handles in a cell, a row or a column`; then each cell is resolved once, in sheet order, left to right along a row and top to bottom down a column, the first bad cell named by its coordinates whichever way it is bad, `result_handles cell (2, 1) is blank, expected trade results handle`, a creator's failure relayed whole behind the cell's name, and `_ReportRisk` or `util_ReadHandle` over the failed collection's cell shows the creator's text once behind its own wrapper, the relay rule reading through the cell's name. A collection's own handle in the vector is another kind, `result_handles cell (1, 1) is aggregate results handle '1234:aggregate_results:25', expected trade results handle`, so no collection nests. Every cell counts, a repeated cell twice, and the order given is the record's order. The cell shows the handle, `pid:aggregate_results:count`, no index name, a collection spanning indexes; it is shared while equal calls are live and released when its creators go, as every handle is since #114, and a collection held by a cell keeps its sources alive after their own cells have moved on. `=_ReportRisk(D2,"all","month")` then spills the ticket's table:

| | F | G | H | I | J | K |
|---|---|---|---|---|---|---|
| 2 | as_of | 4-Jan-2027 | - | - | - | - |
| 3 | period | HNG nominal_delta [LOT] | HNG delta [LOT] | WTI nominal_delta [LOT] | WTI delta [LOT] | curve_1 USD dv01 [USD per basis point] |
| 4 | str \| datetime64[D] | float64 | float64 | float64 | float64 | float64 |
| 5 | Total | 20 | 19.5 | 6 | 5.8 | -0.0114 |
| 6 | 1-Jan-2027 | 20 | 19.5 | 6 | 5.8 | 0 |
| 7 | 1-Jan-2028 | 0 | 0 | 0 | 0 | -0.0114 |

## Excel help

| Item | Text |
|---|---|
| Function | Collects one or many evaluated batches' saved risk into one collection, the lots by index and the DV01 by curve and currency, nothing valued again, and shows its handle, which _ReportRisk takes beside a single result's. |
| result_handles | The results handles to collect: a cell, a row or a column of cells showing _EvaluateTrades's results, such as B2:B5, in the order given, every one counted and a repeat counted again. |

## The library checks

In the order given, each occurrence's day first, then its index's compatibility; a sum past the largest number after the groups are made. Nothing of the collection is made when a refusal stands, and a collection already held is unchanged by a later call that fails.

| Rule | Refused as |
|---|---|
| Every occurrence is valued on the first's day | `results 2 is valued on 2027-01-05, expected 2027-01-04, the valuation day of results 1` |
| One index object per name: a distinct index object whose name a group already has is a mistake to show, not two columns `HNG 1` and `HNG 2` and not a silent merge | `results 2 is on another index named 'HNG' than results 1, expected one index for one name` |
| One history object per index | `results 2 is on index 'HNG' over another history than results 1, expected one history for one index` |
| One price-vector object per index; another `Market` wrapper over the same two objects combines | `results 2 is on index 'HNG' quoted off another price vector than results 1, expected one price vector for one index` |
| Every new vector and total is finite, by contract, day, month, year or in all, the vectors before the total | `the nominal delta of index 'HNG' for contract F27 is inf, expected a finite number of lots; the results' lots sum past the largest number` |

Identity is the exact object, never a name: results sharing one index object combine, a cleared occurrence is in its index group and in no rate group, a rate group is the exact curve object and the result's currency, one curve valuing two currencies two groups under one number, and the groups and the curve numbers follow first appearance. Each result has already applied its valuation treatment, so the collector sums the saved nominal deltas and the saved discounted deltas separately and discounts nothing again: HNG cleared +10 and HNG bilateral +10 at 0.95 are 20 nominal and 19.5 discounted. Trade IDs are no key; two results of equal trades count separately.

## The record

| Field | What it holds |
|---|---|
| `as_of` | the valuation day every source shares |
| `sources` | the occurrences in the order given, every one, by reference |
| `index_groups` | one `IndexGroup` per distinct index object, in first-appearance order: the index, its reporting lot, the history and the price vector its occurrences share, the occurrences' positions, the summed vectors by contract, by observation day and since #NN by contract month and year with their axes and the two saved totals |
| `rate_groups` | one `RateGroup` per distinct curve object and currency among the bilateral occurrences, in first-appearance order: the curve, its number by first appearance, the currency, the positions, the DV01 by payment day, month and year with their axes and the saved total |
| `currencies` | the sources' currencies in first-appearance order, the DV01 columns of nothing a collection valued on no curve reports |
| `by_day`, `by_month`, `by_year` | `ReportAxes`: the union of the index groups' axes with each group's places, the union of the rate groups' payment axes with each group's places, and the union of both with every group's places on it |

Every array is frozen; nothing of a source's preparation, market or curve is copied, and nothing is written after the record is made. `AggregateResults.report(risk, bucket)` is the one way a reader asks for a view: a one-line selection, `aggregate_view`, into the same `RiskView` a result's `TradeResults.report` selects through `risk_view`, so `_ReportRisk` lays out one rectangle for either and checks no type, [report-risk.md](report-risk.md).

## The readback

`util_ReadHandle` on the collection shows its membership, since #180: one row per occurrence in the order given, a repeat a row again, with each source's own saved totals and the day every source shares. The collection's totals and vectors are `_ReportRisk`'s to show, the owner's revision of 11 October to the ticket, since appending totals beneath the membership rows would mix two kinds of rows; no handle text is shown, a source's cell possibly released while the collection holds the object.

| position | index | reporting_lot | route | curve | currency | nominal_delta | delta | dv01 | as_of |
|---|---|---|---|---|---|---:|---:|---:|---|
| int64 | str | str | str | str | str | float64 | float64 | float64 | datetime64[D] |
| 1 | HNG | LOT | cleared | - | USD | 10 | 10 | 0 | 4-Jan-2027 |
| 2 | HNG | LOT | bilateral | curve_1 | USD | 10 | 9.5 | -0.0095 | 4-Jan-2027 |
| 3 | WTI | LOT | cleared | - | USD | 2 | 2 | 0 | 4-Jan-2027 |
| 4 | WTI | LOT | bilateral | curve_1 | USD | 4 | 3.8 | -0.0019 | 4-Jan-2027 |

## The worked example

The ticket's four sources on 4 January 2027, one-barrel indexes HNG, whose F27 expires that day, and WTI, whose F27 expires the day after, the bilateral two paying 4 January 2028 on one USD curve of 0.95 a year out: A, HNG cleared +10 at 70 quoted 80; B, HNG bilateral +10 the same; C, WTI cleared +2 at 50 quoted 55; D, WTI bilateral +4 the same. B2:B3 collected are 20 nominal, 19.5 discounted and -0.0095 of DV01, `-0.0001 * 1 year * 95`. B2:B5 by month is the table above; by day HNG's deltas stand on 4 January and WTI's on the 5th, with the DV01 on 4 January 2028; `nominal_delta` and `delta` keep the observation rows alone, one column per index, `dv01` the payment row alone, one column per curve and currency. HNG quoted 81 moves the DV01 to -0.01235 and no delta; the factor 0.96 moves the deltas to 19.6 and 5.84 and the DV01 to -0.01152; A, B and A again are 30, 29.5 and -0.0095. Three results of 1e16, 1 and -1e16 lots on one index keep the 1 in every dated vector and in the Total whatever their order, #179's compensated reductions. An all-cleared collection's `dv01` is a Total of nothing per currency, `cleared USD dv01 [USD per basis point]`, over no dated row.

## What it reads and what it does

Per occurrence, from the seam: one resolution of its cell, after one check of the range's shape and one pass decoding the cells, each text taken in turn; one publication of the record. From each result, the collector reads `encoded.references` with the saved `lot_delta` and `discounted_lot_delta`, the preparation's `daily_lots`, `monthly_lots` and `yearly_lots` on the encoding's day, month and year axes, the saved `dv01_by_payment_day`, `_month` and `_year` on the payment axes for a bilateral result, and the three saved totals. It concatenates the occurrences' axes, takes the unique days and their places by one search, sums each occurrence's entries into its places with one compensated pass per occurrence under a guard against overflow, and takes the unions of the groups' axes for the three report levels. Work: `sources_collected`, `index_groups`, `rate_groups`, `entries_aligned`, `aggregate_reductions` and `report_coordinates`, each reported to the counter; `_summed` once per vector, `_compensated` once per occurrence per vector, `_outrun` once per total. A read of the collection makes one copy per column through the saved places and nothing else, [report-risk.md](report-risk.md).

## Tests

| Where | What |
|---|---|
| `tests/unit/test_aggregate_excel.py` | the ticket's four sources through the seam: the HNG pair's 20, 19.5 and -0.0095, the four's table by month and by day, every selection and bucket; a row, a cell, a boxed cell and a repeat as 30 and 29.5; the readback's membership rows; an all-cleared collection; the quote to 81 as -0.01235 and the factor to 0.96 as 19.6, 5.84 and -0.01152; the 1e16, 1, -1e16 residual in every order; every refusal in the seam's and the library's words with nothing published; a failed evaluation through the collection, the report and the readback showing the creator's text once; the reader taking either kind while `_ReportValues` and `_ReportReserves` refuse the collection |
| `tests/unit/test_aggregate_risk.py` | the collector's own figures since #179: one source collecting as itself, repeats and order, the compatibility refusals, the overflow refusal by coordinate, the compensated residual |
| `tests/unit/test_handles.py` | the two forms on probes: `CollectCurves` over a vector of curves in sheet order, every cell counted, and its refusals, a true array, a blank, a number, a boolean, empty text, text naming nothing, another kind, a creator's failure, a left-out argument; a failed vector relayed once through either consumer; `ReadEither` over two kinds; the registrations refused |
| `tests/unit/test_help.py` | the two help texts |
| `tests/performance/test_trade_valuation_budgets.py` | one shape check, one pass over the cells, one resolution per occurrence, one publication and the collector's own counts at two results and at twenty-four, no numpy call of the seam's own, nothing of the kernel, the market or the curve; the report over a collection resolving one handle, `AggregateResults.report`, `aggregate_view` and a copy per column into #178's rectangle, nothing published; 16,640 bytes to collect two results of 2,500 trades over 24 slots and 6,263 to report all three by day, the single result's rectangle |
| `tests/performance/test_aggregate_budgets.py` | the collector's counts by source, group, entry, reduction and coordinate since #179 |
| `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `tools/excel_lifetime.ps1 -Groups valuation`, `workbooks/handles.xlsx` | QV8, QV22 and QV24 collected down RT3:RT5 and across RT1:RV1, two curve groups beside the UNIT group, the cleared one alone, the readback and the refusals; the host's first valuation test collecting its results twice and reading the doubled Totals, the readback and the refusals, with four smoke rows; D18 and D30 collected in AE4 through a quote tick, a failing cell and its recovery, a reformat, a factor change, a full recalculation and a held old collection over fixed handle texts across a second tick; the kept workbook's block from row 2380, the two indexes, the four results, the two collections, the reports, the readback, the repeat, the two moves and the refusals |

## Not here

No nested collection, a collection's handle in the vector refused as another kind. No collection of values or reserves, `_ReportValues` and `_ReportReserves` taking a single result. No equivalence of lots across indexes, no FX, no grand total across unrelated lots. No rule that index names are unique at creation, the owner's separate follow-up; the collector refuses two index objects of one name when it meets them. No incremental update or cache: a changed result remakes the collection from its cells. No display name on the labels, the index's name as made.
