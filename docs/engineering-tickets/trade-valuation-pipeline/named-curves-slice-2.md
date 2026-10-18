# Curve-owned risk contributions, named labels and the collection of trades and cashflows

[Parent arc](multiple-discount-curves.md) · slice 2 of 3 · [Slice 1](named-curves-slice-1.md) · [Risk](../../library/trades/report-risk.md) · [Collection](../../library/trades/aggregate-results.md) · [Cashflows](../../library/cashflows/evaluate-cashflows.md) · [Cashflow ticket](cashflow-instrument.md)

**Status:** Approved for implementation on 18 October 2026, after review of the ticket as the first commit of its PR on `feat/curve-contributions` from `feat/named-curves` at `045fe1a`, stacked on #201; the review corrected B8's and B10's expected results, which hold the SOFR cashflow too, and asked for a test of several contributions from one result. Folds in the cashflow aggregation, the cashflow ticket's second PR, as decided on 18 October.

## Outcome

Every evaluated result keeps its rate risk and its cross-gamma as contributions owned by the exact curve that made them: one DV01 contribution and one cross-gamma contribution from today's single-curve trade evaluation, one DV01 contribution from a batch of cashflows, none from a cleared batch. Reports and readbacks name the curve, `SOFR USD dv01`, and `_AggregateResults` collects trade results and cashflow results in one range, combining contributions on the same exact curve object and currency, cashflow-only and mixed collections alike, the cashflows keeping their single-curve evaluation. Every economic number stands: marks, cash, deltas, DV01s, cross-gammas, every pinned total and vector are what they are today. What moves is where a vector is kept, what a column is called and which sources a collection takes. Nothing of the key, of the collection as an evaluation input or of mixed-curve evaluation: slice 3.

## Worksheet contract

```text
_ReportRisk(results, risk, bucket)   -> as today; the DV01 and cross-gamma columns named for their curve
_AggregateResults(result_handles)    -> aggregate_results handle; the cells trade results or cashflow results, in any mix
```

The aggregate page's HNG bilateral source B, +10 lots at 70 quoted 80 on 4 January 2027, paying 4 January 2028 on SOFR at 0.95; the cashflow ticket's batch, 10,000 receivable that day, 10,000 payable 3 January 2029 and 250 paid the day before, valued on the same SOFR; and a second SOFR of 0.96 and 0.92, two snapshots of one name.

| | A | B |
|---|---|---|
| 2 | B, HNG bilateral +10 lots on SOFR | `=_EvaluateTrades(B22,B14,B30)` shows `30512:trade_results:HNG:21` |
| 3 | the cashflow batch on SOFR | `=_EvaluateCashflows(B40,B41,B30)` shows `30512:cashflow_results:USD:22` |
| 4 | the cashflow batch on FFOIS, 0.96 and 0.92 | `=_EvaluateCashflows(B40,B41,B31)` shows `30512:cashflow_results:USD:23` |
| 5 | B valued on the second SOFR | `=_EvaluateTrades(B22,B14,B32)` shows `30512:trade_results:HNG:24` |
| 7 | `=_AggregateResults(B2:B3)` | shows `30512:aggregate_results:25`, the trade and the cashflow |
| 8 | `=_AggregateResults(B2:B4)` | shows `30512:aggregate_results:26`, the second cashflow on its own curve |
| 9 | `=_AggregateResults(B3)` | shows `30512:aggregate_results:27`, cashflows alone |
| 10 | `=_AggregateResults(B2:B5)` | shows `30512:aggregate_results:28`, two snapshots of SOFR |

`=_ReportRisk(B2,"dv01","year")`, the trade alone, and `=_ReportRisk(B7,"all","year")`, the trade and the cashflow:

| period | SOFR USD dv01 [USD per basis point] |
|---|---:|
| Total | -0.0095 |
| 1-Jan-2027 | 0 |
| 1-Jan-2028 | -0.0095 |

