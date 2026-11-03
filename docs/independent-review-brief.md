# Catalyst: independent valuation and performance review brief

Original assessment: 27 September 2026, code inspected at `6fc6373`. Review scope reconciled with the agreed pipeline on 3 October 2026. Measurements and test counts below remain historical; this revision did not refresh them. Capture the exact commit and working changes again when beginning the review.

## Reviewer profile

Seek a senior quantitative software/performance engineer who has shipped commodity derivatives valuation using Python/NumPy and understands .NET, pythonnet, Excel-DNA and Excel recalculation. The review should be independent of the earlier Priceratops implementation and the present design.

If one person does not cover both areas, pair a commodity/rates valuation specialist with a Python/.NET/Excel performance engineer. The first reviews cash, discounting and risk semantics; the second reviews data movement, repeated work, batching and ownership. A general code review alone is insufficient for either conclusion.

## Objective

Assess whether Catalyst's static-trade and array-based market design supports correct, efficient commodity valuation from Excel. Distinguish implemented guarantees, historical measurements and proposed behavior. Reproduce the current baseline before recommending changes. Prioritize small, demonstrated improvements over a framework rewrite.

The [trade-valuation pipeline](engineering-tickets/trade-valuation-pipeline/README.md) is the current design contract. The [contract survey](futures-trade-field-review.md) preserves supporting exchange research; its former field schema and implementation sequence are superseded. Review implementation against the pipeline and identify remaining decisions explicitly rather than treating historical prototypes as the required API.

The agreed boundaries are:

| Boundary | Review contract |
|---|---|
| Instrument definitions and templates | Library-approved exact field names/types; instrument first in template creation; template/ticket fields disjoint even for equal values; unknown fields and duplicate headers fail |
| CreateTrades | Static resolution and encoding using Index conventions/specifications; no history, valuation date or current prices |
| PrepareTrades | Explicit history input; retained fixed/set contributions, compatible aggregate live exposure and dependency identity |
| EvaluateTrades | Compatible current market; aggregate valuation and risk for the supplied collection, with payment groups preserved when treatment differs |
| Readers | Pure views of completed results; no preparation or pricing |

One trade and many trades use the same path; duplicate occurrences each contribute. Individual trade results are not required on every tick. Current prices and historical fixings do not mutate executed terms. The initial real NG example covers open-contract economic marks; physical delivery processing and margining are outside v1. The [result contract](engineering-tickets/trade-valuation-pipeline/05-results.md) distinguishes route-specific mark/cash from actual bank reconciliation. Instrument selection without a template, Index input placement and the bilateral rates interface remain open decisions in the packet.

## Historical evidence from the original assessment

| Area | Evidence at the inspected revision | Limit |
|---|---|---|
| Market construction | Wrapper retains history, a price vector and an offset; avoids a daily expanded price array | Does not prove full market-feed update is constant work |
| Price snapshot | One owned float64 copy, 8 bytes per price plus overhead; allocation budgets exist | Updating a supplied vector still copies its values |
| Structure and ownership | Calendar/history references reused; creator reuse and handle release tested in Excel | Not proof of selective instrument recalculation or flat whole-process memory |
| Seam performance | Counts, copy/allocation checks, timing and profiling tools for Python, host and Excel | Most workloads are probes, not trade valuation |
| Pricing work budgets | Test-only cold/warm `quantities * prices` example | Did not establish a production trade/payment/risk evaluator |

Sources: [market budget](../tests/performance/test_seam_budgets.py), [price-vector allocation](../tests/performance/test_seam_allocation.py), [pricing stand-in](../tests/performance/test_work_budgets.py), [ownership tests and open issues](seam/handles.md).

The stored timing baseline is revision `aaa5259`, measured September 11 local time / September 12 UTC. It predates the current code. For a 10,000-row `RowSums` probe, milliseconds per Excel recalculation were:

| Arrangement | Full recalculation | One input-cell edit |
|---|---:|---:|
| One formula per row | 226.91 | 1.17 |
| Ten arrays of 1,000 rows | 5.91 | 1.92 |
| One array of 10,000 rows | 7.93 | 8.85 |

This supports batching and the need to examine batch size/dependency scope. It does not establish current pricing throughput. A single-cell edit in a probe is not necessarily a market tick feeding many positions. [Timing baseline and boundaries](seam/baseline.md).

The repository check passed during the original 27 September assessment: 1,365 Python tests, 190 host tests, 337 Excel smoke formulas and 26 lifetime checks, plus format/lint/types. These are historical counts at the original review boundary, not the current suite or a portfolio latency target. No new timing baseline was collected for this brief. Re-run the current checks and inventory available numerical specimens and budgets before making a present-day performance claim.

## Questions the review must answer

### 1. Economic and rates boundary

- Are trade terms truly static while market/settlement state changes separately?
- Do route-specific mark/cash results have the meanings defined by the pipeline? In the cleared model, are economic P&L buckets kept distinct from actual variation-margin cash or asset NPV?
- Do actual payment dates, currencies and settlement/collateral agreements select the correct valuation treatment?
- How are curve start, valuation date and coverage checked? What happens at a day roll or out-of-range payment?
- Are fixed observations, fixed-but-unpaid amounts and modeled settled payments kept distinct? Does an unpaid bilateral amount retain discount risk after losing commodity-price risk?
- Is risk to an independently traded futures index distinguished from risk through a reconstructed benchmark curve?
- Are rate bumps defined? Supplied discount-factor sensitivity must not be mislabeled as calibrated rate-instrument DV01.

