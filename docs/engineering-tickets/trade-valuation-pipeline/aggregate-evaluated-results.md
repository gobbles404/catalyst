# Risk reporting and aggregation of evaluated results

[Pipeline overview](README.md) · [First implementation ticket](unified-risk-reporting.md) ·
[UAT notes](surface-uat-notes.md#12-aggregate-evaluated-results) ·
[Collector kernel ticket](aggregate-risk-kernel.md) ·
[Bilateral Excel integration](bilateral-excel-integration.md)

**Status:** Current series specification, 11 October 2026. The owner agreed to one risk
reader for a single evaluated trade array or a collection of evaluated arrays, an explicit
risk selection and time bucket, and a saved Total above the dated rows. This replaces the
10 October proposal for separate aggregate readers, a default day bucket and long tables.
The first ticket, [unified-risk-reporting.md](unified-risk-reporting.md), is built in #178 on
PR #177's path, reviewed clean at `788e5a7`; the second, [aggregate-risk-kernel.md](aggregate-risk-kernel.md),
the private collector, in #NN above it; the Excel creator and the reader's acceptance of its
handle are the next ticket's, and release and UAT remain separate.

The first PR establishes the report on one evaluated batch. The [second ticket](aggregate-risk-kernel.md), built in #NN privately,
defines the private collector kernel and makes the proposed identity, snapshot and duplicate
policies explicit for review. A subsequent PR exposes collection and extends that same
reader to the aggregate handle. These policies are not hidden decisions in the first PR.

## Public shape

```text
_ReportRisk(results, risk, bucket) -> table

# Later in this series:
_AggregateResults(result_handles) -> aggregate_results_handle
_ReportRisk(aggregate_results, risk, bucket) -> the same style of table
```

All three reader arguments are required. There is no implicit risk selection or bucket.

| Argument | Accepted values | Meaning |
|---|---|---|
| results | Evaluated-result handle; later, an aggregate-result handle | Read a completed snapshot |
| risk | nominal_delta, delta, dv01, all | One measure, or all three supported risk measures |
| bucket | day, month, year | Calendar grouping of that measure's underlying dates |

`nominal_delta` is undiscounted live exposure in the index's reporting lots. `delta` is
valuation-weighted exposure: equal to nominal for cleared trades, discounted per payment
for bilateral trades. `dv01` is the saved signed analytic sensitivity to a parallel +1 bp
rise in zero rates. `all` includes these risks only, not mark, cash or reserves.

```excel
=_ReportRisk(evaluated_hng,"delta","month")
=_ReportRisk(evaluated_hng,"all","day")
=_AggregateResults(A2:A5)
=_ReportRisk(collected_results,"dv01","year")
```

Cut over the existing `_ReportRisk` and retire `_ReportDelta` in the first reporting PR,
with kept callers migrated together. Do not add `_ReportAggregateDelta`,
`_ReportAggregateDV01`, `_ReportDV01` or a `summary` selection. Every dated report already
has its saved total; a separate `total` bucket is not part of this series specification.
Quarters, hours and index/valuation-parameter resolution settings remain deferred.

## What the user sees

The body is wide: one date column and a column for each selected compatible risk group.
The first body row is **Total**; chronological bucket rows follow. For illustration,
this future two-index `delta / month` report omits its context and type headings:

| Period | HNG delta | WTI delta |
|---|---:|---:|
| **Total** | **1.8** | **1.0** |
| 1 Dec 2026 | 6.2 | 2.9 |
| 1 Jan 2027 | -4.4 | -1.9 |
| 1 Feb 2027 | 0 | 0 |

Each column has its own reporting-lot basis. There is no grand total of HNG and WTI lots.
The Total is the saved scalar, not a SUM performed by the reader. Summing only the dated
rows should reconcile to it within the documented numerical tolerance. This is a useful
worksheet checksum, not a second valuation path.

Headings identify the index or curve/currency group, measure and unit. The common as_of
is visible in heading context. The [first ticket](unified-risk-reporting.md#spill-contract)
proposes the compact, exact heading arrangement and mixed date/Total column. Dates remain
actual Excel dates, not formatted date strings.

With `all`, keep nominal_delta then delta together for each index, in index order; append
DV01 columns in curve/currency-group order. With a single measure, omit unrelated columns.
Index groups follow first appearance in the collector's input range, not alphabetical order.
Names come from retained index definitions. Same-name distinct indexes need disambiguating
local group labels, and the debug view links those labels to the supplied occurrences.
Current discount curves have no name/currency metadata; use local curve-group labels and
the result's currency, without inventing a curve registry.

## The two date meanings

| Measure | Dates used for rows | Saved scalar |
|---|---|---|
| nominal_delta | Observation dates | Nominal lot total per index |
| delta | Observation dates, after payment-specific discount weighting | Discounted lot total per index |
| dv01 | Payment dates | DV01 total per compatible curve/currency group |
| all | Sorted union of the selected observation and payment buckets | Each column's own scalar |

A December crude observation can refer to an F27 future and still belongs to December
observation risk. A payment in January contributes to January DV01 even when every
observation was in December. Help text and column context must explain this distinction:
`all` puts the two date meanings on a shared display axis, not a shared economic meaning.

Day uses the actual date; month and year use their first calendar day. Start at the earliest
represented bucket, not automatically at as_of. Keep fixed and paid dates with zero risk;
keep signed net-zero buckets too. Fill absent group/date intersections with zero when
aligning saved vectors, but never turn a pricing failure into zero. Do not expand a dense
calendar or create rows for days not represented by any selected source axis.

Cleared results have zero scalar DV01 and no dated rate-risk entries, even if they retain
payment dates for moving mark to cash. They need no curve. A single cleared `dv01` report
therefore has Total = 0 and no dated rows; its `all` report has observation rows with zero
DV01. An all-cleared collection follows the same zero convention without inventing a curve.
Bilateral results retain their full payment axis after payment, with zero DV01 on paid dates.

## What sums with what

| Saved view | Aggregation key | Meaning |
|---|---|---|
| Nominal and discounted dated delta | Exact index identity, observation date, reporting-lot basis | Compatible cleared/bilateral live lots |
| Contract delta | Exact index identity, pricing reference, reporting-lot basis | Remaining risk against the future supplying the price |
| Dated DV01 | Exact curve identity, settlement currency, payment date, DV01 convention | Saved signed payment-group rate risk |
| Mark and cash, if carried in the collection | Settlement currency and route | Keep cleared/bilateral mark and cash distinct |
| Reserves, if carried in the collection | Settlement currency and reserve kind | Booked costs outside valuation |

Schedule method, clearing house, counterparty and entry units do not prevent summing
normalized risk on the same index. Different payment dates remain distinct through
valuation; sum their already-discounted delta on the common observation date afterwards.
Do not average or blend discount factors, or undo the payment ownership in source results.

DV01 can combine across HNG and WTI when curve, currency and definition match. Otherwise
keep separate groups. Use the existing signed analytic parallel +1 bp zero-rate convention,
ACT/365F: -0.0001 * time_to_payment * group_NPV. Payment-date DV01 is attribution by payment,
not curve-node or key-rate sensitivity. Fixed-but-unpaid trades may have zero commodity
delta and nonzero DV01. No FX conversion, cross-index lot conversion or currency-only
inference of a common curve is introduced.

Values and reserves are outside the new risk reader. The [collector kernel ticket](aggregate-risk-kernel.md)
retains them only through source-result references; it does not compute their aggregates.
Grouped value/reserve totals and their reports remain a later extension.

## Saved state and work boundaries

Read saved numerical results, never reconstruct risk by summing a formatted debug spill.
Current results already retain nominal and discounted observation-time vectors, contract
vectors, scalar totals and bilateral `dv01_by_group`. The missing reporting work is to
save payment-time DV01 views and the alignment needed for a combined display.

- Resolve static observation/payment day, month and year axes and their placement maps
  outside evaluation. Payment reporting uses all encoded payment groups, not the shrinking
  `unpaid_payments.days` used for discount-factor gathering.
- Reuse nominal vectors prepared with history. Evaluation reduces its already-calculated
  payment-group DV01 onto the saved payment axes. It retains the existing scalar totals.
- Prepare alignment for `all` upstream. Readers may copy/select through saved placements
  while formatting; they do not discover unions, sort dates, sum, reprice or convert units.
- Keep read-only arrays and source context. Share immutable vectors where possible; do
  not retain a dense trade-by-day matrix or duplicate every vector for presentation.
- Fail before publishing results/aggregates if any new reduction is nonfinite, including
  a bucket whose overflow is masked by cancellation elsewhere.

The later collector retains source-result references, input occurrences, index/lot and
curve/currency group context, compatible scalar totals and dated/contract vectors. Its
one-result path uses the same grouping model as many. Preserve zero dates and full static
payment axes. Collection membership/structure or curve-group associations may change an
axis; ordinary ticks do not. Local group numbers are not persistent business identifiers.

## Collector policies for the later tickets

Recommended initial policies, to make explicit in the implementation proposal:

- Same as_of throughout. Name mismatching input positions and dates; do not roll or revalue.
- Group by the exact retained Index object, never just a name or description. Separately
  created same-name indexes remain separate, without economic-equivalence inference.
- Within an index group, require the same history and price-vector references. Different
  Market wrappers over those same inputs are acceptable. Across indexes, common as_of
  does not promise simultaneous feed timestamps; use the supplied snapshots.
- Group rates by exact retained curve and result currency. The curve itself cannot validate
  currency because it stores none. Distinct curve objects remain distinct groups.
- For a mixed collection, report actual bilateral curve/currency DV01 groups; cleared
  inputs add zero without creating extra curve columns. For an all-cleared collection,
  propose one zero-total DV01 column per settlement currency, labelled cleared with no
  curve and no dated rate rows. Confirm this heading policy in the collector ticket.
- Every supplied occurrence contributes. Repeated handles count repeatedly; no silent
  deduplication by trade ID, handle or equal numbers. Caller owns overlapping membership.
- Accept a single cell or one-dimensional row/column of evaluated-result handles. Refuse
  empty input, true two-dimensional ranges, blanks, failed/dead/wrong-kind handles by
  position. No partial success; nested aggregate handles are outside this first collector.

Typed handle ranges and accepting either of two concrete result kinds are bounded seam
extensions, not capabilities to assume exist today. Resolve handles once at the seam;
the library receives typed objects, never handle text or store access. Do not use
`Handle[object]` or runtime guessing to bypass the declared contract.

## Worked collection acceptance

Synthetic HNG and WTI each use a one-unit reporting lot, not exchange lot specifications.
As_of is 4 January 2027. HNG observes that day at 80 against fixed price 70; WTI observes
5 January at 55 against 50. A shared USD curve has factors 0.95 at 4 January 2028 (365 days)
and 0.90 at 3 January 2029 (730 days). All amounts are unpaid. Use valid synthetic schedules,
histories and a later unused contract so calendar-end limitations do not affect this case.

| Source | Terms | Mark | Nominal delta | Delta | DV01 |
|---|---|---:|---:|---:|---:|
| A, HNG cleared | +10 lots | 100 | 10 | 10 | 0 |
| B, HNG bilateral | +10 paying in 365 days; -10 paying in 730 days | 5 | 0 | 0.5 | 0.0085 |
| C, WTI cleared | +2 lots | 10 | 2 | 2 | 0 |
| D, WTI bilateral | +4 paying in 365 days | 19 | 4 | 3.8 | -0.0019 |

The `all / day` body is:

| Period | HNG nominal_delta | HNG delta | WTI nominal_delta | WTI delta | Curve 1 / USD dv01 |
|---|---:|---:|---:|---:|---:|
| **Total** | **10** | **10.5** | **6** | **5.8** | **0.0066** |
| 4 Jan 2027 | 10 | 10.5 | 0 | 0 | 0 |
| 5 Jan 2027 | 0 | 0 | 6 | 5.8 | 0 |
| 4 Jan 2028 | 0 | 0 | 0 | 0 | -0.0114 |
| 3 Jan 2029 | 0 | 0 | 0 | 0 | 0.018 |

A delta-only report omits payment-only rows. A DV01-only report omits observation-only
rows. Month/year merge only like calendar buckets and retain separate risk columns. The
first payment DV01 is HNG -0.0095 plus WTI -0.0019. Values remain USD cleared mark 110,
bilateral mark 24 and cash zero; these are evaluation checks, not columns in this report.

HNG quote 81, with A and B reevaluated: cleared mark 120, bilateral mark 24.5; delta
unchanged; dated DV01 -0.01235 / +0.0198, total +0.00745. WTI results remain reusable.
At original quotes, replace the shared curve with factors 0.96 / 0.92 and reevaluate B
and D: HNG delta 10.4, WTI delta 5.84, bilateral mark 23.2; dated DV01 -0.01152 / +0.0184,
total +0.00688. Cleared results and commodity preparation remain reusable.

## Dependencies and delivery order

```text
history/as_of -> preparation --+
market -----------------------+-> evaluation -> ReportRisk
curve, when bilateral --------+       |
                                      +-> AggregateResults -> the same ReportRisk
other evaluated results --------------+
```

A quote or curve change updates evaluation, then collection and reports through Excel's
existing dependency graph. Initially rebuild the compact collection from all supplied
results when an input handle changes. No hidden cache, new volatility or incremental
aggregation promise. Retained old results/collections remain immutable and readable.
Failures publish nothing; exercise recovery, held snapshots and final release normally.

Deliver in reviewable slices after bilateral integration/UAT:

1. **Unified risk report for one evaluated batch.** The [first ticket](unified-risk-reporting.md)
   defines the required selectors, saved payment-time DV01, Total-first layout, removal
   of `_ReportDelta`, full caller migration and financial/workbook acceptance. No collector.
2. **Collector kernel.** The [second ticket](aggregate-risk-kernel.md), built in #NN, specifies typed source
   input, compatible risk groups and scalar/vector views, identity/duplicate policies,
   worked examples and work budgets. It reuses the first slice's report-view structure;
   no Excel creator or reader input change occurs in this slice.
3. **Collection surface and shared reader.** Typed handle range, `_AggregateResults`, the
   bounded two-result-kind reader input, wide multi-group headings, debug membership,
   kept workbook and lifetime coverage. Split the seam work into its own PR if size warrants.

Each PR has one purpose. Do not merge all slices just because they share a user-facing arc.
Keep source economics, payment ownership and existing value/reserve readers unchanged.

## Verification and budgets

Pin independent financial examples and reconciliation of each vector with its saved total.
Test netting by date, rolling Asian references, different payment dates, live/fixed/paid
states, repeated inputs, order changes, one/many, multiple currencies/curves, distinct
same-name indexes and every declared refusal. Check actual Excel dates/numbers, exact
selector choices, Total placement and stable zeros. Old reports must migrate explicitly.

Count entries mapped/reduced/aligned, source occurrences, output cells and temporary and
retained bytes. No additional quote/fixing/factor reads arise from reporting aggregation;
no trade resolution, unit conversion or preparation is repeated. Work scales with compact
saved axes/groups, not trade rows times a dense calendar. Readers perform selection and
formatting only. Pin before/after counts, run the normal gate, smoke, workbook and lifetime
checks, and obey separate review of existing golden changes. Timing is diagnostic only.

Cross-index hedge equivalence, FX, curve-node DV01, per-trade views, incremental collection,
scenario comparisons, hourly/quarterly buckets and portfolio persistence remain deferred.
