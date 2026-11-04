# Give saved evaluation results a clear owner

**Status:** Agreed 17 October 2026 and built the same day from PR 193's head `5474645` on the branch `refactor/saved-results`; the pull request that carries this page is the record. Kept as the plan as it was: the module map in [docs/architecture.md](../architecture.md) and the code are maintained, not this page.
**Suggested PR title:** `refactor(trades): separate saved results from evaluation`
**Scope:** One behavior-preserving PR after documentation ownership and link checking.

## Purpose and recommendation

Make it possible to understand what evaluation saves without reading the calculation engine. Evaluation should produce a defined result record; aggregation and readers should consume that record without depending on the module that calculates it.

The current result already retains the economic information we need. The concrete problems are that its definition and reporting helpers live in `evaluation.py`, and its two constructors each supply 32 positional arguments. Several adjacent arguments have identical types. A reviewer must count positions to verify that each calculated vector lands in the intended field.

**Recommendation: keep the saved data structure flat in this PR.** Extract its definition and existing saved-view selection into `trades/results.py`, and construct it with named, keyword-only fields. Preserve the numerical arrays, their ownership and every external result. The side-by-side comparison below deliberately shows the same data: the proposed improvement is an explicit boundary and safer construction, not another calculation or a new storage hierarchy.

## Baseline and placement

