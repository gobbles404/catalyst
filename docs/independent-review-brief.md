# Goosedove: independent valuation and performance review brief

Prepared 27 September 2026. Code inspected at `6fc6373`; the working tree also contains the design reports. Capture the exact commit and changes again when beginning the review.

## Reviewer profile

Seek a senior quantitative software/performance engineer who has shipped commodity derivatives valuation using Python/NumPy and understands .NET, pythonnet, Excel-DNA and Excel recalculation. The review should be independent of the earlier Priceratops implementation and the present design.

If one person does not cover both areas, pair a commodity/rates valuation specialist with a Python/.NET/Excel performance engineer. The first reviews cash, discounting and risk semantics; the second reviews data movement, repeated work, batching and ownership. A general code review alone is insufficient for either conclusion.

## Objective

Assess whether Goosedove's static-trade and array-based market design supports correct, efficient commodity valuation from Excel. Distinguish implemented guarantees, historical measurements and proposed behavior. Reproduce the current baseline before recommending changes. Prioritize small, demonstrated improvements over a framework rewrite.

The product-design context is the [futures trade field report](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/futures-trade-field-review.md). Trades preserve executed terms, including the agreed price. Commodity prices, discount curves, fixings and settlement state are separate inputs. Listed basis and averaging futures retain their own market identity; actual strips retain constituent contract positions.

## What the current evidence establishes

| Area | Evidence now | Limit |
|---|---|---|
| Market construction | Wrapper retains history, a price vector and an offset; avoids a daily expanded price array | Does not prove full market-feed update is constant work |
| Price snapshot | One owned float64 copy, 8 bytes per price plus overhead; allocation budgets exist | Updating a supplied vector still copies its values |
| Structure and ownership | Calendar/history references reused; creator reuse and handle release tested in Excel | Not proof of selective instrument recalculation or flat whole-process memory |
| Seam performance | Counts, copy/allocation checks, timing and profiling tools for Python, host and Excel | Most workloads are probes, not trade valuation |
| Pricing work budgets | Test-only cold/warm `quantities * prices` example | Production trade/payment/risk evaluator has not yet been implemented |

Sources: [market budget](C:/Users/jgile/.codex/worktrees/5b83/goosedove/tests/performance/test_seam_budgets.py:1587), [price-vector allocation](C:/Users/jgile/.codex/worktrees/5b83/goosedove/tests/performance/test_seam_allocation.py:594), [pricing stand-in](C:/Users/jgile/.codex/worktrees/5b83/goosedove/tests/performance/test_work_budgets.py:20), [ownership tests and open issues](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/seam/handles.md:185).

The stored timing baseline is revision `aaa5259`, measured September 11 local time / September 12 UTC. It predates the current code. For a 10,000-row `RowSums` probe, milliseconds per Excel recalculation were:

| Arrangement | Full recalculation | One input-cell edit |
|---|---:|---:|
| One formula per row | 226.91 | 1.17 |
| Ten arrays of 1,000 rows | 5.91 | 1.92 |
| One array of 10,000 rows | 7.93 | 8.85 |

This supports batching and the need to examine batch size/dependency scope. It does not establish current pricing throughput. A single-cell edit in a probe is not necessarily a market tick feeding many positions. [Timing baseline and boundaries](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/seam/baseline.md:93).

The repository check passed during this assessment: 1,365 Python tests, 190 host tests, 337 Excel smoke formulas and 26 lifetime checks, plus format/lint/types. These establish the tested behavior, not a portfolio latency target. No new timing baseline was collected for this brief.

## Questions the review must answer

### 1. Economic and rates boundary

- Are trade terms truly static while market/settlement state changes separately?
- Are cumulative futures P&L, settled cash, outstanding settlement and physical delivery obligations distinct outputs?
- Do actual payment dates, currencies and settlement/collateral agreements select the correct valuation treatment?
- How are curve start, valuation date and coverage checked? What happens at a day roll or out-of-range payment?
- Are projected amounts distinguished from fixed cash? Does a fixed-but-unpaid amount retain discount risk while losing commodity-price risk?
- Is risk to an independently traded futures index distinguished from risk through a reconstructed benchmark curve?
- Are rate bumps defined? Supplied discount-factor sensitivity must not be mislabeled as calibrated rate-instrument DV01.