Begin with the [NG worked example](engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md): opposite signs, two contracts and a duplicate occurrence. Compare the aggregate answer with the sum of separate compatible singleton evaluations. The separately labeled toy lifecycle case covers fixing/payment transitions; it must not be mistaken for a supported physical-NG final cash payment.

Broaden only with the corresponding implementation slice: an actual monthly strip, an averaging future, then bilateral payments/rates when specified. Include opposite signed payments on different dates and offsetting trades with different execution prices. Listed basis research is useful for a later product; two-index basis swaps and exact-date/CFD trade inputs are deferred. No review conclusion should require physical delivery or margining to complete the initial path.

### 2. Repeated work and invalidation

Measure first construction/calculation, unchanged repeat, one commodity-price update, fixing arrival/correction, valuation-date roll, one trade edit and reader-only calls. Add rate-input changes when that slice exists. State exactly what each event invalidates and why.

Require zero creation, schedule regeneration and historical-fixing folding on a compatible price-only tick. History/as-of changes rebuild the preparation from the supplied history; the explicit prepared handle retains that work between ticks. Evaluation must reject incompatible history or market layout rather than silently prepare again. Readers perform no valuation. The initial design does not require a private history cache or selective recalculation framework.

Determine whether calendars, unit factors, contract selections and dependency mappings are rebuilt unnecessarily. Inspect repeated traversals for value, cash, delta and rate sensitivity. Test curve-grid changes as well as factor changes. Distinguish market-input gathering reuse from result caching.

Count hashed/scanned/copied elements and bytes. A counter reporting one hash can conceal an O(N) scan or copy. Determine whether selective recomputation actually improves the workload compared with a simple vectorized batch; do not assume a dependency framework is necessary.

### 3. Representation and scale

Use one-trade correctness cases and portfolio sweeps at 1,000, 5,000 and 10,000 trades; add a larger stress size after observing scaling. Vary unique contracts, repeated definitions, strip constituents, observation counts, currencies, payment dates and output cells independently.

Compare compact indexed arrays/grouped reductions with dense or sparse matrices where plausible. Quantify temporary rows and bytes. Preserve duplicate trade occurrences, executed-price contributions, payment timing, units and market identities in retained source/prepared data. Compression must respect compatible payment/currency/treatment groups before aggregation; it need not retain or publish a priced output row per trade. Explain which work must scale with source trades and which can scale with unique live inputs or payment groups. Delivery eligibility and operational account netting are not first-path output requirements.

### 4. Excel and host path

Attribute cost to Excel dependency calculation, argument hashing/comparison, .NET/Python transfers and GIL crossings, preparation, commodity/discount gathers, arithmetic, aggregation and worksheet publication.

Compare single-trade formulas, practical batches and one large batch under both broad updates and sparse edits. Include the time until results are available on the sheet. Separate cold startup from warm recalculation. Mark clearly whether clocks include COM control overhead, input construction, output publication and Excel itself.

### 5. Memory and long-run behavior

Stress thousands of updates, growing/shrinking batches, failed construction, duplicate creators, multiple workbooks and workbook closure. Measure temporary peak allocation, live retained objects, Python and .NET memory, and process memory where practicable. Handle-count plateaus alone are not proof of flat process memory.

## Required deliverables

1. A boundary/dataflow map showing immutable ownership, prepared-handle dependencies and invalidation events; identify cache keys only for caches the inspected implementation actually uses.
2. A reproducible baseline at a named revision/environment, with raw results and precise timing scopes. Report distributions of the measured quantity; batch-average spread is not per-call tail latency.
3. Independent economic examples and explicit tolerance/rounding rules.
4. A table of work counts, data movement, memory and latency by scenario and scale.
5. Ranked findings with evidence, expected impact and a small confirming experiment. Separate correctness defects from unnecessary work and optional optimizations.
6. Recommended regression budgets expressed primarily as work/size constraints. Timings guide experiments; they do not become brittle CI pass/fail thresholds.

Current code can be reviewed now. End-to-end trade-pricing claims require either the first real evaluator or a deliberately limited prototype. Label prototype measurements separately and retain their omitted work in the report. Standalone numerical examples and their tests remain useful evidence, not the production API or mandatory production array shape. Independent hand expectations and financial consistency checks supplement production regression snapshots; specimen snapshots are not production-library goldens.

## Starting material

- [Current pipeline](engineering-tickets/trade-valuation-pipeline/README.md), [NG worked example](engineering-tickets/trade-valuation-pipeline/ng-creation-preparation-example.md) and [Excel binding proposal](engineering-tickets/trade-valuation-pipeline/excel-trade-input-binding.md).
- [Project rules](../AGENTS.md) and [principles](../PRINCIPLES.md).
- [Measurement method](seam/measuring.md) and [historical baseline](seam/baseline.md).
- `tests/performance`, `tools/performance` and Excel lifetime/smoke scripts in the repository.
- [Discount-curve implementation](../src/catalyst/globals/discount_curve.py) and [documented contract](library/globals/discount-curve.md).

Run Python through `uv run` and begin with `.\check.ps1`. Inspect the measurement tools' documented scopes before running them. For example, `uv run python tools/performance/measure_python.py` measures the prepared Python seam on already-built inputs and excludes Excel and the host; it cannot answer the end-to-end latency question alone.