The inspected baseline is `bd89df4` on [PR 193](https://github.com/gobbles404/catalyst/pull/193), the fresh documentation-link checker above [PR 191](https://github.com/gobbles404/catalyst/pull/191). PR 192 is the closed prototype; do not branch from it. PR 193 still has a review correction outstanding in its separate decision-number test. Stack this implementation on PR 193's accepted head, or current `main` once the documentation PRs merge, and record the actual base in the PR.

Include this ticket in the implementation PR. The current/proposed tables below describe this refactor at its starting point; once built, keep them as the historical plan and maintain the current module map and owning code instead.

The next, separate consolidation slice can address shared risk-report selection across a single result and an aggregate. This PR must stand on its own without requiring that later work.

## Current and proposed organization

| Responsibility | Current | Proposed |
|---|---|---|
| Validate evaluation inputs; read live prices and discount factors; calculate values and risk | `evaluation.py` | `evaluation.py`, unchanged arithmetic and failure order |
| Define the saved evaluation snapshot | `evaluation.py`: `TradeResults` | `results.py`: the same `TradeResults` fields and types |
| Construct the snapshot | Two long positional calls | Two explicit keyword calls; record is keyword-only |
| Select a single result's saved risk views | Helpers beside the calculation | Existing helpers beside the result in `results.py`, moved without redesign |
| Collect compatible saved results | `aggregation.py`, importing result/report types from evaluation | `aggregation.py`, importing those types from results; grouping and summation unchanged |
| Present values, reserves, risk and debug contents | Excel modules | Same functions and spills; imports updated |

No new worksheet function or handle is introduced. `_EvaluateTrades` still creates one result for the supplied batch, whether that batch contains one trade or many.

## Current and proposed saved structures, side by side

These rows group fields for explanation only. They do not propose nested records. Together they account for all 32 current fields.

| Part of the snapshot | Current: `evaluation.TradeResults` | Proposed: `results.TradeResults` |
|---|---|---|
| Retained evaluation inputs | `prepared`, `market`, `curve` | `prepared`, `market`, `curve` |
| Interpretation | `route`, `currency`, `as_of` | `route`, `currency`, `as_of` |
| Aggregate values | `mark`, `cash` | `mark`, `cash` |
| Live contribution and contract axis | `dated_live_contribution`, `contracts` | `dated_live_contribution`, `contracts` |
| Nominal contract risk | `price_sensitivity`, `lot_delta`, `lot_delta_total` | `price_sensitivity`, `lot_delta`, `lot_delta_total` |
| Units | `price_sensitivity_unit`, `lot_unit` | `price_sensitivity_unit`, `lot_unit` |
| Valuation-adjusted contract risk | `discounted_price_sensitivity`, `discounted_lot_delta`, `discounted_lot_delta_total` | `discounted_price_sensitivity`, `discounted_lot_delta`, `discounted_lot_delta_total` |
| Valuation-adjusted dated delta | `discounted_daily_lots`, `discounted_monthly_lots`, `discounted_yearly_lots` | `discounted_daily_lots`, `discounted_monthly_lots`, `discounted_yearly_lots` |
| Rate risk | `dv01`, `dv01_by_day`, `dv01_by_month`, `dv01_by_year` | `dv01`, `dv01_by_day`, `dv01_by_month`, `dv01_by_year` |
| Bilateral payment-group facts | `payment_amount`, `payment_factor`, `npv_by_group`, `dv01_by_group` | `payment_amount`, `payment_factor`, `npv_by_group`, `dv01_by_group` |
| Booked reserves | `reserves` | `reserves` |
| Saved facts used to refuse an invalid report range | `early_delta`, `early_dv01` | `early_delta`, `early_dv01` |

Nominal daily/monthly/yearly vectors remain accessible through `prepared`. Dates, mappings and payment-group ownership remain on preparation/encoding. The result does not need another copy of those arrays merely to appear self-contained.

The construction change is illustrated below; both examples omit unrelated fields for readability:

```python
# Current: meaning depends on the declaration's position.
TradeResults(prepared, market, route, currency, as_of, mark, cash, ...)

# Proposed: each saved value names its destination.
TradeResults(
    prepared=prepared,
    market=market,
    route=route,
    currency=currency,
    as_of=as_of,
    mark=mark,
    cash=cash,
    # Remaining fields also supplied by name.
)
```

Use `@dataclass(frozen=True, slots=True, kw_only=True)`. Keep field names, types and declaration order; update internal construction sites directly. Do not add compatibility properties, a dictionary payload or a second constructor that hides the named assignments.

## What is owned, and what is shared

The same ownership applies before and after this PR.

| Saved information | Owner / relationship |
|---|---|
| Preparation, market and bilateral curve | Retain the exact input objects. Identity is part of validation and collection, not just equal values. |
| Contract references and booked reserves | Encoding owns them; results retain references. |
| Nominal contract sensitivities, lots, totals and dated lots | Preparation computes them. Results reuse them; a quote tick does not rebuild them. |
| Live contributions | Evaluation creates one value per live slot. This is exposure times quote, not the slot's allocated NPV. |
| Cleared valuation-adjusted delta | The nominal arrays themselves, shared by identity. No extra numeric buffers. |
| Bilateral discounted risk, payment amounts/factors, group NPVs and DV01 vectors | Evaluation computes and freezes them. Keep the current axes, array shapes and reduction order. |
| Collected risk | `AggregateResults` retains its source occurrences and owns the collection's sums/axes. That record and its algorithms are unchanged. |
| `RiskView` | Temporary report content, not another saved result. Selection may borrow an array or place saved values into an output array. It does not reprice or recompute totals. |

Preserve duplicate occurrences in a collection. Preserve results held across later ticks, including their original market/curve references and saved arrays. No mutation of an earlier snapshot is permitted.

## Cleared and bilateral meaning stays explicit

| Fact | Cleared | Bilateral |
|---|---|---|
| `mark` | Undiscounted value of unpaid groups | Sum of unpaid group NPVs |
| `cash` | Preparation's paid amount | Preparation's paid amount |
| Nominal delta | Live lots | Live lots |
| Valuation-adjusted delta | Same arrays and total as nominal delta | Live lots weighted by their payment factors before aggregation |
| `dv01` | Zero | Saved analytic DV01 total |
| Curve, four payment-group arrays and three dated DV01 arrays | All `None` | All populated, including when all payments are paid |

Paid bilateral groups retain the existing conventions: factor one, group NPV zero and group DV01 zero; paid amounts contribute to cash. Cleared dated DV01 has no saved payment axis. Do not replace `None` with fabricated zero arrays.

Eight fields are currently nullable together. A single optional bilateral payload could express that relationship more strongly. It is a reasonable future design choice, but the current factory already supplies the fields consistently. This ticket does not claim an invalid-state bug or introduce nested value/risk/payment records solely for symmetry. Named construction makes the current relationship inspectable without changing every consumer's field access or adding wrapper objects on each evaluation.

## Module boundary and imports

Move `TradeResults`, its `report()` and `codes()` methods, and the existing result-view implementation together. Moving only the class would leave `report()` reaching back into evaluation.

The extraction includes `Risk`, `Bucket`, `RiskView`, `NO_DAYS`, `NOTHING`, `Period`, `risk_view`, `_day_view`, `_period_view`, `_saved` and `placed`. These retain their behavior. This is a relocation of the existing selection path, not a unification of single-result and aggregate reporting.

The dependency direction should be:

```text
results.py       -> preparation / encoding / domain types
evaluation.py    -> results.py + evaluation inputs
aggregation.py   -> results.py + its existing collection dependencies
Excel creators   -> evaluation.py
Excel readers    -> results.py / aggregation.py
```

`results.py` must not import evaluation, aggregation or Excel. It must not call live-price, fixing or discount-factor lookup methods. Constructors assign already-computed facts; they do not validate markets again, calculate totals, sort axes or copy arrays.

Update consumers to import from the owning module directly, including `trades/aggregation.py`, `excel/bridge.py`, `excel/trades.py`, `excel/utilities.py` and affected tests. Preserve the class name, handle-kind registration and `trade_results` handle text. Do not introduce local-import workarounds or compatibility re-exports to keep the old dependency.

## Implementation and documentation

Keep this to one PR with two reviewable commits:

1. Extract the record and existing selection helpers, update imports and the affected ownership references. Preserve behavior verbatim.
2. Make construction keyword-only and name every field at both evaluation paths and any direct test construction sites. Add focused ownership coverage only where existing tests leave a gap.

Follow the documentation ownership established by PR 191. Update the current module map in `docs/architecture.md` and the relevant implementation explanation in `docs/library/trades/kernel.md`. Explain which state is shared and which evaluation creates; do not reproduce this ticket's full field inventory in several pages. The class owns field meanings, the architecture page owns the rebuild/reuse overview, and tests own exact expectations. Fix links affected by moved symbols/files. Leave unrelated historical narratives alone.

Do not change report layouts, worksheet signatures/help, instrument fields, schedules, payment rules, discounting or DV01 conventions, aggregate grouping policy, error wording/order, finite checks, workbook examples or release packaging. Do not add new caches, selective tick evaluation, per-trade expansion, framework abstractions or a new dependency.

## Acceptance and evidence

- A reader can find the saved result definition without entering the calculation implementation. Consumers that only need saved results no longer depend on the evaluation module; the worksheet creator still imports the calculation entry point.
- Both calculation paths visibly assign each field by name. Existing numerical answers, refusals, labels, row order and report totals remain unchanged.
- Preserve frozen records and read-only arrays. Existing aliasing tests must still prove object identity for borrowed arrays and cleared nominal/discounted vectors, not merely numerical equality.
- Preserve the distinct axes: live-slot contributions; pricing-contract risk; observation-day delta; pricing-contract month/year delta; payment-day/month/year DV01. No axes are rebuilt in the result constructor or reader.
- Existing hand-priced cleared/bilateral, paid/unpaid, fixing/tick/curve, collection, overflow and report tests remain the reference. Retain original expectations; do not regenerate expected values to make the refactor pass.
- Retained numeric-buffer sizes and work budgets remain unchanged. No preparation, quote/factor read, reduction or numeric-buffer allocation is added to either evaluation path. Existing transient report placement allocations are allowed exactly as before.
- Handle publication, retained-source lifetime and held-snapshot behavior remain unchanged. Run the normal repository gate, including host, smoke and lifetime checks, plus the accepted documentation-link checks.
- The PR describes the dependency change and reports validation. If the move reveals an economic or reporting discrepancy, record it separately rather than quietly fixing it in this refactor.

Done means a clearer saved-result boundary and construction that can be reviewed by field name, with the same numbers, arrays and worksheet behavior.
