# Cross gamma of commodity delta to one discount curve

**Status:** Agreed 17 October 2026 and built the same day from main `84fa10a` on the branch `feat/single-curve-cross-gamma`, pull request #197, the record. Kept as the plan as it was: the code, [evaluate-trades.md](../../library/trades/evaluate-trades.md), [report-risk.md](../../library/trades/report-risk.md) and [aggregate-results.md](../../library/trades/aggregate-results.md) are maintained, not this page.
**Base:** Current main; the consolidation arc ends at `84fa10a`. Start implementation from main on a feature branch, suggested name `feat/single-curve-cross-gamma`. Record the actual base in the PR.
**Suggested PR title:** `feat(risk): report commodity delta sensitivity to rates`
**Delivery:** One feature PR with two reviewable commits: calculation and saved results, then collection and the Excel surface. Do not start the multiple-curve-per-batch work in this PR.

[Pipeline](README.md) · [UAT notes](surface-uat-notes.md) · [Evaluation](../../library/trades/evaluate-trades.md) · [Risk reporting](../../library/trades/report-risk.md) · [Collection](../../library/trades/aggregate-results.md)

## Outcome

Report how much a batch's discounted commodity lot delta would change, to first order, for a one-basis-point parallel increase in the discount curve's continuously compounded zero rates. Call this measure `cross_gamma`, in reporting lots per basis point.

The desk already sees nominal delta, discounted delta and DV01. Cross-gamma explains why its commodity hedge changes when interest rates move, including when the current NPV and DV01 are zero. It is a saved risk vector with a saved scalar total, available through the existing risk reader for one evaluated batch or a collection.

Keep one discount curve per evaluated bilateral batch. The instrument, templates, trade rows and all creator signatures stay as they are. The new risk comes from the current payment groups, prepared live exposure and supplied curve; no extra preparation stage or worksheet function is needed.

## Meaning and units

| Measure | Meaning in this library | Units |
|---|---|---|
| `nominal_delta` | Remaining commodity exposure without discounting | Index reporting lots |
| `delta` | Remaining commodity exposure weighted by the route's valuation treatment | Index reporting lots |
| `dv01` | Signed sensitivity of NPV to a parallel rate increase, scaled to 1 bp | Settlement currency per basis point |
| `cross_gamma` | Signed sensitivity of discounted lot delta to that same rate increase, scaled to 1 bp | Index reporting lots per basis point |

For this ticket, the rate move is exactly the convention already used by DV01: ACT/365F and a parallel shift of continuously compounded zero rates. Hold trades, valuation date, commodity prices, fixings, payment dates and the curve's coverage constant while taking this derivative.

This is a first-order sensitivity scaled to 1 bp, not the exact change from a finite 1 bp scenario. It is not commodity-price gamma, rate convexity, key-rate/node risk or a correlation model. Nominal delta is independent of the discount curve; its rate sensitivity is zero.

For one positive live payment exposure, rising rates reduce discounted delta, so cross-gamma is negative. A negative exposure has the opposite sign. The sign of a portfolio depends on its payment-weighted exposures, not its net quantity or its NPV.

## Calculation and where compression happens

For each live observation slot `s`, let `g(s)` be its payment group:

```text
q[s]   = prepared live nominal lots at the slot, signed and fractional
D[g]   = discount factor on the group's payment date
tau[g] = calendar days from as_of to the payment date / 365

discounted_lots[s] = q[s] * D[g(s)]
cross_gamma[s]     = -0.0001 * tau[g(s)] * discounted_lots[s]
```

The derivation is `D_bumped[g] = D[g] * exp(-b * tau[g])`, where `b` is a decimal rate shift. Differentiate discounted lots with respect to `b` at zero, then multiply by `0.0001`. No actual curve bump or second evaluation belongs in production calculation.

Fixed and paid slots contribute exactly zero. A fixed-but-unpaid payment can retain NPV and DV01 while its commodity delta and cross-gamma are zero. Cleared trades have zero cross-gamma under the existing undiscounted valuation treatment.

Apply the payment's own time weighting before summing slots across payment groups. Never multiply total delta by a final, average or representative maturity. Different payment dates must remain distinct until this calculation is complete, even if the pricing contract and observation date match.