| period | HNG nominal_delta [LOT] | HNG delta [LOT] | SOFR USD dv01 [USD per basis point] | HNG SOFR cross_gamma [LOT per basis point] |
|---|---:|---:|---:|---:|
| Total | 10 | 9.5 | 0.8405 | -0.00095 |
| 1-Jan-2027 | 10 | 9.5 | 0 | -0.00095 |
| 1-Jan-2028 | 0 | 0 | -0.9595 | 0 |
| 1-Jan-2029 | 0 | 0 | 1.8 | 0 |

`=_ReportRisk(B8,"dv01","year")` is two columns, `SOFR USD dv01` with the trade and the SOFR cashflow together, 0.8405, and `FFOIS USD dv01` with the second cashflow's 0.88, -0.96 in 2028 and 1.84 in 2029; `=_ReportRisk(B9,"dv01","year")` is the cashflow result's own report, Total 0.85, and B3 twice in a range doubles it; `=_ReportRisk(B10,"dv01","year")` is three columns in first-appearance order, `SOFR (curve_1) USD dv01` with 0.8405, `FFOIS USD dv01` with 0.88 and `SOFR (curve_2) USD dv01` with the second trade's -0.0096, FFOIS unqualified since one object carries that name; its cross-gamma is `HNG SOFR (curve_1) cross_gamma` -0.00095 beside `HNG SOFR (curve_2) cross_gamma` -0.00096, the cashflows contributing nothing there. The three arguments of `_ReportRisk`, the selectors and the buckets are as they are. `_AggregateResults` takes a cell, a row or a column whose cells show `_EvaluateTrades`'s or `_EvaluateCashflows`'s results in any mix, the handle-vector seam widened to two kinds, [inputs.md](../../seam/inputs.md) decisions 44 and 45 together: a cell of another kind is refused at its cell in the two kinds' words, `result_handles cell (2, 1) is index handle '30512:index:HNG:3', expected trade results or cashflow results handle`, and everything else the seam refuses today it refuses as today. `_ReportValues` and `_ReportReserves` are untouched.

## The saved contributions

A `TradeResults` holds `rate_contributions` and `cross_contributions`, tuples of records, one each for a bilateral batch and empty for a cleared one; a `CashflowResults` holds `rate_contributions` with one. A rate contribution is the curve object, the currency, the DV01 total, the DV01 by payment day, by payment month and by payment year, the axes those vectors stand on, by reference, the encoding's payment axes for a trade result and the batch's distinct days, months and years for cashflows, and the early-risk facts for the month and year views. A cross contribution is the curve object, the cross-gamma by reference, by observation day, by contract month and by contract year, the total, the delta's axes by reference and the early facts. The vectors live in the contributions and nowhere else: the `dv01_by_...`, `cross_gamma...` and `early_...` fields leave the records' top level and every reader, the single result's view, the collector and the readbacks, reads the contribution, cut over with no second copy. The batch scalars stay where they are and mean what they mean today: `dv01` and `cross_gamma_total` are the batch's risk with every used curve shifted by one basis point together, equal to the one contribution's total here and the sum of the contributions' in slice 3, explicitly not the sensitivity to either curve alone; the per-group `payment_factor`, `payment_amount`, `npv_by_group` and `dv01_by_group` stay, so the slot and group readbacks are unchanged. The result's one `curve` stays as the batch's curve until slice 3 replaces it with the selection. Contributions are references to arrays the evaluation already makes: nothing is copied, nothing added to retained memory.

## The labels

| Column | Heading | Example |
|---|---|---|
| DV01 | the curve's name, the currency, `dv01`, the currency per basis point in brackets | `SOFR USD dv01 [USD per basis point]` |
| DV01, no curve | `cleared`, as today, for a cleared batch and for the columns of nothing a collection with no rate contribution shows | `cleared USD dv01 [USD per basis point]` |
| cross-gamma | the index's name, the curve's name, `cross_gamma`, the reporting lot per basis point | `HNG SOFR cross_gamma [LOT per basis point]` |
| cross-gamma, no curve | `cleared`, as today | `HNG cleared cross_gamma [LOT per basis point]` |

