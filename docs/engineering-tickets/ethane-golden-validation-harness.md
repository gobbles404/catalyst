# Ethane financial validation and golden regression harness

**Status:** Proposed implementation plan; no harness implemented by this document.\
**Scale:** A small parent ticket delivered through focused PRs.\
**Starting evidence:** `ethane-trades.xlsx` and `ethane-trades-v2.xlsx`, inspected read-only on 29 September 2026.\
**Design authority:** [Trade valuation pipeline handoff](trade-valuation-pipeline/README.md).

## Outcome and scope

Establish independently reviewed answers for the supplied ethane examples, then prove that
the actual library reproduces them. Save the library's outputs as regression snapshots so
later changes are visible and separately reviewed. One trade and a batch must use the same
evaluation path, while preserving every trade occurrence and its economic contribution.
The public result is aggregate for the supplied collection. Per-trade and per-component
breakdowns in the financial reference explain the hand answers; they do not require a
production result row for each trade or payment.

Start with the first workbook's undiscounted amounts and price sensitivities, retaining its
attribution as independent reference evidence.
Capture the second workbook's payment/PV expectations now; activate those cases when a real
payment-valuation path exists. Discounting is a subsequent implementation phase and does not
expand the pipeline's initial scope. Two-index spreads are deferred. Oil
roll conventions, a general product framework, durable result storage and an Excel-driven
CI harness are outside this ticket.

The supplied calendars and product descriptions are fixture assumptions pending review.
Arithmetic reconciliation does not certify an exchange contract specification. These cases
use dated assessments and a declared monthly projection; they do not establish equivalence
to pricing a listed future from its own directly quoted market price.

Some workbook shapes use explicit date windows or a whole-quarter assessment average;
those capabilities are outside the current future v1 schema. Preserve all seven financial
references now, but connect each production case only when its terms have a supported
instrument representation. This validation plan does not authorize adding those fields or
silently translating them into a different supported trade.

## Four distinct references

| Reference | Question answered | How established |
|---|---|---|
| Frozen case inputs | What exactly are we evaluating? | Reviewed trade terms, conventions, dates, fixings and market data |
| Financial expectations | Is this economically the intended answer? | Hand-worked calculations and independently checked tables |
| Golden snapshots | Did observable library behavior change? | Saved outputs from the actual library on a fixed example |
| Consistency tests | Does the implementation obey general relationships? | One/batch, compression, aggregation and perturbation checks |

Workbook caches are supporting evidence for financial expectations. They are not library
goldens. A standalone prototype's outputs are not production-library goldens either.
Consistency tests supplement independent expected answers; agreement between two paths
sharing the same erroneous inputs is insufficient.

## What the two workbooks give us

Both contain seven trades, nine components and 183 exploded daily terms over 83 assessment
dates. Their valuation date is 16 December 2026. Prices are in CENT/GAL; one fixture lot is
1,000 barrels, or 42,000 gallons. December through March marks are 26.1, 25.8, 25.4 and 25.0.
These units and conversions must be explicit in the fixtures.

The baseline treats assessment dates strictly before 16 December as fixed; 16 December
itself remains projected (`Index!C28:C110`). December has 11 fixed assessments totaling
276.3 CENT/GAL, and T2 has two fixed days. Preserve this explicit cutoff as a fixture rule,
rather than assuming every assessment on the valuation date is already published.

| Trade | Shape | Signed lots | Agreed price, CENT/GAL | Independently calculated amount, USD |
|---|---|---:|---:|---:|
| T1 | December monthly average | +3 | 25.1 | 641.4545454545455 |
| T2 | 14–18 December average | +2 | 25.5 | 218.40 |
| T3 | 22 December single assessment | -5 | 26.0 | -210.00 |
| T4 | Whole Q1 average | +6 total | 24.8 | 1,445.9016393442623 |
| T5 | January–March monthly strip | +2 each month | 24.8 | 1,512.00 |
| T6 | 16–31 December balance-of-month | +1 | 26.0 | 42.00 |
| T7 | December monthly average | -3 | 25.4 | -263.45454545454544 |

The whole-quarter average has 61 assessments: 19 in January, 19 in February and 23 in
March. Its monthly exposures differ from the strip's equal two lots per month. This is a
particularly useful acceptance case: the same total lots and period do not imply the same
payoff.