Reuse `prepared.unpaid_payments.tau` and the payment factors evaluation already gathers. `tau` is aligned to the unpaid group's positions, not directly to all groups or all slots; map it explicitly. Assign zero to paid groups without reading a past DF. Do not recompute year fractions, sort payment dates, resolve contracts or read fixings on a price tick.

## Worked acceptance example

These are synthetic economics, not exchange specifications. Use an index whose reporting lot contributes one settlement-currency unit for a one-unit change in its quote, so money and lots remain easy to follow.

Valuation day is **4 January 2027**. Both trades observe one synthetic `G27` pricing contract on **1 February 2027**, with a live quote of **72**. Both are bilateral and use the same curve. Include the preceding boundary contract and later untraded contracts required by the current calendar and market rules.

| Trade | Quantity in lots | Fixed price | Payment date | Lag from observation | tau | DF |
|---|---:|---:|---|---|---:|---:|
| A | 10 | 70 | 4 January 2028 | `+337cd` | 1 | 0.95 |
| B | -5 | 74 | 3 January 2029 | `+702cd` | 2 | 0.90 |

The second payment is exactly 730 calendar days after as_of. Curve anchors are `(as_of, 1)`, `(4 January 2028, 0.95)` and `(3 January 2029, 0.90)`, built with the existing daily interpolation. Payment lags use calendar days; use an ordinary empty holiday calendar for the required payment-calendar field.

| Trade contribution | Nominal lots | Discounted lots | Payment amount | NPV | DV01 | Cross-gamma, lots/bp |
|---|---:|---:|---:|---:|---:|---:|
| A | 10 | 9.5 | 20 | 19 | -0.0019 | -0.00095 |
| B | -5 | -4.5 | 10 | 9 | -0.0018 | 0.00090 |
| Total | 5 | 5 | 30 | 28 | -0.0037 | -0.00005 |

The contribution rows explain the arithmetic; the implementation need not produce individual trade valuations. The batch retains two payment groups even though its commodity risk compresses to one contract and one observation date.

With the quote changed to **73**, NPV becomes **33** and DV01 **-0.00375**. Nominal delta stays **5**, delta **5**, and cross-gamma **-0.00005**. This pins that cross-gamma is not derived from the live monetary contribution or NPV.

With the original quote and payment DFs changed to **0.96 / 0.92**, delta becomes **5**, NPV **28.4**, DV01 **-0.00376**, and cross-gamma **-0.00004**. Equal net delta does not imply equal cross-gamma.

Two further hand examples reuse the dates and original DFs:

| Case | Quantities and fixed prices | NPV | DV01 | Nominal delta | Delta | Cross-gamma |
|---|---|---:|---:|---:|---:|---:|
| Zero NPV | A +10, B -5, both fixed at the live quote 72 | 0 | 0 | 5 | 5 | -0.00005 |
| Zero discounted delta | A +18, B -19, both fixed at 70; quote 80 | 0 | 0.0171 | -1 | 0 | 0.00171 |

In the second case, discounted exposures are **+17.1** and **-17.1**. Their different maturities leave cross-gamma of **-0.00171 + 0.00342 = 0.00171**. Netting the discounted delta before applying time would incorrectly return zero.

## Ownership through the existing pipeline

| Stage | Responsibility for this feature |
|---|---|
| CreateTrades / encoding | Keep current static slots, payment groups and reporting axes. No curve association or new instrument fields |
| PrepareTrades | Keep current live lots, paid/fixed state and unpaid payment time fractions; no new curve input |
| EvaluateTrades | Reuse current DFs and discounted slot lots; calculate, validate and save cross-gamma |
| Saved result | Own immutable cross-gamma vectors, total and facts needed to refuse unsupported earlier-period reporting |
| AggregateResults | Sum saved cross risk within the correct index-and-curve groups; never evaluate or bump a source |
| ReportRisk / ReadHandle | Select and format saved values; no risk calculation or summing totals |

