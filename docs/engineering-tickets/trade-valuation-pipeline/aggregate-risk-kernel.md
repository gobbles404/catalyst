# Collector kernel for evaluated risk

[Series specification](aggregate-evaluated-results.md) ·
[Previous ticket](unified-risk-reporting.md) · [Pipeline overview](README.md) ·
[UAT notes](surface-uat-notes.md#12-aggregate-evaluated-results)

**Status:** Built in #179 on `claude/aggregate-risk`, stacked on PR #178 at `88f838c`, the
[unified risk reporting ticket](unified-risk-reporting.md) with its saved payment-time DV01,
11 October 2026, the page as the ticket; the [As built](#as-built-179) section at the end says
what was built and what was not, with the owner's three clarifications of 11 October. This
ticket does not claim the first slice has shipped.

**PR title:** `feat(trades): aggregate saved risk across evaluated batches`

## Outcome and scope

Combine one or many evaluated trade arrays into one immutable collection of saved risk.
Cleared and bilateral HNG exposures combine by index and observation date. WTI remains
a separate commodity group. DV01 combines by curve, currency and payment date, including
across commodities when those rate-risk facts match.

This PR builds the library calculation and retained state. The following PR exposes
`_AggregateResults(result_handles)` in Excel and lets the existing `_ReportRisk` accept
its handle. No new worksheet function, handle kind registration, input-range binding or
aggregate workbook formulas are introduced in this slice.

Collect risk only: nominal_delta, delta and dv01, their dated vectors and contract lot
vectors. Source results remain available by reference, including their values/reserves;
do not compute aggregate mark, cash or reserves in this PR. Their reporting is a separate
extension, not necessary to establish the risk collection.

## Private boundary

Illustrative signature; use the repository's naming and typed collection conventions:

```python
aggregate_results(
    sources: Sequence[TradeResults],
    counter: WorkCounter,
) -> AggregateResults
```

The input contains already-created library objects. Snapshot membership into an immutable
tuple, preserving order and every occurrence. Refuse an empty input. One source uses the
same path and returns the same aggregate record kind as many; do not return the source
TradeResults as a singleton shortcut.

No handle strings, store access, Excel parsing, implicit market/curve argument or lookup
of the latest result. Trust source types and invariants established by their creators;
validate the new collection compatibility rules here. The later seam will resolve each
handle cell once and pass these typed objects.

## Collection policy for this slice

These include the owner's 11 October response to engineering. Flag a proposed
change to their financial meaning before implementation; do not silently choose different
deduplication, identity or snapshot behavior.

| Question | Rule |
|---|---|
| Valuation day | Every occurrence has the same as_of. |
| Commodity group | The exact retained Index object, with its existing reporting-lot basis. Names and descriptions are labels. |
| Name collision | Distinct Index objects sharing the same exact name fail the collection; do not suffix their headings or merge by name. |
| Commodity snapshot | Within that index group, the exact same history and price-vector objects. Separate Market wrappers over those objects are acceptable. |
| Rate group | Exact retained discount-curve object, result settlement currency and the existing DV01 convention. |
| Repeated input | Every occurrence counts. A repeated result object contributes repeatedly. |
| Order | Commodity and rate groups each follow first appearance among input occurrences. |

Apply compatibility checks even to zero-quantity, fully fixed or fully paid sources.
Do not skip a stale snapshot because its current live risk is zero. Equal values in a
new history or price vector do not establish identity. Same-name distinct indexes fail,
even if they share a schedule or have identical numbers. Creation-time uniqueness is a
separate follow-up, unique index names at creation, outside this PR; this collector guard does not depend on it.

Use object identity, not dataclass equality, hashing of array contents or comparison of
names. These records contain NumPy arrays. Identity maps may use process-local object
identifiers while retaining strong references; those identifiers are never business IDs,
saved labels or user-visible identity keys. Exact Index identity already fixes the lot
definition: no new specification lookup, unit conversion or lot-equivalence resolver.

Different curves are allowed, including within one index's sources. Commodity delta sums
the already-discounted exposures; DV01 stays separated by curve/currency. Equal factor
values in distinct curve objects do not merge them. A curve shared across currencies
still produces separate currency groups. The curve stores no currency metadata; this
grouping does not independently validate its currency.

Across indexes, common as_of does not assert simultaneous feed timestamps. The collection
uses the supplied snapshots and does not find newer ones. Distinct curve objects may be
intentional alternatives or different versions; the collector keeps them separate and
does not infer which is current. A common curve input on the sheet is how users make a
shared rate group.

Repeats are not mistakes for this function to correct. `[A, B, A]` includes A twice;
distinct result objects containing equal trades also count separately. Keep occurrence
positions so a later debug spill can make membership obvious. Exposed positions are
one-based, matching Excel; internal array offsets may remain zero-based. The caller owns overlapping
trade populations; trade IDs are not a deduplication key.

## Retained state

Use small typed records and immutable arrays. The following is the data contract, not a
requirement for these exact class/field names or a generic aggregation framework.

| State | Retain |
|---|---|
| Collection | Common as_of; ordered tuple of source results; occurrence-to-group mappings |
| Each index group | Index, history and price-vector references; readable index/lot context; contributing occurrence positions |
| Commodity scalars | Sum of source nominal lot totals and sum of source discounted lot totals, separately |
| Commodity dated risk | Observation day/month/year axes and both lot vectors on each axis |
| Commodity contract risk | Stable union of pricing references within that index, with nominal and discounted lot vectors |
| Each rate group | Curve reference, settlement currency, DV01 convention and contributing occurrence positions |
| Rates | Sum of source DV01 scalars; full payment day/month/year axes and DV01 vectors |
| Reporting layout | Saved compact union axes, column descriptors and placement maps for each risk/bucket selection |

Keep enough membership/context to explain every group without revisiting trades. Index
headings use the unambiguous retained name. Number distinct curve objects by first
appearance within this collection: one curve used in USD and EUR keeps the same curve_1
label in two separate currency groups. Curve groups link back to their occurrences.
Local numbers are not persistent identifiers. Do not add an identity registry here.

Retain source references rather than copying their preparation, markets, curves or raw
trade rows. New vectors are read-only; sharing existing immutable arrays is allowed when
it preserves the same one/many behavior. The collection owns its membership: mutating a
caller's input list later cannot change it. Holding an old collection keeps its original
source snapshots readable after newer evaluations are built.

No aggregate price-sensitivity-in-quote-units view is required. The source results retain
that detail; aggregate contract risk here is the nominal and discounted lot vectors that
reconcile with the selected risk measures.

## Numerical work and dates

Consume the saved unformatted views from the preceding reporting slice. Do not parse
`util_ReadHandle` output, read repeated contract totals off slots, or traverse observations
again to calculate risks that evaluation has already saved.

1. Establish membership, identities and compatible groups.
2. Form compact sorted unions within each group and map source entries onto them.
3. Reduce saved nominal/discounted lot vectors and saved payment-time DV01 by those maps.
   Produce day/month/year views, reusing source bucket views where useful; do not multiply
   payments by discount factors again or recalculate DV01 from NPVs.
4. Sum source scalar totals separately. These become the saved Total values; reconcile
   them with the resulting vectors within documented numerical tolerances.
5. Retain the report-axis unions and placements needed by the existing private selector
   and formatter. The later reader selects and copies saved data, without reductions.

Python iteration over source/group records is metadata orchestration. Numerical alignment
and reduction use arrays, not Python loops over trades, dates, contracts or risk entries.
Avoid pairwise scans across all sources and dense source-by-calendar matrices.

Contract coordinates are references into a particular index's schedule. Merge them only
inside that index group, in its schedule order. Neither a bare row number nor a contract
code is globally meaningful across indexes. A December Asian can carry January/February
contract risk while its observation vector stays in December.

Keep each source's structural dates, including zeros from netting, fixing and payment.
The rate axis comes from the full saved payment view, never just unpaid dates. Month/year
use calendar bucket starts, matching the first ticket. Do not clip to as_of or insert a
full calendar. The shared report axis for nominal_delta/delta is the union of commodity
observation buckets; dv01 uses payment buckets; all uses the union of both. If an
observation and payment share a date/bucket, show one row with separate risk columns.

Different payment dates have already affected each source's discounted delta. Sum those
values on observation dates without blending factors. Never total lots across indexes,
DV01 across incompatible currency/curve groups, or delta together with DV01.

Cleared sources have zero DV01 and no rate axis. In a mixed collection, only actual
bilateral curve/currency groups produce DV01 columns; cleared inputs add no fake curve
group. If every source is cleared, retain one zero-total reporting column per settlement
currency, in first-appearance order, with empty date axes and no curve. This supports the
first ticket's cleared Total-only DV01 convention. These zero columns are display context,
not evidence that a discount curve was supplied.

Check every newly reduced scalar and vector for finiteness before returning the aggregate.
An overflowing bucket or contract is a failure even if another coordinate could cancel
it in the total. Preserve signed cancellation; do not clip, drop small values or replace
nonfinite results with zero. Determinism is required for the same ordered input; permutation
properties compare by identity within the reviewed floating-point tolerance.

## Refusals

Check nonempty input first. Then inspect source occurrences in supplied order: as_of,
same-name/different-index conflict, then history and price-vector compatibility with the
first occurrence of that index. Name both occurrence positions and the index name on
name or snapshot conflicts; name both
dates on an as_of conflict. Do not expose memory addresses. Numerical failures then
identify the measure, group and date/contract or Total affected.

For example, collection of HNG source A at the old quote snapshot and B at its replacement
fails even if both as_of dates agree. Reevaluating both against the shared new vector
makes the collection valid. Do not re-evaluate B internally, exclude A, or return a
partial collection. Existing held collections remain unchanged when a new call fails.

Empty cells, wrong-kind handles, two-dimensional input ranges and creator errors are
surface refusals for the following PR. Do not implement a second handle validator here.

## Worked acceptance

Use the series' synthetic HNG and WTI fixtures, each with a one-unit reporting lot.
As_of is 4 January 2027. HNG observes that day at quote 80 versus fixed price 70; WTI
observes 5 January at 55 versus 50. All payments are unpaid. Bilateral sources share
one USD curve: 0.95 at 4 January 2028 (365 days) and 0.90 at 3 January 2029 (730 days).
Each index's cleared/bilateral sources share its exact history and price vector.
Both day counts are measured from as_of. In particular, D pays on 4 January 2028,
not 365 days after its 5 January 2027 observation.

| Source | Terms | Nominal delta | Delta | DV01 |
|---|---|---:|---:|---:|
| A HNG cleared | +10 lots | 10 | 10 | 0 |
| B HNG bilateral | +10 paying in 365 days; -10 paying in 730 days | 0 | 0.5 | 0.0085 |
| C WTI cleared | +2 lots | 2 | 2 | 0 |
| D WTI bilateral | +4 paying in 365 days | 4 | 3.8 | -0.0019 |

For a simpler explanation of mixed routes, a cleared +10 has nominal_delta 10 and delta
10; a bilateral +10 at DF 0.95 has nominal_delta 10 and delta 9.5. Together they report
nominal_delta 20 and delta 19.5. Sum each source's saved delta after its own valuation
treatment. This explanatory example does not replace the acceptance figures above.

First prove `[A, B]`: one HNG group, nominal Total 10, delta Total 10.5; one USD curve
group with payment DV01 -0.0095 / +0.018 and Total +0.0085. Then `[A, B, C, D]` produces
the following saved all/day view (a library test, not a new Excel spill in this PR):

| Period | HNG nominal_delta | HNG delta | WTI nominal_delta | WTI delta | Curve 1 USD dv01 |
|---|---:|---:|---:|---:|---:|
| **Total** | **10** | **10.5** | **6** | **5.8** | **0.0066** |
| 4 Jan 2027 | 10 | 10.5 | 0 | 0 | 0 |
| 5 Jan 2027 | 0 | 0 | 6 | 5.8 | 0 |
| 4 Jan 2028 | 0 | 0 | 0 | 0 | -0.0114 |
| 3 Jan 2029 | 0 | 0 | 0 | 0 | 0.018 |

The first payment combines HNG -0.0095 and WTI -0.0019. Selected delta views omit
payment-only rows; selected DV01 views omit observation-only rows. Month/year group only
matching calendar buckets. Neither risk is reassigned to its pricing contract's month.

Additional exact expectations:

| Input/change | Expected result |
|---|---|
| `[B]` | Same scalar/dated/contract risks as B, through the aggregate path |
| `[A, B, A]` | HNG nominal 20, delta 20.5; DV01 remains 0.0085 |
| Reorder to `[C, D, A, B]` | WTI columns first; identical economic groups and numbers |
| HNG quote becomes 81; reevaluate A and B | Lot totals unchanged; USD payment DV01 -0.01235 / +0.0198, Total 0.00745 |
| Original quotes, shared curve becomes 0.96 / 0.92; reevaluate B and D | HNG delta 10.4; WTI delta 5.84; USD DV01 -0.01152 / +0.0184, Total 0.00688 |

Use valid histories and a later unused contract, preserving existing calendar support
limits. Hand figures are the oracle; comparing two aggregation paths alone does not prove
financial correctness. Keep the project tolerances explicit for signed cancellation.

## Regression and work acceptance

- Reconcile commodity scalars, contract vectors and observation day/month/year vectors;
  reconcile rate scalars and payment views. Singleton collection matches its source for
  every selector/bucket. Verify source arrays remain unmodified and read-only.
- Cover sources with overlapping and disjoint observation dates/contracts; multiple
  payment groups on the same date; different dates in one month and across years;
  observation/payment intersections. Keep fixed, paid and net-zero coordinates.
- Same-index different Market wrappers over the same history/vector pass. Equal-valued
  but distinct histories/vectors fail. Distinct same-name indexes fail by name and input
  positions, without suffixing or name-based merging. Apply
  these rules with zero risk too; keep one/many and duplicate inputs on the same path.
- Cover distinct equal-valued curves, several curves within one index, one curve across
  commodities and across currencies, all-cleared collections and mixed routes. Test a
  fully paid bilateral source retains its zero payment axis and rate-group identity.
- Reverse source order and compare by retained identity; group numbering changes with
  first appearance, not the arithmetic. Copying the input list or appending to it after
  collection cannot mutate membership. New evaluations cannot mutate old collections.
- Exercise overflow of scalar, dated and contract reductions before return, including
  finite source values with opposing risk elsewhere. No partial success.
- Prove collector-attributable quote, fixing and factor reads, trade resolution, unit
  conversion, preparation and evaluation calls are all zero. Readers of saved views
  perform no further grouping, sorting, bucketing or summation.
- Count source occurrences, groups, vector entries consumed, alignment/reduction work
  and output coordinates. Measure temporary and newly retained bytes separately from
  the source object graphs held alive by reference; do not count shared buffers as copies.
- Exercise one, many and large collections with identical/overlapping/disjoint axes,
  repeated occurrences and long Asian sources. Work follows saved vector sizes, not the
  number of original trade rows or days expanded from a full calendar.

Initially a changed result causes a fresh collection from all inputs. The collector may
rebuild its compact unions/maps on that call; count that work honestly. This does not
rebuild the source trades' static encoding or payment preparation. No cache or selective
update algorithm is promised, and no reader is allowed to defer this work until a spill.

## Delivery and completion

Add the private collector/state, numerical and compatibility tests, and performance
budgets. Reuse or minimally extend the previous ticket's private report-view structure
so its selection/formatting path can consume the saved columns. Do not build a parallel
aggregate reporter or an extensible risk-measure registry.

Document the retained record, policies, refusal order and work boundary on the library
page, and update this packet's status/link rows selectively. State work counts and memory
before/after in the PR. Run check.ps1; review changes to existing goldens separately under
the project rule. Existing surface tests continue to pass with their current signatures.

Done means typed source results produce correct, immutable, inspectable aggregate risk
with saved totals and report views, without any pricing work. The next ticket then adds
typed handle-range input, `_AggregateResults`, the two-result-kind `_ReportRisk` boundary,
debug readback, worksheet examples and host publication/lifetime acceptance.

Cross-index hedge equivalence, FX, aggregate values/reserves, nested collections, new
valuation formulas, curve-tenor DV01, incremental collection, public function migration
and new time resolutions remain outside this PR.

## As built (#179)

Built as agreed on 11 October with the owner's three clarifications: results on the same index
object combine, and distinct index objects of one name are refused rather than numbered or merged,
unique index names at creation a later consideration outside this PR; D pays on 4 January 2028,
365 days from the valuation day and not from its observation, the explicit date in the fixture;
and the same risk measure combines within an index whatever the route, the saved nominal deltas
summed apart from the saved valuation-weighted deltas, 10 cleared lots and 9.5 discounted making 20
and 19.5, nothing discounted again. Curve objects are numbered by first appearance, the same curve
in two currencies two groups under one number. The library page is
[aggregate-results.md](../../library/trades/aggregate-results.md).

- **The record.** `AggregateResults` in `trades/aggregation.py`: the valuation day, the sources
  by reference in the order given, `IndexGroup`s and `RateGroup`s in first-appearance order with
  their occurrences' positions, the currencies in first-appearance order, and `ReportAxes` by day,
  month and year, the unions of the observation axes, of the payment axes and of both with every
  group's places on them. Every new array frozen; nothing of a source's preparation, market or
  curve copied.
- **The collector.** `aggregate_results(sources, counter)`: the membership snapshotted, nothing
  refused; each occurrence in order held to the first's valuation day, then to its index's first
  occurrence's history and price-vector objects, another `Market` wrapper over them accepted and a
  distinct index of a seen name refused; the groups' saved reference, day, month and year vectors
  summed onto the unions of their saved axes with Neumaier's compensation over the occurrences,
  every entry of an occurrence at once, the saved totals summed by Python's compensated sum, so
  that what cancels is kept in the vectors and the Total alike whatever the order;
  each new vector and total finite or the first coordinate that is not refused by its measure,
  group and coordinate, the vectors before the total; the report axes made and their places saved.
  Counted as `sources_collected`, `index_groups`, `rate_groups`, `entries_aligned`,
  `aggregate_reductions` and `report_coordinates`.
- **The view.** `aggregate_view(aggregate, risk, bucket)` returns the first ticket's `RiskView`,
  so `_ReportRisk`'s rectangle needs no new layout when the next ticket hands it the collector's
  handle: one column per index group under `HNG nominal_delta [LOT]` and `HNG delta [LOT]`, one
  per rate group under `curve_1 USD dv01 [USD per basis point]`, a collection with no curve one
  column of nothing per currency under `cleared USD dv01 [...]` over no day, and all three on the
  union with the index groups' pairs first and the rate groups after; a copy per column through
  the saved places and nothing else.
- **The figures.** The ticket's four sources and every expectation of its tables: `[A, B]`, the
  all-by-day view of `[A, B, C, D]` with the first payment HNG's -0.0095 and WTI's -0.0019
  together, the single-risk views on their own axes, the month and year buckets, `[B]` as itself
  through the same path, `[A, B, A]`, the reorder, HNG quoted 81 and the curve at 0.96 and 0.92.
  Beside them: two curves equal in every value two groups, one curve in dollars and in cents two
  groups under one number, the all-cleared collection, a fully paid source keeping its payment axis
  and rate group, and sums past the largest number refused by contract and in all.
- **The counts.** The same functions and numpy calls at one source and at twenty-four, eleven
  reductions and sixteen uniques for one index group and one rate group, none of the kernel's,
  the market's or the curve's; the peak within five arrays of eight bytes a stacked entry over the
  bytes retained, 8,240 bytes for one five-trade lastday source and 315,232 for twenty-four asian
  sources of 2,000 trades over 519 days, whose stacked days are 12,456; the retained bytes exactly
  the new arrays', 560 and 33,224 for one source of each; a view one zeros per column.
  2,648 Python tests, 314 host tests, 1,136 smoke formulas and 166
  lifetime checks on the final form, the sheet untouched.
- **Not done.** No worksheet function, handle kind, input-range binding or workbook formula; no
  aggregate mark, cash or reserves; no cross-index equivalence, FX, nested collection, curve-tenor
  DV01 or incremental collection; no identity registry. A DV01 bucket past the largest number
  cannot be made from finite sources on this calendar, a group's DV01 being bounded by the
  largest amount times two years of a basis point, so that refusal is pinned for the lots alone.
  No golden file exists to change.
- **Review of #179 at dc9f2d6.** One P2: the vectors were summed by `bincount`, sequentially,
  while the totals were summed with compensation, so ten thousand trillion lots bought, one
  bought and ten thousand trillion sold made a Total of one lot over vectors of nothing in one
  order and of one in another, and a third of a three-barrel lot missed the tolerance. Fixed on
  the branch: the vectors are summed over the occurrences with Neumaier's compensation, the
  flags down and the compensation added back where finite, as Python's sum does, and the
  regression tests pin the cancellation in every order, the three-barrel case and every column
  of every view summing to its Total.