The curve's name is the name it was created with, as typed. In a collection where two distinct curve objects share a name, every heading and readback cell of either carries the name qualified by the object's place among the collection's curves of that name, by first appearance, `SOFR (curve_1)` and `SOFR (curve_2)`, both of them, never the first left bare; a name one object carries is never qualified, and a single result's labels never are, a result having one curve. The qualifier is display, not identity: groups are keyed by the exact object as today. The refusals that name a curve say the same word: the early-risk refusal `the DV01 of SOFR USD in the payment month from 2026-09-01 is ...`, the overflow refusal `the cross-gamma of index 'HNG' on SOFR for contract F27 is inf, ...`, and in a collection `on SOFR (curve_2)`. A label is read off the records and nothing is resolved: no registry, no lookup by name.

## The collection

Every source is held to the first's valuation day, as today, and every trade source to its index's compatibility rules, unchanged. A cashflow source joins no index group and no cross group; its one contribution joins the rate group of its exact curve object and its currency, made when the pair is first met, so a cashflow on a curve no trade uses makes a column of its own and a cashflow on a trade's curve sums into that curve's column. The groups read contributions, not records: a rate group is the exact curve object and the currency over every contribution on them, a cross group the exact index object and curve object, so a result holding several contributions in slice 3 sums into several groups with no change here. Positions, occurrences and the readback's rows stay one per source in the order given, a repeat a row again.

| Rule | Refused as |
|---|---|
| `nominal_delta`, `delta` or `cross_gamma` of a collection of cashflows alone, which has no index group | `risk is 'delta', expected dv01 or all for a collection of cashflows alone, which has no commodity risk`, the cashflow result's own words |
| a cell of another kind, a nested collection among them | `result_handles cell (2, 1) is aggregate results handle '30512:aggregate_results:25', expected trade results or cashflow results handle` |
| everything the collector refuses today, a second valuation day, two histories for one index, two price vectors, two indexes of one name, a sum past the largest number | as today, the curve named where `curve_1` was |

`all` on a mixed collection is each index group's two columns, then each rate group's, then each cross group's, as today; on a collection of cashflows alone the DV01 columns, as the cashflow result's `all` is. The cleared columns of nothing stand only when no source has a rate contribution, as today.

## Reading it back

The collection's readback keeps its twelve columns and its row per occurrence. `curve` shows the heading's word for the source's curve, `SOFR` or `SOFR (curve_2)`, or `-` for a cleared source. A cashflow occurrence shows `-` under `index` and `reporting_lot`, `cashflow` under `route`, its currency, its DV01 and the day, and `-` under `nominal_delta`, `delta`, `cross_gamma` and `cross_gamma_unit`, numbers a batch of cashflows has not. The trade results, the cashflow results, the trades and the prepared trades read back as today, column for column.

## Hand-worked acceptance

The grid above, from numbers already pinned: B's -0.0095 of DV01, 9.5 of delta and -0.00095 of cross-gamma, [aggregate-results.md](../../library/trades/aggregate-results.md); the cashflow batch's 0.85, -0.95 a year out and +1.80 two years out, [cashflow-instrument.md](cashflow-instrument.md). Collected together, `SOFR USD dv01` totals 0.8405, -0.9595 in 2028 and 1.8 in 2029, while `HNG nominal_delta` 10, `HNG delta` 9.5 and `HNG SOFR cross_gamma` -0.00095 are the trade's alone: adding a cashflow moves the DV01 of its curve and nothing else. On FFOIS at 0.96 and 0.92 the second cashflow is -0.96 and +1.84, 0.88 in all, in a column of its own with SOFR's 0.8405 unmoved. The cashflow alone collected is its own report; twice, 1.70. B on the second SOFR is -0.0096 and -0.00096, in qualified columns beside the first's, the first's holding the trade and the cashflow as before. Every number the suites pin today, the kernel's bilateral example, the aggregate page's four sources, the risk buckets' tables, the cross-gamma block and the bump's centered checks, stands under the new headings.