Follow the consolidated module responsibilities: calculation in `trades/evaluation.py`, saved results and their view selection in `trades/results.py`, collection in `trades/aggregation.py`, shared selectors/labels in `trades/risk_report.py`, and Excel formatting in `excel/trades.py`. Do not introduce a general Greek engine, report registry or parallel result hierarchy.

Retain these logical values on each result; internal field names remain engineering choices:

| Saved value | Axis / purpose |
|---|---|
| Cross-gamma by contract | The existing stable pricing-reference axis |
| Cross-gamma by day | The existing observation-date axis |
| Cross-gamma by month | The existing pricing-contract month axis |
| Cross-gamma by year | The existing pricing-contract year axis |
| Cross-gamma total | Sum of the batch's cross risk in its reporting lots per bp |
| Earlier-period facts | The existing report refusal policy applied to this measure |

Arrays are immutable, including all-zero states. Preserve the axes as slots fix and payments settle. An intermediate slot vector need not be retained merely to support a debug spill. Cleared zero risk may use an explicit known-zero representation; do not allocate unnecessary full-sized zero buffers just for symmetry.

## Worksheet and report contract

Signatures remain:

```text
_EvaluateTrades(prepared, market, [discount_curve]) -> results
_AggregateResults(result_handles) -> aggregate_results
_ReportRisk(results_or_aggregate, risk, bucket) -> spill
```

Add the exact selector `cross_gamma`. All three ReportRisk arguments remain required; bucket choices remain `day`, `month`, `year`. No bump-size or risk-method parameter is added.

For a single bilateral result, use a heading such as:

```text
HNG curve_1 cross_gamma [LOT per basis point]
```

`HNG`, `LOT` and the curve label come from the same records and numbering rules as the existing reports; do not hardcode the lot spelling. Keep the current as_of, heading, type and saved Total rows.

For the primary example, the meaningful contents of `=_ReportRisk(result,"cross_gamma","month")` are:

| period | HNG curve_1 cross_gamma [LOT per basis point] |
|---|---:|
| Total | -0.00005 |
| 1 January 2027 | 0 |
| 1 February 2027 | -0.00005 |

The day report puts the value on **1 February 2027**, its observation day. The month and year reports use the **pricing contract's** month and year, just like delta, even if the observation is in a preceding month. Payment dates supply the time weighting; they do not become cross-gamma's display axis. A rolling Asian assigns cross risk to the contracts pricing its live days.

Follow current period display rules: month/year begins in the period containing as_of, shows consecutive periods to the last relevant saved contract period, and refuses nonzero earlier risk rather than silently dropping it. Daily reporting retains the observation axis. Month/year is not obtained by calendar-bucketing the daily report.

`all` includes the new measure. Preserve every existing column's relative order and position by **appending cross-gamma columns after the existing nominal-delta, delta and DV01 columns**. A single bilateral result therefore has four risk columns. Reuse the existing union of commodity and payment periods, zero-filling through saved mappings where appropriate.

Cleared policy is explicit: cross-only reports a zero Total and zeros on the commodity risk axis, headed `HNG cleared cross_gamma [LOT per basis point]`. Under `all` that zero column is appended. A paid bilateral result also reports zeros on its retained commodity axes, subject to the usual period display start.

Update all kept callers whose `all` spill width changes. Existing selectors keep their numerical values, units and layouts. Do not add a new ReportCrossGamma function.

## Collection without adding multiple curves to a batch

A collection already accepts separate batches valued on different curves. That remains supported. Cross risk belongs to **the pair of exact index object and exact curve object**, not the existing index-only delta group or curve-and-currency DV01 group.

For example:

| Sources | Cross-gamma columns |
|---|---|
| Two HNG batches on curve A | One HNG / curve A vector, summed |
| HNG on A and HNG on B | Separate HNG / A and HNG / B vectors |
| HNG and WTI both on A | Separate HNG / A and WTI / A vectors; their lots are not summed |
| Cleared HNG and bilateral HNG on A | HNG / cleared zero column and HNG / A column |

Treat cleared sources as an index-and-no-curve group with known-zero risk. This keeps a cleared-only collection and a single cleared result consistent without pretending a discount curve exists. Show that zero group even in a mixed collection; there is no hidden summing across curve groups.