| Baseline | Workbook saved result | Independent calculation |
|---|---:|---:|
| Undiscounted book amount, USD | 3,386.3016393442776 | 3,386.301639344262 |
| Version 2 book PV, USD | 3,354.4236134661983 | 3,354.423613466183 |

The independent calculation used primitive terms, supplied holiday assumptions, assessment
data, marks and curve anchors, rather than the workbook's calculated coefficient rows.
The largest component amount discrepancy was approximately USD 1.76e-11. This is useful
reconciliation evidence; a reviewed, checked-in derivation is still required in phase 1.

Version 2 explicitly describes these as the **paid versions** of the shapes (`Notes!A12`).
Its payment-date PV is a separate measure from cleared-futures price-difference P&L.
Its factor sensitivity is USD per unit discount factor, not rate DV01 (`Notes!A8`).

### Source map for extraction and review

| Data | Workbook location |
|---|---|
| Units and lot conversion | Both: `Index!A3:C8` |
| As-of, marks and holiday assumptions | Both: `Index!A10:C24` |
| Assessment dates and selected prices | Both: `Index!A27:F110` |
| Trade terms | v1: `Trades!A1:I8`; v2: `Trades!A1:J8` |
| Exploded daily terms | Both: `Exploded!A1:L184` |
| Constants, coefficients, amounts and quantity-equivalent deltas | Both: `Compressed!A1:R11` |
| Payment dates, discount factors, PV and PV sensitivities | v2: `Compressed!S1:AA11` |
| Curve anchors / daily curve grid | v2: `Curve!A4:B8` / `Curve!A11:B208` |
| Trade and book outputs | v1: `Value!A1:I9`; v2: `Value!A1:L9` |
| Payment-date aggregation and factor sensitivity | v2: `Value!A12:F20` |

### Limits of using Excel as the reference

- Assessment dates, exploded membership and denominators are hardcoded. Editing a trade
  period or holiday list does not regenerate the entire example.
- The two amount views share exploded inputs. Their agreement is an internal consistency
  check, not independent evidence of the correct schedule or contract interpretation.
- ID-based lookup/grouping cannot establish correct treatment of duplicate trade occurrences.
- Version 2 derives payment dates from the last assessment date plus a business-day lag.
  Do not silently replace that rule with contractual period end. The distinction needs a
  separate case when publication and payment calendars diverge.
- Its curve grid and payment-summary buckets are also hardcoded. Changed anchors or lags
  can fall outside the existing grid or summary. Its curve-start warning is informational.

All formulas had saved caches and none showed saved errors. The files were not recalculated
or modified during this inspection. On-disk evidence does not include unsaved Excel edits.
Freeze and review these examples; do not use the workbooks as automatic oracles for arbitrary
structural mutations.

The inspected on-disk sources have these SHA-256 fingerprints:

```text
ethane-trades.xlsx     089c47e4d91ad6821420f49cafbcde7f25dfb4dcf6f8e41a10371b2dd3ce3cd2
ethane-trades-v2.xlsx  094059ed3f2ca6f738a485097efc4369efaf6cdb2c2f5d110d80c566a20e2e46
```

## Phase 1: freeze the inputs and write the financial references

Archive exact source workbook bytes in a versioned test-evidence location, recording filename,
SHA-256, capture date and a cell-to-field map. Extract declared inputs once into readable JSON.
Record known-fixing status explicitly, including the treatment of the valuation date; do not
infer it from the machine clock. Capture all calendar dates and curve anchors used by a case.
Normal tests must require neither Excel, the user's Downloads folder nor workbook caches.

Keep immutable executed terms separate from market marks and fixing state. Give every input
row a stable occurrence ordinal in addition to its user-facing trade ID. Record strip quantity
allocation explicitly. Use stable case identities and version the fixture schema.

Write a small worked document and checked-in expected tables from primitive terms. For example:

```text
amount = signed lots × 42,000 GAL/lot × 0.01 USD/CENT
         × (weighted assessment price − agreed price)
```

The derivation must show the full contractual denominator, fixed versus projected contributions,
sign and unit conversion. Fixed observations retain their share of that denominator; remaining
weights are not renormalized. The reference must not call the production encoder, binder or
compression code. Manually reviewed expected numbers and schedule tables should be sufficient
for this small suite; do not build a second general pricing engine.