## Migration

The label `curve_1` is pinned in 30 places across seven unit test files, 9 in the smoke, 3 in the host and 12 on three pages; every one becomes the curve's name, `SOFR` where the fixture's curve is, `FFOIS` where a second curve is. Readers of the moved fields, `dv01_by_day` and the rest, read the contribution. The lifetime's `valuation` group collects as today and its `cashflows` group gains a collection of the batch with the trades' results through a factor change and the day's roll. The kept workbook's reports relabel themselves on recalculation, the collection block from row 2380 and the cross-gamma block's readback show names in their `curve` cells, and a block below the cashflow block holds the grid above; the harness compares every cell of both sheets before and after, allowing heading and `curve` text to change and nothing else. Pages: [report-risk.md](../../library/trades/report-risk.md), [aggregate-results.md](../../library/trades/aggregate-results.md), [evaluate-trades.md](../../library/trades/evaluate-trades.md), [evaluate-cashflows.md](../../library/cashflows/evaluate-cashflows.md), [read-handle.md](../../library/utilities/read-handle.md) for the collection's `curve` column, the library index; [inputs.md](../../seam/inputs.md) decisions 44 and 45 and [bridge.md](../../seam/bridge.md) for the two-kind vector; the cashflow ticket's status, this ticket and UAT item 24.

## Work and budgets

Contributions are references: no vector copied, no array added, retained bytes unchanged on every record, and the evaluation's ledgers move only where a function moved. The collector counts `contributions_collected`, one per contribution read, beside `sources_collected`; a cashflow source aligns its DV01 entries as a trade's does and nothing else; peaks follow groups and entries as today, pinned for a cashflow-only and a mixed collection beside the existing sizes. The two-kind vector decodes and resolves each cell once, as the one-kind vector does.

## Tests

- The contributions on a bilateral result, a cleared result and a cashflow result, by reference, frozen, the totals equal to the batch scalars; the labels for one curve, `cleared`, and the qualification of both snapshots; the refusals' words; in `tests/unit/test_bilateral_kernel.py`, `test_cross_gamma.py`, `test_cashflows.py` and `test_aggregate_risk.py`.
- The grid above through the seam, each collection, each selection and bucket, the readback rows, the mixed collection against its separate parts, the cashflow's DV01 added and the deltas and the cross-gamma unmoved, reordered and repeated; the two-kind range and its refusals; in `tests/unit/test_aggregate_excel.py`.
- Several contributions from one result, the shape slice 3 fills, in `tests/unit/test_aggregate_risk.py`: a result given a second rate contribution and a second cross contribution on another curve, the record remade with the tuples and the batch scalars summed, collected alone reports column for column what the two single-curve results collected together report, labels, Totals and every dated vector, by day, month and year; with the second curve a later snapshot of the first's name, both columns qualified.
- Every existing pinned number under its new heading, the suites renamed and nothing else; the help lines; the budgets with `contributions_collected` and the two new sizes.
- The host's fact for the mixed collection; the smoke's block; the lifetime's `cashflows` group; the kept workbook's block.

## Temporary gaps, closed in slice 3

A result holds one curve and one contribution of each kind until slice 3, the tuples being the shape slice 3 fills; the collection's readback shows one curve per occurrence, and slice 3 agrees the layout for a source on several, showing the names used without repeating the source's scalars; the trade results readback does not show the curve's name, which slice 3 adds beside the key on the payment groups. No adapter is written for any of these: the single-curve evaluator fills the contributions directly, and nothing is kept for compatibility.

## Not in this slice

The `discount_curve_key` field, the collection as `_EvaluateTrades`'s input, the selection by key, grouping by key, per-curve factor gathering and mixed-curve evaluation: slice 3. Cashflows on several curves: outside the arc. A combined-risk selector: none, the batch scalars keep their meaning. Any change to a number.