Cross groups follow first appearance of the pair in supplied occurrence order. Reuse the collector's existing curve numbers, so `curve_1` means the same curve in DV01 and cross-gamma headings. Equal-valued but distinct curve objects remain distinct. A repeated source counts again, and two wrappers over the same permitted market inputs retain current compatibility behavior.

Keep all current as_of, index-name, index-identity, history and price-vector checks. Keep existing delta grouping by index and DV01 grouping by curve/currency. Build and validate saved cross vectors and totals during collection. Apply earlier-period checks after summing within each cross group; cancellation across different curves or indexes must not hide a group's risk. There is no combined cross-gamma scalar across unlike indexes or separately shifted curves.

## Debug readback

Add a saved contract cross-gamma column and an explicit unit to the evaluated-result readback, beside its existing contract risk in meaning but appended in position to minimize unrelated column movement. State that a contract total repeated on multiple slot rows is repeated context, not additive per-slot risk. Do not recalculate a slot value in the reader or pretend the rows are individual trades.

Append each source's saved cross-gamma total and unit to the collection's occurrence readback. Keep its existing membership-row policy: no group totals or second risk report inside ReadHandle. Existing curve attribution identifies the single curve of each source. The public report remains the place for aggregate vectors and totals.

## Update behavior and measured work

| Change | Expected behavior |
|---|---|
| Commodity quote tick | Existing evaluation runs; mark and DV01 may move, but cross-gamma is numerically unchanged when history, dates, quantities and curve are unchanged |
| Discount curve update | Evaluate against the same preparation; delta, DV01 and cross-gamma update |
| Fixing arrival / as_of roll | Follow the existing new-history/preparation path; live slots and payment times change; fixed exposure loses cross-gamma |
| Fixed price or reserve changes only | Cross-gamma is unchanged for identical quantities, schedule, payment dates, as_of and curve |
| Report selector / bucket changes | Select saved data; no valuation, curve access, risk reduction or new creator handle |

Do not add caching or selective repricing. A quote tick may repeat this small analytic calculation as part of evaluation; measuring it is the goal here, not introducing another mutable state store.

Pin before/after work for one trade and a representative large batch. Cross-gamma adds slot arithmetic, contract/day/month/year reductions and a saved total. Factor reads, price reads, fixing reads, date sorting and schedule construction must not increase. Reuse current payment-time facts and factor gathers; count any necessary mapping work honestly. Four new vector reductions are expected if the current reduction structure is followed; count the actual implementation rather than assuming a total.

Retained bilateral numeric storage should be explainable by the saved axes: approximately `8 * (contracts + observation_days + contract_months + contract_years)` bytes plus the scalar and metadata. Measure temporary buffers, cleared zero handling and aggregate storage too. No copied source records or unrelated budget increases. Readers may place/format vectors as today but do not reduce them; collection aligns and sums saved vectors only.

## Verification

Expected answers start with the hand arithmetic above. No production-output snapshot is the proof of financial correctness. The tables state real-arithmetic targets: compare calculated sums with an explicit floating-point tolerance, including cancellations such as `18 * 0.95 - 19 * 0.90`. Do not round or clip production risk to make a mathematical zero exact. Structural zeros from fixed, paid or cleared exposure remain zero by construction.