Store input/reference provenance independently from saved library output. A proposed layout is:

```text
tests/validation/ethane/
  sources/                 # original workbooks and provenance manifest
  worked-examples.md
  expected.json            # independent economic expectations
  test_ethane_validation.py
tests/regression/
  inputs/                  # normalized fixed examples, shared by validation
  golden/                  # approved actual-library output snapshots only
  cases.py                 # named case registry and library adapters
  snapshot.py              # deterministic projection, serialization and comparison
  test_regression.py
tools/regression/
  generate.py              # candidate generation only
  check_changes.py         # full-PR baseline/input governance
```

The economic reviewer signs off trade meanings, quantity allocation, assessment membership,
known-fixing selection, units and expected answers before first production snapshots are accepted.
Unverified exchange conventions remain visibly labeled as fixture assumptions.

## Phase 2: build the small regression mechanism

There is no `tests/regression` harness today. Reuse pytest and the current Windows CI rather
than introducing another test runner. The repository already pins Python 3.13.13 through
`.python-version`, uses `uv sync --locked`, and runs on Windows 2022. The project Python
constraint permits other 3.13 patch versions, so generation needs its own explicit runtime check.

### Case execution and output contract

A registry maps a stable case ID to fixed inputs and a call through actual library APIs.
Both pytest and snapshot generation use that same adapter. The adapter must not implement
pricing mathematics or substitute expected values when a capability is missing.

For end-to-end cases, feed terms through the library-owned instrument definition, optional
template and `CreateTrades` (resolution and static encoding), then call `PrepareTrades`
with explicit history, `EvaluateTrades` with a compatible market, and the pure result readers.
Supplying precomputed workbook coefficients would bypass precisely the schedule and binding
behavior we need to validate. A separately named kernel
case may deliberately start at arrays, with that limited scope stated explicitly.

Snapshot only declared observable outputs:

- Measure name, currency and units; as-of date and pricing route.
- Aggregate amounts and labeled sensitivities for the supplied collection, on identified axes.
- Declared reader rows and labels, and retained source occurrence/payment facts if exposed.
- Numeric array shapes and dtypes where part of the output contract.

The complete pipeline target is the route's mark/cash pair plus delta and DV01, with the
meanings in [the result contract](trade-valuation-pipeline/05-results.md). An intermediate
undiscounted amount case must be labeled as such; it does not prove that complete target.
Unavailable measures cannot be replaced with zeros, and readers cannot calculate them later.
The workbook's discount-factor sensitivity is not a substitute for DV01.

Preserve duplicate source occurrences and any declared source-row order. The aggregate value
and aligned risk must be invariant within declared tolerances to a permutation of the same
inputs; risk/reader axes keep their defined ordering. Canonicalize mapping keys without sorting away meaningful output
order. Exclude process handles, addresses, timestamps and timings. Do not
snapshot every private intermediate array, which would unnecessarily freeze storage choices.
Reference coefficient tables and daily terms remain useful independent evidence without
requiring the production library to expose or retain the same dense/per-trade representation.

Record the case-input digest, producing revision, runtime, dependency versions and lockfile
digest as provenance alongside the output. Compare the input digest to detect input changes;
do not compare today's Git revision to the producing revision as an output assertion.

### Comparison and candidate generation

- Pytest is compare-only. A missing expected golden, non-finite numeric output, changed unit,
  missing/extra row or changed value fails visibly. No automatic recording or baseline fallback.
- Emit deterministic JSON without decimal rounding. Start with exact serialized numeric
  comparison on the pinned reference platform. Verify repeatability in fresh processes before
  accepting this policy; any necessary exception must be narrow, explicit and separately reviewed.
- Financial validation, independent daily-reference comparisons and singleton/batch checks
  have their own declared numerical tolerances. A candidate for these small USD amount fixtures is absolute USD 1e-8 with zero
  relative tolerance, subject to review. This is not a universal risk or monetary tolerance.
- Report case ID, field/index, expected and actual values, and numeric difference. Provide
  readable structural diffs for row, shape, label and unit changes.
- The generator verifies Windows, exact Python 3.13.13 and the locked environment. It accepts
  explicit case selections and writes candidates into an ignored directory such as
  `profiles/regression-candidates/`. It does not silently overwrite approved snapshots.
