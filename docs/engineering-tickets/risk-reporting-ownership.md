# Give shared risk reporting rules one owner

**Status:** Agreed 17 October 2026 and built the same day from PR 194's head `58d63b5` on the branch `refactor/risk-report`; the pull request that carries this page is the record. Kept as the plan as it was: the report page, the module map and the code are maintained, not this page.
**Suggested PR title:** `refactor(trades): centralize shared risk reporting rules`
**Base:** Stack on [PR 194](https://github.com/gobbles404/catalyst/pull/194), branch `refactor/saved-results`, reviewed at `58d63b5`. Target that branch while it is open; use its accepted successor or main if it lands first. Record the actual base in the PR.
**Scope:** One behavior-preserving PR. Include this ticket in that PR as the plan; current behavior remains owned by the report page and code.

## Outcome

Give the risk choices, bucket choices, report-view record and column-label rules a shared home. A change to how an index, reporting lot or DV01 column is named should have one implementation to edit. Preserve the existing ways a single result and a collection select their saved data.

PR 194 separated the saved evaluation record from the calculation engine. Reporting now has this shape:

```text
saved result or collection -> select saved risk view -> format Excel spill
```

The worksheet function is already shared: `_ReportRisk(results, risk, bucket)` accepts either result kind and uses one Excel table formatter. The remaining ownership issue is inside the library: common reporting definitions and placement utilities live in `results.py`, while single-result and aggregate selection independently construct the same kinds of headings.

This PR gives those common rules one owner. It does not require one selection algorithm for both records.

## Current and proposed ownership

| Responsibility | Current | Proposed |
|---|---|---|
| Calculate, validate and save values and risk | Preparation, evaluation and aggregation | Unchanged |
| Define `Risk`, `Bucket`, `RiskView` and the existing `Period` alias | `trades/results.py` | `trades/risk_report.py` |
| Format delta and DV01 labels | Repeated in `risk_view` and `aggregate_view` | Shared functions in `risk_report.py`, called by both paths |
| Place a saved vector onto an existing report axis; provide empty output arrays | `results.py`: `placed`, `NO_DAYS`, `NOTHING` | Move unchanged to `risk_report.py` |
| Select a single result's saved vectors, axes, totals and refusal facts | `results.py` | Unchanged selection path |
| Select an aggregate's saved groups, vectors, axes, totals and refusal facts | `aggregation.py` | Unchanged selection path |
| Write Excel's context, headings, types, Total and dated rows | `excel/trades.py`: `_risk_table` | Unchanged |

Keep `TradeResults.report`, `risk_view`, `_day_view`, `_period_view` and `_saved` with the single-result record. Keep `AggregateResults.report`, `aggregate_view` and its source-specific helpers with the collection. These paths know which saved data they select; neither should discover or calculate risk while reporting.

## Shared module

Create `src/catalyst/trades/risk_report.py`. Move the existing definitions, type alias, placement function and empty arrays directly. Preserve enum values, record fields and types, and the empty arrays' dtypes and read-only flags. Both consumers must use the same shared definitions and constants.

Add two small label functions with this responsibility:

```python
def delta_labels(index: Index, reporting_lot: ReportingLot) -> tuple[str, str]:
    # Current nominal_delta label, then current delta label.
    ...


def dv01_label(group_label: str, currency: str) -> str:
    # Current curve/cleared label, currency and unit wording.
    ...
```

The delta helper owns selection of the current `index.name` and reporting lot's `name` as well as their formatting. Taking the existing domain records avoids leaving that policy repeated at two callers. It reads those fields only; it performs no index resolution or unit conversion. Keep the current short name in the output; switching to the human-readable description is a separate feature decision.

The DV01 helper receives the group label already selected by its caller, such as `curve_1` or `cleared`. Curve numbering, group membership, currency membership and their order remain with the existing source paths. The helper does not inspect a curve, infer a currency or allocate group numbers.

For an index named HNG, reporting lot named LOT and USD settlement, preserve these exact labels:

| Column | Label |
|---|---|
| Nominal delta | `HNG nominal_delta [LOT]` |
| Delta | `HNG delta [LOT]` |
| Bilateral DV01 on the first curve | `curve_1 USD dv01 [USD per basis point]` |
| Cleared DV01 | `cleared USD dv01 [USD per basis point]` |

`RiskView` remains the existing temporary view of dates, labels, saved totals and columns. No new saved reporting payload, generic report-input record, adapter hierarchy, registry or configuration system is needed.

## Dependencies

`risk_report.py` may import NumPy, the standard library and the index-definition types its label helper needs. It must not import preparation, evaluation, results, aggregation, markets or Excel, or perform market/fixing/discount-factor lookups.

```text
results.py        -> risk_report.py + its existing input records
aggregation.py    -> results.py for source records + risk_report.py + collection inputs
excel/trades.py   -> risk_report.py for report types + existing creators and result types
```

Update imports at their consumers, including tests. Aggregation still legitimately depends on `TradeResults` because it collects those records. Do not add compatibility re-exports, local imports to avoid cycles, runtime type checks or a second Excel dispatch mechanism.

In particular, do not implement single-result reporting by calling `aggregate_results([result])`. Collection performs grouping, reductions and axis construction; reading an already evaluated result needs none of that work.

## Behavior to preserve

The current report contract and executable examples remain authoritative. The following distinctions are especially important during this extraction:

| Boundary | Required behavior |
|---|---|
| Delta time axes | Day uses observation dates. Month and year use pricing-contract periods; do not rebuild them by bucketing the day rows. |
| DV01 time axes | Use payment day, month or year. Under `all`, select the already saved common axis and mappings. |
| Display start | Month/year starts at the saved result or collection's `as_of` period, with existing zero padding and cutoffs. A held result does not consult today's workbook clock. |
| Totals and units | Read saved scalars. Do not sum displayed rows to create Total, convert units, or add unlike index lots or curve/currency risks. |
| Grouping | Preserve index identity, curve-plus-currency grouping, first-appearance order and repeated source occurrences. |
| Column order under `all` | Each index's nominal/delta pair, in group order, then rate-group columns; preserve cleared currency columns when no curve valued any source. |
| Refusal order | Preserve the existing source-specific ordering. In an aggregate, check all nominal groups, then all discounted-delta groups, then rate groups. A loop in displayed column order is not equivalent. |
| Aggregate cancellation | Read the collection's saved early-risk facts after like-group summation. Do not reject a collection by applying each source's early-risk refusal first; offsetting exposures may cancel within a group. |
| Cleared DV01 | A single cleared result has zero Total and no dated rate axis. An entirely cleared collection has zero DV01 per currency; a mixed collection uses its actual rate groups. Preserve `all`'s existing zero columns. |
| Array ownership | A single daily individual-risk view can borrow its existing axis/vector with no NumPy allocation. An aggregate places each group's vector through saved mappings. Preserve both behaviors and all frozen saved state. |

Keep the worksheet signature, required selectors, accepted values, help text, handle kinds, spill layout, labels, row order and error wording unchanged. There is no new risk, bucket, filter, start-date option or reader in this PR. Values, reserves and debug readback are outside the change.

## Implementation and documentation

Use one PR with two reviewable commits:

1. Move the shared definitions, constants and placement utility; update imports and directly affected ownership descriptions. Preserve behavior.
2. Route both label-building paths through the shared label functions. Add focused coverage only where the existing report tests leave a gap.

Follow the documentation ownership established by PR 191. `docs/library/trades/report-risk.md` owns worksheet behavior; `docs/architecture.md` owns the module map; the code owns its implementation. Update those explanations and any directly affected implementation pointer in `docs/library/trades/kernel.md`, without creating another report specification or copying the full test inventory into prose. Once built, this ticket remains the historical plan.

Two narrow corrections are already established by the implementation and tests: the report page still locates `risk_view` in `evaluation.py` even though PR 194 moved it to `results.py`; its NG example also says there is no October row, whereas the current month report includes the October `as_of` row at zero. Correct those statements and retain the tested behavior. Leave unrelated historical narratives alone.

## Acceptance and validation

- Both source paths import the common reporting definitions and call the shared label functions. The report-label policy is no longer duplicated; moving files alone is insufficient.
- Existing expected outputs remain unchanged for all four risks and three buckets, for cleared and bilateral results and single-/multiple-index collections. Retain the current financial examples rather than regenerating expected answers.
- Preserve singleton-collection equivalence where already established, repeated occurrences, mixed cleared/bilateral groups, multi-curve/currency headings, and the existing ordering/refusal cases. Check label wording through both paths, not only the helper in isolation.
- Existing identity and allocation checks still demonstrate borrowed single-result daily arrays, copied aggregate columns, immutable saved state and readable held snapshots. No publication, grouping, reduction, sorting, axis discovery or market lookup is added to a report.
- Keep numeric work counts, NumPy call expectations and retained numeric-buffer sizes unchanged. Helper-call ledgers may reflect the explicit label functions. Measure and report any transient Python overhead; justify any necessary ceiling adjustment by that measured cause, without increasing broad slack or weakening per-size limits. Do not promise identical Python bookkeeping merely because the numerical work is unchanged.
- Run the relevant report, aggregation, help, seam and performance tests, the documentation-link checker and the repository's full `check.ps1`. Existing smoke, host and lifetime evidence should keep the same expectations; no workbook change is required for unchanged output.

Done means one maintained home for common report vocabulary and labels, with the same financial meaning, saved data, worksheet output and useful differences in how each source is read. Broader shared selection machinery requires its own demonstrated need and proposal.