1. **Worked figures:** pin the base example, quote move, curve move, zero-NPV case and zero-discounted-delta case, including the separate payment contributions and the reported totals.
2. **Independent numerical derivative:** for well-behaved strictly decreasing daily factors, form `D_plus(t)=D(t)*exp(-h*tau(t))` and `D_minus(t)=D(t)*exp(h*tau(t))`. Evaluate delta on both and compare `0.0001*(delta_plus-delta_minus)/(2*h)` with analytic cross-gamma. Use a small decimal bump such as `h=1e-5`; compare contract and dated vectors as well as totals. Check agreement at a second suitable bump using an explicit absolute/relative tolerance justified by truncation and float error. Do not demand monotonically improving error as h shrinks, since roundoff eventually dominates, or equality to the exact one-sided 1 bp change. The primary toy's centered result at the stated h is approximately `-0.0000499999999581`.
3. **Bump the built daily curve:** apply the test shift to every daily factor, with the first factor still 1, and use the ordinary curve constructor. Bumping only sparse anchors and re-interpolating tests a different convention. Choose data for which both bumped curves satisfy the existing monotonicity rules; do not relax those rules or ship a new bump utility for this ticket.
4. **Lifecycle:** partially fixed Asian exposure keeps only its remaining weighted cross risk; fixed-but-unpaid can have nonzero NPV/DV01 with zero cross; paid risk is zero with unchanged nominal cash; cleared physical and financial paths stay zero without requesting a curve. Retain a valid market with later untraded contracts for fully fixed examples; do not expand the ended-calendar boundary.
5. **Axes:** preceding-month NG expiry belongs to the pricing contract month/year, its day entry remains the observation date; a rolling Asian splits by pricing reference; payments spanning years weight correctly; daily/monthly/yearly totals reconcile while their date attribution differs.
6. **Cardinality and compression:** batch equals the sum of singleton results on the same state; reordered tickets, repeated occurrences, buys, sells, zero quantity and multiple payment dates preserve the economics. Cancellation is permitted only after the appropriate payment weighting.
7. **Collections:** same index/same curve combines; same index/different curves separates; different indexes/same curve separates; an equal-valued curve copy separates; cleared groups stay zero. Test repeats, reordered sources, single-source collection equivalence, period display and cancellation within versus across cross groups.
8. **Failures and immutability:** preserve existing refusals and their order. Every new calculated vector and total must be finite before publication; fail with the relevant slot/group, contract, date, bucket or collection group when arithmetic cannot be represented. Do not return a partially populated handle, clip or hide overflow by netting. Held result/collection snapshots remain unchanged through quote, curve and history updates.
9. **Surface:** exercise the selector, units, saved Total, all three buckets, widened `all`, cleared zeros and both handle kinds through seam tests, host replay and Excel smoke. Add a compact kept-workbook block using the worked example with quote and curve changes. Extend the existing valuation lifetime scenario only as needed to prove the new saved risk follows the existing handle behavior.

The existing unit and budget suites for bilateral valuation, aggregate risk, contract bucketing and Excel trade reports are the starting places. Add a focused cross-gamma test module if that keeps the mathematical examples together. Run the full repository gate and report measured work/storage changes. Follow the existing golden-baseline review rule if goldens are introduced or changed.

## Suggested commits and documentation

**Commit 1: analytic risk and saved ownership.** Add the per-payment calculation, immutable saved vectors/total, numerical and lifecycle tests, and honest work/memory pins. Preserve current public report behavior until the next commit wires the selector. No signature or instrument change.

**Commit 2: collection and reporting.** Add index-and-curve grouping, the selector and shared heading rule, debug readback, Excel/host/workbook coverage and the owning documentation. Both single-result and collected-result paths must be complete before the feature PR is ready for review.

Use the documentation ownership map in [working.md](../../seam/working.md#10-what-each-page-owns). Update the evaluation page for the calculation convention, the risk-report page for selectors/axes/units, and the collection page for grouping, linking between owners rather than repeating the full derivation. Exact numbers, error text and work counts belong to tests. Carry this ticket as the proposal and update its status when implemented; UAT notes and the packet index link to it.

The PR is ready when the new report works for one batch and a collection, all existing valuation/risk outputs are unchanged, the hand and numerical checks agree, measured work is explained, and the full gate passes. No permission to merge is implied by this planning ticket.

## Deferred work and the wider arc

The next feature after this is multiple discount-curve selections inside one trade array. Its static selection key must survive compression before evaluation binds the actual curves. This ticket retains one curve per batch and introduces no SOFR/FFOIS trade field, curve-set creator, market envelope or general curve registry.

Cashflows, commodity interpolation, quoting, market depth, marketing-reserve calculations, public curve-bump utilities, node-level cross risk and performance caching are separate work.

**Ticket/reference-data hygiene is also separate**, to revisit around the quoting arc: consistent counterparty/broker identities and eventual CTRM interoperability. No dropdown design, reference-list enforcement, data-entry UI or booking-field change has been agreed here.