- Promote candidates only as an explicit reviewed baseline change. Changes to comparator
  tolerances or serialization rules count as code changes, never as baseline-only housekeeping.

Use small mechanical tests for the comparator, generator guards and governance gate. A fixture
used to test serialization is clearly a harness test, not evidence that ethane pricing exists.
Delivery 2 runs those mechanical tests. Activate ethane regression collection and mandatory
case-completeness checks together in delivery 3, when the first actual-library adapters exist.

## Phase 3: connect the first actual-library cases

The earlier NG trade-capture prototype was removed by the pipeline cleanup. Standalone
numerical experiments remain as evidence; the general `CreateTrades`/`PrepareTrades`/
`EvaluateTrades` pipeline and a production ethane averaging path are not implemented.
Deliver the relevant slice under the current pipeline handoff, then connect it here.
Infrastructure and reviewed references can land first, but the ethane milestone is complete
only when real library outputs
pass both financial validation and regression checks. Do not disguise deferred adapters with
passing placeholders or a silently empty case registry.

Declare which cases each delivery activates and which await supported product capabilities.
The first connected delivery must have a nonempty required case set; missing active cases
fail. A supported subset is an incremental delivery, not completion of the seven-case suite.
Daily reference tables and independently evaluated singleton collections provide diagnostics;
the batch tick path need not calculate or store individual trade amounts.

| Case or check | Required proof |
|---|---|
| Seven-trade workbook v1 baseline, when all shapes are supported | Aggregate amount/risk reconcile to the nine-component independent reference; units and source occurrence/payment facts are correct |
| Each trade alone and the complete book | Separately evaluate singleton collections through the same API/path; their amounts and aligned risks sum to the aggregate batch within declared tolerance |
| Whole quarter versus monthly strip | 61-day denominator versus independent monthly denominators |
| Partial fixing state | Known contribution retained; fixed dates carry no forward-price sensitivity |
| Equal/opposite monthly exposures at different agreed prices | T1 + T7 retain USD 378 with zero amount delta |
| December mark +0.10 CENT/GAL | Independent predicted book amount change is USD -117.60 |
| Daily reference and compressed evaluation | Aggregate evaluation matches independent daily arithmetic without losing `fixed_leg` or `floating_leg_set` contributions; no second production path is required |
| Duplicate occurrence and reordered input rows | Each duplicate contributes again; aggregate amounts/risks agree within declared tolerances after reordering; retained source facts follow their declared order |
| Fully fixed / zero-live case | Correct amount and zero commodity sensitivity without fetching unused live prices; no particular private array shape is mandated |
| Coverage and identity failures | Missing required fixing or incompatible/reordered axis cannot silently misprice |

The workbook-derived baseline and bump can have actual library goldens. Broad invariants
belong in ordinary tests; avoid generating a snapshot for every property-test permutation.
Synthetic cases cover gaps the workbooks cannot prove, including valid zero fixings and
negative prices, fixing corrections, and a fixing arrival that changes binding while leaving
static trades unchanged. Encode the relevant policy and expected result explicitly.
Test explicit preparation reuse as well: a price-only tick evaluates the retained preparation
without rebuilding static trades or folding history; a fixing/as-of change requires new
preparation. Incompatible history or market layout fails at evaluation. These are observable
dependency/work checks, not a requirement for a private cache or particular storage layout.

Keep sensitivity units distinct: USD per CENT/GAL is different from quantity-equivalent GAL.
A one-cent bump is +1.0 in the source price units, not +0.01. Where exposed, check the analytic
slope against independent bump/reprice results as well as the saved baseline.

### Subsequent phase: version 2 payments and PV

Activate after a real payment-date valuation path is available. Preserve each component's
date through amount calculation and apply its own discount factor before aggregating PV.
Use the workbook's stated linear interpolation in discount factors and explicit curve anchors;
do not introduce an unstated interest-rate convention.

Required cases include the v2 aggregate baseline, payment-date ownership, aggregate PV price
sensitivities and USD-per-unit-DF sensitivities where that measure is supported. Check
component/trade PV hand answers through separately evaluated compatible subcollections,
without requiring those values in the full batch result. T1/T7 demonstrate why amount
compression must preserve payment ownership: nominal net is USD 378 with zero amount delta,
but their different dates produce PV USD 377.20085454545455 and a residual December PV slope
of USD 0.5145 per CENT/GAL. The independent predicted December +0.10 CENT/GAL book PV change
is USD -117.50053. These bump predictions were calculated independently, not obtained by
recalculating the source workbooks.