Reconcile small cases independently: NG `Z26`, a bilateral lookalike with a delayed payment, an actual calendar strip, a listed basis future and an averaging future. Include opposite signed payments on different dates and offsetting trades with different execution prices. Do not infer two trade legs merely from a benchmark's difference formula.

### 2. Repeated work and invalidation

Measure first construction/calculation, unchanged repeat, one commodity-price update, one discount-curve update, fixing arrival, valuation-date roll and one trade edit. State exactly what each event invalidates and why.

Determine whether calendars, unit factors, contract selections and dependency mappings are rebuilt unnecessarily. Inspect repeated traversals for value, cash, delta and rate sensitivity. Test curve-grid changes as well as factor changes. Distinguish market-input gathering reuse from result caching.

Count hashed/scanned/copied elements and bytes. A counter reporting one hash can conceal an O(N) scan or copy. Determine whether selective recomputation actually improves the workload compared with a simple vectorized batch; do not assume a dependency framework is necessary.

### 3. Representation and scale

Use one-trade correctness cases and portfolio sweeps at 1,000, 5,000 and 10,000 trades; add a larger stress size after observing scaling. Vary unique contracts, repeated definitions, strip constituents, observation counts, currencies, payment dates and output cells independently.

Compare compact indexed arrays/grouped reductions with dense or sparse matrices where plausible. Quantify temporary rows and bytes. Preserve duplicate trade occurrences, execution-price constants, payment timing, deliverable eligibility and account attribution. Explain which work must scale with trades/output size and which can scale with unique shared dependencies.

### 4. Excel and host path

Attribute cost to Excel dependency calculation, argument hashing/comparison, .NET/Python transfers and GIL crossings, preparation, commodity/discount gathers, arithmetic, aggregation and worksheet publication.

Compare single-trade formulas, practical batches and one large batch under both broad updates and sparse edits. Include the time until results are available on the sheet. Separate cold startup from warm recalculation. Mark clearly whether clocks include COM control overhead, input construction, output publication and Excel itself.

### 5. Memory and long-run behavior

Stress thousands of updates, growing/shrinking batches, failed construction, duplicate creators, multiple workbooks and workbook closure. Measure temporary peak allocation, live retained objects, Python and .NET memory, and process memory where practicable. Handle-count plateaus alone are not proof of flat process memory.

## Required deliverables

1. A boundary/dataflow map showing ownership, cache keys and invalidation events.
2. A reproducible baseline at a named revision/environment, with raw results and precise timing scopes. Report distributions of the measured quantity; batch-average spread is not per-call tail latency.
3. Independent economic examples and explicit tolerance/rounding rules.
4. A table of work counts, data movement, memory and latency by scenario and scale.
5. Ranked findings with evidence, expected impact and a small confirming experiment. Separate correctness defects from unnecessary work and optional optimizations.
6. Recommended regression budgets expressed primarily as work/size constraints. Timings guide experiments; they do not become brittle CI pass/fail thresholds.

Current code can be reviewed now. End-to-end trade-pricing claims require either the first real evaluator or a deliberately limited prototype. Label prototype measurements separately and retain their omitted work in the report.

## Starting material

- [Project rules](C:/Users/jgile/.codex/worktrees/5b83/goosedove/CLAUDE.md) and [principles](C:/Users/jgile/.codex/worktrees/5b83/goosedove/PRINCIPLES.md).
- [Measurement method](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/seam/measuring.md) and [historical baseline](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/seam/baseline.md).
- `tests/performance`, `tools/performance` and Excel lifetime/smoke scripts in the repository.
- [Discount-curve implementation](C:/Users/jgile/.codex/worktrees/5b83/goosedove/src/goosedove/globals/discount_curve.py) and [documented contract](C:/Users/jgile/.codex/worktrees/5b83/goosedove/docs/library/globals/discount-curve.md).

Run Python through `uv run` and begin with `.\check.ps1`. Inspect the measurement tools' documented scopes before running them. For example, `uv run python tools/performance/measure_python.py` measures the prepared Python seam on already-built inputs and excludes Excel and the host; it cannot answer the end-to-end latency question alone.
