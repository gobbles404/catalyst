# Aggregate evaluated risk in Excel

[Series specification](aggregate-evaluated-results.md) ·
[Collector kernel](aggregate-risk-kernel.md) · [Single-result reporting](unified-risk-reporting.md) ·
[Pipeline overview](README.md) · [UAT notes](surface-uat-notes.md#12-aggregate-evaluated-results)

**Status:** Built in #180 on `claude/aggregate-excel`, stacked on PR #179 at `f604293`, the
[collector kernel ticket](aggregate-risk-kernel.md) with its compensated reductions, 11 October
2026, the page as the ticket; the [As built](#as-built-180) section at the end says what was
built, the one revision the owner agreed on 11 October, and what was not. PR #178 implements
the report on one result and PR #179 the private collector; this ticket does not claim either
has shipped.

**Suggested PR title:** `feat(excel): collect evaluated results for risk reporting`

## Outcome

A user passes one or many evaluated-result cells to `_AggregateResults`, receives one
aggregate handle, and passes that handle to the existing `_ReportRisk`. The same reader
continues to accept a single evaluated-result handle. Both paths show saved risk vectors
and their saved totals; collection does not evaluate trades again.

```text
_EvaluateTrades(...) -> trade_results_handle        # existing
_AggregateResults(result_handles) -> aggregate_results_handle
_ReportRisk(results, risk, bucket) -> mixed table    # either result kind
```

For example, B2 and B3 contain the evaluated results of HNG cleared and bilateral batches:

```excel
D2: =_AggregateResults(B2:B3)
F2: =_ReportRisk(D2,"delta","month")
```

An individual result still works directly: `=_ReportRisk(B2,"delta","month")`.
Add WTI results in B4:B5 and change the collection to `=_AggregateResults(B2:B5)`;
the report gains a WTI column. There is no separate aggregate-risk reader.

## Worksheet inputs

| Function / argument | Accepted input | Contract |
|---|---|---|
| `_AggregateResults(result_handles)` | One cell, a row, or a column of evaluated-result handles | Required, nonempty; preserve order and every occurrence |
| `_ReportRisk(results, risk, bucket)` / results | One TradeResults or AggregateResults handle | Required; no other handle kind |
| risk | `nominal_delta`, `delta`, `dv01`, `all` | Required, exact spelling, as in #178 |
| bucket | `day`, `month`, `year` | Required, exact spelling, as in #178 |

A 1x1 range is one result. Row order is left to right; column order is top to bottom.
Reject a true two-dimensional range, empty input, blanks, empty text, nontext cells,
creator failures, dead handles and wrong-kind handles. A failure names its one-based
input position or cell coordinate. Do not skip empty cells or return a partial collection.
Nested aggregate handles are refused by this first collector. Repeating the same result
cell intentionally counts it again; do not deduplicate by handle, trade ID or equal values.
Preserve the host's native Excel-error propagation before seam validation. Test creator
failure propagation through collection and then reporting: cell-qualified error labels
must retain the useful original failure, rather than accumulating nested wrapper errors.
Equivalent membership in differently shaped ranges has the same risks; it need not have
the same published handle, since the host's creator key includes the supplied arguments.

Use direct references or named ranges to result cells. Handle text is a runtime reference,
not a persistent portfolio identifier or a way to discover the latest evaluation.

## Seam and library boundary

Add only the input forms required by these two functions:

1. A typed handle vector accepting a scalar/row/column and delivering an ordered immutable
   collection of TradeResults objects. Validate shape before cells, then process cells in
   supplied order. Resolve each occurrence once, including repeated occurrences.
2. A bounded choice of the two concrete handle kinds for the existing reader. Resolve once
   and dispatch from that resolution. Keep kind/type validation at the seam.

The present seam supports neither form directly. Record the declarations, validation order
and refusals in `docs/seam/inputs.md` with registration and binding probes. Do not implement
them as arbitrary `Handle[object]`, untyped handle text, repeated store lookups, or internal
runtime type checking. Existing field-table handle columns are not a substitute for a
plain row/column of evaluated-result handles. Python declaration syntax is an engineering
choice within these boundaries.

The Excel creator calls #179's `aggregate_results(sources, counter)` and publishes its
AggregateResults through the existing handle machinery. Use the normal process-prefixed
`aggregate_results` kind without assigning a single index name to a multi-index object.
Keep the ordinary host reuse/publication/release behavior; this does not require a new
host transport or a new dependency graph.

The reader chooses the existing `risk_view` or `aggregate_view`, then uses #178's shared
RiskView formatter. It must not collect a single result just to report it, or recollect an
aggregate while reading it. A singleton collection still returns AggregateResults through
the ordinary collector path.

## Risk grouping and report layout

Retain #179's policies without introducing new financial calculations:

- All sources share `as_of`. Within an index group, require the exact retained Index,
  history and price-vector objects. Different Market wrappers over those same inputs pass.
  Distinct Index objects with the same exact name fail; names alone never establish identity.
- Sum nominal and discounted lots separately by index. Cleared delta equals nominal delta;
  bilateral delta is already discounted by its payment groups. Different payment dates do
  not prevent summing the saved delta on a common observation date. Do not blend factors.
- Sum DV01 by exact curve object, settlement currency and payment date. A shared curve and
  currency may combine HNG and WTI DV01. Different curves or currencies remain separate.
- Index columns follow first supplied appearance. Curve numbers follow curve-object first
  appearance, with currency groups separate. Do not invent index suffixes or a grand total
  across unrelated reporting lots.

Preserve the report's four leading rows: as_of context, column headers, type labels, then
**Total**. Chronological date rows follow. Dates are Excel dates. Headers retain the index
or curve/currency, measure and unit; use #179's labels and column order.

`nominal_delta` and `delta` use observation dates. `dv01` uses payment dates. `all` uses their
saved sorted union, with each index's nominal/delta pair followed by the rate columns.
Month/year use the first calendar day of the bucket. Keep represented fixed, paid and
net-zero dates; zero-fill absent intersections of valid saved vectors. Do not expand a
dense calendar, clip dates to as_of or insert payment-only rows into a delta-only report.

Mixed collections show their bilateral curve/currency DV01 columns; cleared sources add
zero without extra rate groups. An all-cleared collection shows one zero-total DV01 column
per currency, labelled cleared, with no dated rate rows. Single-result reporting keeps its
existing layout and numbers for every selection and bucket.

## Worked worksheet acceptance

Use synthetic one-unit reporting lots, not exchange specifications. As_of is 4 January
2027. HNG observes that day at 80 against fixed price 70; WTI observes 5 January at 55
against 50. Both bilateral sources pay 4 January 2028, 365 days after as_of, using the
same USD curve with DF 0.95. Cleared sources remain unpaid in this state. Within each
index, both sources share its history and price vector. Use valid synthetic schedules
and a later unused contract, preserving current calendar support limits.

| Source cell | Evaluated batch | Nominal delta | Delta | DV01 |
|---|---|---:|---:|---:|
| B2 | HNG cleared +10 lots | 10 | 10 | 0 |
| B3 | HNG bilateral +10 lots | 10 | 9.5 | -0.0095 |
| B4 | WTI cleared +2 lots | 2 | 2 | 0 |
| B5 | WTI bilateral +4 lots | 4 | 3.8 | -0.0019 |

First collect B2:B3. The HNG totals are nominal_delta **20**, delta **19.5**, DV01
**-0.0095**. The bilateral DV01 is `-0.0001 * 1 year * 95 NPV`.

Then collect B2:B5. `_ReportRisk(collection,"all","month")` has this body below the
unchanged context/header/type rows; labels are shortened here only for readability:

| Period | HNG nominal_delta | HNG delta | WTI nominal_delta | WTI delta | curve_1 USD dv01 |
|---|---:|---:|---:|---:|---:|
| **Total** | **20** | **19.5** | **6** | **5.8** | **-0.0114** |
| 1 Jan 2027 | 20 | 19.5 | 6 | 5.8 | 0 |
| 1 Jan 2028 | 0 | 0 | 0 | 0 | -0.0114 |

By day, HNG is on 4 January and WTI on 5 January; rate risk remains on 4 January 2028.
The day/month/year columns each reconcile to their saved Total within the existing
numerical tolerance. Delta-only reports omit the payment row; DV01-only reports omit
the observation rows. Retain #179's existing offsetting-payment example and tests too.

| Change through worksheet dependencies | Expected updated totals |
|---|---|
| HNG quote 80 -> 81; reevaluate HNG sources | Commodity deltas unchanged; combined DV01 -0.01235 |
| Original quotes; DF 0.95 -> 0.96; reevaluate bilateral sources | HNG delta 19.6, WTI delta 5.84, combined DV01 -0.01152 |
| Collect HNG cleared, HNG bilateral, HNG cleared again | HNG nominal 30, delta 29.5, DV01 -0.0095 |

## Recalculation and lifetime

The dependency chain is market/curve -> evaluated result -> collection -> report. A changed
result handle causes a new collection from its current input cells. Collection reads the
saved vectors from every occurrence; incremental updates/caches are outside this ticket.
Changing only the risk or bucket reformats the existing collection, with no new publication.

The aggregate retains source objects by reference, as #179 already does. A retained old
aggregate remains an immutable snapshot even when current evaluations change or the old
source handle entries are released. Retaining an object does not make its released handle
text valid again. Releasing the aggregate must let otherwise-unreferenced sources go.

Exercise quote updates, curve updates, as_of/history replacement, a failing input followed
by recovery, unchanged recalculation and a held old aggregate across repeated ticks. The
current failed formula must show the failure, never silently keep an old successful answer.
Use the existing lifetime groups and host conventions; document any measured growth.

## Debug readback

Register `util_ReadHandle` for the new kind through the normal kind reader. Show the saved
membership with occurrence positions, common as_of, index/rate groups, saved totals and
risk vectors. Repeats must be inspectable. Follow existing debug-table conventions and
document the layout. No repricing, new business aggregation, recursive trade expansion or
dependence on released source-handle text. This is diagnostic readback, not a second risk
report; `_ReportRisk` remains the daily-use surface.

## Verification and measured work

Add seam, host and worksheet acceptance for scalar/row/column inputs, one/many/repeated
sources, mixed indexes/routes, exact selectors, shape/cell failures, source identity
refusals, and no publication on failure. Pin #178's unchanged single-result reports and
compare singleton collection values with their source for every selection/bucket.

Carry #179's numerical protections through the surface: large opposite positions with
a small residual must retain that residual in the dated vectors and Total, including
reordered inputs. Keep the compensated reductions; do not re-sum formatted spills.
Exercise all-cleared, fixed-but-unpaid and paid states, different payment dates, curve/
currency groups, source reordering and structural zeros. Use hand expectations, not only
agreement between library and Excel paths sharing the same input error.

Pin one resolution per source occurrence and one collection publication, with #179's
existing occurrence/group/vector counters. Readers resolve one handle and select/format
saved views, publishing nothing and making no reductions, sorting or axis discovery.
Neither path reads quotes, fixings or discount factors or repeats trade creation,
preparation, evaluation or unit conversion. Measure retained/temporary bytes and work by
saved axes and output cells, not trade rows multiplied by a full calendar. Record before/
after counts in the PR; timing remains diagnostic.

Add a working collection block to `workbooks/handles.xlsx`, smoke and host coverage, and
the lifetime cases above. Update function help, the library aggregate/report pages, seam
decisions, pipeline README and UAT item 12. Run the full gate including the relevant Excel
and lifetime checks; preserve the project's separate review rule for existing goldens.

## Scope and completion

One focused integration PR should connect the existing collector and reader. If the two
seam input forms merit a separate review, split only that prerequisite and keep this ticket
as the acceptance contract. Engineering should flag changes to agreed behavior before
implementing them.

Complete when Excel can collect one or many evaluated batches and report the saved risk
correctly through the same reader, with the examples, refusals, work budgets and lifecycle
verified. No new aggregate mark/cash/reserve totals, FX, cross-index lot conversion,
key-rate DV01, quarters/hours, nested collections, portfolio persistence or index-name
registry. Unique index names at creation remain the owner's separate follow-up ticket.
`_ReportValues` and `_ReportReserves` continue to accept single TradeResults only.

## As built (#180)

Built on `claude/aggregate-excel` above #179's `f604293`, one pull request, the two seam forms
inside it as the ticket allowed; [aggregate-results.md](../../library/trades/aggregate-results.md)
is `_AggregateResults`'s page and [report-risk.md](../../library/trades/report-risk.md) names the
reader's second kind.

**The seam.** Two forms of declaration in `excel/bridge.py`, [inputs.md](../../seam/inputs.md)
decisions 44 and 45: `Handles[Kind]`, a cell, a row or a column of handles of one kind, the shape
checked first and then each cell resolved once in sheet order through the handle rule, a bad cell
named `result_handles cell (2, 1)`; and `Handle[A] | Handle[B]`, one handle of either kind, resolved
once by one store lookup and refused by its kind in both kinds' words, `expected trade results or
aggregate results handle`. Registration refuses a vector of any kind or of a seam type, a default on
either form, and a choice that names `object` or something that is no handle. `_resolve` takes a
tuple of kinds now, so no existing ledger moved; `_resolve_each` and `_handle_form` are new.

**The functions.** `_AggregateResults(result_handles)` in `excel/trades.py` calls #179's
`aggregate_results(sources, counter)` and publishes the record as `pid:aggregate_results:count`,
the ordinary handle machinery, no index name. `_ReportRisk(results, risk, bucket)` declares the
two kinds and asks the resolved object for its view, `TradeResults.report` and
`AggregateResults.report`, each a one-line selection of saved data, `risk_view` or
`aggregate_view`, into #178's `RiskView` and the shared `_risk_table`; no type check, nothing
collected to read a result, nothing recollected to read a collection. `_ReportValues` and
`_ReportReserves` take a single result as before and refuse the collection's handle in the seam's
words.

**The readback, revised.** `util_ReadHandle` on a collection shows the membership alone: one row
per occurrence in the order given, a repeat a row again, with its position, index, reporting lot,
route, the collection's number for its curve or a dash, currency, its own saved nominal delta,
delta and DV01, and the shared valuation day. The ticket asked for the saved totals and vectors as
well; the owner agreed on 11 October to leave those to `_ReportRisk`, since appending totals
beneath the membership rows would mix two kinds of rows, and nothing of the saved object is lost by
choosing which reader shows it. No handle text is shown, a source's cell possibly released while the
collection holds the object.

**Where it is checked.** `tests/unit/test_aggregate_excel.py`: the ticket's four sources on HNG
and WTI through the seam, the HNG pair's 20, 19.5 and -0.0095, the four's table by month and by
day, every selection and bucket, a row, a cell, a repeat as 30 and 29.5, the quote to 81 as
-0.01235 and the factor to 0.96 as 19.6, 5.84 and -0.01152, the 1e16, 1, -1e16 residual in every
order, the refusals in the seam's and the library's words with nothing published, and the reader
over either kind while the value readers refuse the collection; `tests/unit/test_handles.py`, the
two forms on probes; `tests/unit/test_help.py`, the help texts;
`tests/performance/test_trade_valuation_budgets.py`, one resolution per occurrence, one shape
check, one publication and the collector's own counts, the report over a collection resolving one
handle and copying a column per risk, 16,640 bytes to collect two results of 2,500 trades over 24
slots and 6,263 to report all three by day, the single result's rectangle. The host's `CallTests.cs`
collects the first valuation test's results twice and reads the doubled Totals, the readback and the
refusals, four smoke rows beside them; `tools/excel_smoke.ps1` collects QV8, QV22 and QV24 down RT3:RT5
and across RT1:RV1, two curve groups and the cleared one alone; `tools/excel_lifetime.ps1 -Groups
valuation` collects D18 and D30 through a quote tick, a failing cell and its recovery, a reformat
and a held old collection over fixed handle texts across a second tick; `workbooks/handles.xlsx`
holds the ticket's block from row 2380, the two indexes, the four results, the two collections, the
reports, the readback, the repeat, the two moves and the refusals.

**Not here.** No nested collection: a collection's handle in the vector is refused as another
kind. No collection of values or reserves. No unique-index-name rule at creation, the owner's
separate ticket. No incremental update or cache: a changed result remakes the collection from its
cells. No FX, no cross-index lots, no grand total. The lifetime group does not replace the
valuation day or the history under a collection; the day advance under manual calculation is
exercised on the results above it.