Add independently worked cases for a payment date outside curve coverage, a changed payment
lag and differing assessment/payment calendars. Do not use the workbooks' fixed summary
buckets or grid as their oracle. This fixture's PV/DF checks do not complete the pipeline's
rate DV01 requirement. Rate-bump conventions and independent DV01 expectations need their
own reviewed cases before the full bilateral result can be published. Payment mark/cash
transitions also need independent before/on/after-payment cases under the agreed model;
the workbook baseline alone does not establish that lifecycle.

## Review policy: two separately reviewed PRs

For existing cases, follow the user's policy:

1. **PR A changes implementation or inputs.** Existing approved goldens stay untouched.
   The comparison exposes the difference for investigation and review.
2. **PR B accepts the baseline, when appropriate.** Generate candidates against A's exact
   reviewed revision, review the outputs separately, and require the combined tree to pass.

If the new answer is a bug, fix A and retain the old baseline. If both outputs and the protected
input digest are unchanged, there is no baseline PR. An input change that leaves amounts
unchanged can still require a separately reviewed provenance-only baseline update in B.
A genuinely new case may include its first golden alongside its
implementation/input changes, provided existing cases and snapshots remain unchanged and pass.

Codify that new-case exception in `CLAUDE.md` and the related policy docs during harness
implementation; the present blanket wording does not express it. This plan adopts the user's
explicit instruction and does not require another permission step to propose the alignment.

The governance gate examines the entire PR diff from its merge base, not the last commit.
An existing golden's modification, deletion or rename cannot accompany changes to production
code, existing case inputs/source workbooks, adapters, comparator/serializer policy or relevant
dependencies. Changing an existing case through shared fixtures counts as changing its inputs.
Stable case identity and deletion/rename checks prevent disguising an update as a new case.
Protect case registration and test collection too: removing a failing case is not a baseline fix.

**Integration decision before enforcing required CI:** ordinary sequential merges cannot
simultaneously preserve strict old-baseline checks, two separate baseline/code PRs and an
always-green main branch for an intentional output change. Specify either a supported workflow
that integrates the two separately reviewed revisions together, or an explicitly approved
temporary-red window while A then B land. Validate B against the exact approved code and input
revisions. Do not resolve this by regenerating in CI, suppressing the mismatch or using `xfail`.
This ticket proposes policy; it does not authorize a merge or bypass of required checks.

## Delivery and completion criteria

| Delivery | Reviewable result |
|---|---|
| 1. Financial references | Frozen sources, normalized inputs, source map, worked derivations, reviewed expected amounts and staged PV expectations |
| 2. Harness foundation | Serializer/comparator, candidate generator, governance tests, CI wiring and clarified new-case policy |
| 3. First connected suite | Actual ethane pipeline adapter, independent validation, first approved new goldens and one/batch/compression tests |
| 4. Payment extension | Actual payment/PV adapter and v2 acceptance/regression cases after that capability exists |

Each delivery may be a focused PR. Production pricing work may need further slices in the
parent pipeline ticket; this is not a request to fit an entire trade engine into one harness PR.

Completion of the first connected suite requires:

- Independent expectations and actual library results agree under reviewed, unit-specific tolerances.
- Fresh-process candidate generation is deterministic on the reference environment.
- An unchanged comparison passes without modifying inputs or expected outputs.
- Deliberate amount, label, unit, ordering and missing-row regressions fail with useful diffs.
- Missing snapshots and missing/duplicate case registration fail; tests cannot quietly stop covering a case.
- Governance tests reject mixed changes to existing code/input and baselines, including rename
  evasions, and permit the genuine new-case exception.
- Aggregate-versus-summed-singletons, duplicate-occurrence, zero-live and daily-reference
  agreement are demonstrated without requiring per-trade tick outputs.
- Normal CI uses versioned files and actual library calls, with no Excel or Downloads dependency.
- Existing repository checks pass. Pricing/cache work includes `WorkCounter` budget tests;
  timings and machine-specific performance numbers stay outside the numerical goldens.

The immediate next implementation is delivery 1: make the seven examples and their economic
meaning reviewable in the repository. That gives both the engine work and the regression
mechanism a concrete contract to build toward.
