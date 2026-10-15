# Bilateral discounting and DV01

[Pipeline overview](README.md) · [Mixed trade fields](mixed-trade-fields.md) ·
[Result meanings](result-fields-by-route.md) ·
[Existing discount curve](../../library/globals/discount-curve.md)

**Status:** Planning ticket, 8 October 2026, against the prototype through PR #163,
reviewed at `14130240`. The next agreed direction is bilateral valuation and DV01,
then broader Excel UAT, with rebuilding conditional on what that UAT reveals.
This ticket does not authorize landing the prototype stack or require a rebuild.
The conventions and additional function below are recommendations for alignment;
the DV01 direction and curve-date policy are specifically awaiting the owner's answers.

**Subsequent UAT steer:** The owner expects reported delta in **lots**. The monetary
delta formulas below remain valuation sensitivities; their reporting must be reconciled
with that lot view before this ticket is finalized. The agreed index-specific basis
and cleared implementation are in [Lot-delta reporting](lot-delta-reporting.md).
Whether bilateral lot delta is PV-weighted equivalent exposure or nominal remaining
exposure must be settled explicitly. Curve selection on the template/ticket versus
the current curve supplied at binding is also under discussion; the binding-only
association below remains a proposal, not an agreed decision.

## Outcome

Evaluate a batch of bilateral financial trades into its aggregate discounted mark,
cumulative nominal cash, discounted commodity delta and signed DV01. Keep the existing
trade creation, history preparation, dated slots, payment ownership and two reports.
One trade and many use the same path; evaluation does not produce individual trade values.

The essential change is to discount each unpaid payment group before aggregating.
Opposite exposures on the same contract can have different payment dates, so their raw
contract totals are insufficient for either NPV or discounted delta.

Keep the agreed names: `bilateral_mark` is the NPV of unpaid payments and
`bilateral_cash` is cumulative modeled paid cash. `_ReportValues` exposes these names;
`_ReportRisk` exposes `delta_total` and `dv01` with their units. Readers consume a
completed snapshot. Fees remain reserves and affect none of these measures.

## Scope and proposed conventions

| Topic | First implementation |
|---|---|
| Product | Existing `future` instrument, `route = bilateral`, `settlement_method = financial`; no new swap instrument required for this linear payoff |
| Batch | One index, route, settlement treatment and settlement currency unit, as today; existing mixed schedule methods, quantity terms and payment terms remain supported |
| Rate input | One explicitly supplied existing `DiscountCurve` for the batch; no rate curve on the static trade or template |
| Curve date — owner choice pending | Require `curve.start_date == history.calendar.valuation_date.as_of`; the existing first factor is exactly 1. Refuse mismatches rather than implicitly rebase an old curve |
| Curve coverage | Every unpaid group's payment date must be covered, including fixed-but-unpaid groups. Paid dates require no factors. No extrapolation |
| DV01 — direction pending | Recommend signed NPV change for a **+1 bp** parallel shift in continuously compounded zero rates, holding commodity prices, fixings, dates and quantities fixed |
| Time basis for that bump | Recommend ACT/365F: actual calendar days from valuation date to payment divided by 365; day-level valuation, without `day_fraction_elapsed` |
| Bump calculation | Exact finite change under the specified shift, not the first-order derivative approximation and not a bump to curve input discount factors |
| Payment cutoff | Existing rule: all observations fixed and `payment_date <= as_of`; full signed payment moves to cash, not yesterday's discounted value |

These are deliberately narrow conventions, not assertions that every desk defines DV01
this way. Resolve the two pending owner choices and confirm the rest before implementation.
If direction changes to a rate fall, change the bump and the independent expectations;
do not just negate the finite up-bump answer. If curve rebasing is chosen, specify its
date coverage and valuation-relative factors explicitly before coding it.

Reuse `_CreateDiscountCurve(header_row, table)`: it already builds daily factors from
anchors, interpolating linearly on discount factors. Do not add a zero-rate builder,
bootstrap, interpolation mode or valuation-parameters framework for this work.
Its current positive, non-increasing factors remain a limitation of this slice; negative-rate
curve support is a separate change.

The existing curve has **no currency metadata**. Supplying it explicitly associates it
with this batch's settlement currency; retain that association in the binding and results.
Do not claim that the curve's source currency was independently validated. The present
unit system supports USD and its scaled units such as CENT; discount factors are
dimensionless, and values and risks retain the index's settlement unit. A later multi-currency
feature must address curve identity and currency validation before allowing those combinations.

## Excel connections and ownership

Proposed addition: one small, explicit preparation function for rate-dependent state.
This keeps rates out of history preparation and avoids rebuilding rate weights on price ticks.

```text
trades      = _CreateTrades(index, fields, trade_rows, template)
prepared    = _PrepareTrades(trades, history)
curve       = _CreateDiscountCurve(curve_headers, curve_anchors)
discounting = _PrepareDiscounting(prepared, curve)
results     = _EvaluateTrades(prepared, market, discounting)
values      = _ReportValues(results)
risk        = _ReportRisk(results)
```

`_EvaluateTrades(prepared, market, [discounting])` gains an optional final argument.
For bilateral financial trades it is required, even when the batch is fully paid.
For cleared trades it is absent; supplying it fails rather than silently ignoring it.
A supplied blank remains a seam failure, not an omitted argument. The cleared two-argument
path preserves its current undiscounted mark, cash, delta and model-zero DV01.

`_PrepareDiscounting` accepts only the supported bilateral financial profile. Physical
trades have no modeled payment dates for this purpose and continue to fail rather than
acquire invented financial terms. Market creation and `_PrepareTrades` signatures stay unchanged.

The new immutable binding retains the exact prepared object and curve by reference, the
valuation date, settlement unit and risk convention. Evaluation checks:

1. The market's history is the prepared history, as today.
2. Route and supplied discounting agree with the supported profile.
3. The discounting belongs to this exact preparation, not another batch or history of
   the same name or date.

The binding builder owns curve-date and payment-coverage checks. Report the first uncovered
group in stable group order, its contract/payment date and the curve's range. Keep the
existing index/history and live-price coverage checks. Failure publishes no partial result;
evaluation never silently prepares history or discounting again.

Use the host's existing ownership and release machinery. A reference to an old result must
keep its old inputs and answers alive; subsequent price/rate changes cannot mutate them.
No global history or rate cache is required by this design.

## Calculation and compression

Retain the current financial grouping key `(contract reference, payment date)`. With one
currency and one curve per batch, no extra grouping field is necessary. Preserve groups
and dated slots through rate weighting; methods, units and clearing labels do not create
separate numerical paths after resolution.

For each unpaid payment group `g`:

```text
fixed_leg[g]         = encoded.offset_of_group[g]
floating_leg_set[g]  = prepared.set_amount[g]
floating_leg_live[g] = sum(live slot exposure * its current contract price, in group g)
payment_amount[g]    = fixed_leg[g] + floating_leg_set[g] + floating_leg_live[g]

D[g]   = supplied curve's factor on payment_date[g]
tau[g] = calendar_days(payment_date[g] - as_of) / 365
K[g]   = D[g] * expm1(-0.0001 * tau[g])

npv_by_group[g]  = payment_amount[g] * D[g]
dv01_by_group[g] = payment_amount[g] * K[g]

bilateral_mark = sum(npv_by_group)
dv01           = sum(dv01_by_group)
bilateral_cash = prepared.cash
```

`offset_of_group` is the existing code's name for the signed fixed leg. The above labels
explain the economics; this ticket does not require a repository-wide rename.
Fixed and set floating amounts both receive the payment's factor. Do not discount only
the live portion, and do not discount the batch's already-summed undiscounted mark.

`K` is the factor change under the chosen rate bump, not a second market input. Compute it
from the **already resolved payment-date factor**. Bumping sparse curve anchors and then
interpolating again gives a different sensitivity. No second full trade evaluation or
mutated curve is needed. Retain the finite convention: `-0.0001 * tau * D` is its linear
approximation, not the specified result.

Commodity delta on contract `r` is:

```text
delta[r] = sum(live_slot_exposure[s] * D[group(s)] for slots referencing r)
delta_total = sum(delta)
```

The stable contract axis stays unchanged; fixed contracts retain zero entries. Build this
discounted vector from the live slots and their groups, **not** from `prepared.delta` after
it has netted payment dates together. It can be retained in the discounting binding and
shared by results until history or rates change. Existing raw prepared delta remains the
undiscounted quantity measure used by cleared evaluation.

Paid groups have zero remaining NPV, commodity delta and DV01. Their full signed amount is
cash, even when their payment date predates the supplied curve. A fully fixed but unpaid
group has zero commodity delta but generally nonzero DV01. A zero-rate curve with all
factors equal to 1 still has bilateral rate sensitivity under a rate bump.

## Preparation and tick work

The binding gathers factors once per distinct unpaid payment date, establishes their group
mapping, computes time fractions and bump weights, and builds discounted delta. Retain
these compact arrays and the existing immutable references. Do not copy the daily curve,
expand a dense trade-by-date matrix or repeat unit conversion and schedule work.

For the first implementation, evaluate live contributions once, reduce them into the
existing payment groups, form group amounts, then calculate group NPV and DV01 together.
Both measures share the same price read and amounts. Adding the already prepared fixed and
set vectors is arithmetic, not another traversal of trades or history. More aggressive
compression into rate-weighted contract vectors can follow measurements; it is not required
to establish the correct payment amounts and stored contributions in this slice.

| Change | Reuse | Recalculate |
|---|---|---|
| Commodity price tick | Trades, history preparation, discounting factors/weights and discounted delta | Live group amounts, mark, DV01 and result snapshot; cash unchanged |
| Discount curve update, same as-of/history | Trades and history preparation | Discounting binding, discounted delta, mark, DV01 and result snapshot; no fixing reads |
| Fixing correction | Static trades/encoding; curve may remain the same if its date still matches | History preparation, its discounting binding, results; a corrected paid amount can change cumulative modeled cash |
| Valuation-date roll | Static trades/encoding | History preparation and payment status, a matching curve under the proposed date policy, discounting and results |
| Ticket or template change | Independent market inputs where compatible | Trade creation and all dependent preparation/results |

A price tick **can change DV01** because it changes future payment amounts. A rate tick
**can change commodity delta** because it changes the value of receiving that commodity
exposure on its payment date. Test both dependencies explicitly.

## Saved results and readers

Retain aggregate mark, cash, delta total and DV01, plus the following immutable arrays or
references. Names and record placement below describe required meaning, not new public fields.

| Content | Axis and meaning |
|---|---|
| `delta` | Existing stable contract axis, discounted for bilateral; zero after fixing |
| Payment amounts and NPV contributions | Existing payment-group axis; paid groups have zero NPV and their nominal amount remains inspectable |
| DV01 contributions | Existing payment-group axis, paid entries zero; additive contributions to the **same parallel curve bump**, not independent curve-node or market-quote sensitivities |
| Dated live contributions | Preserve today's slot-level undiscounted price-times-exposure meaning; payment factors remain accessible through the binding |
| Context | Prepared trades, commodity market, discounting binding/curve, as-of, route, settlement unit, value basis and precise DV01 convention |

There is one curve-level DV01 total in this slice. Keep its payment contributions as a
vector so later inspection does not require repricing; do not mislabel those contributions
as key-rate risk. Keep the commodity risk vector too. No per-trade results or dense
group-by-contract matrix are required.

Result contribution vectors use the full, stable payment-group axis. The binding may keep
factors only for unpaid groups with a mapping; do not invent discount factors for paid groups.

The two reports retain their current scalar layouts and unit fields. `_ReportValues`
already derives its mark/cash headers from route. `_ReportRisk` reports the stored total
delta and DV01 in settlement currency units per basis point; its help must state the bump
direction and value basis. `util_ReadHandle` shows the binding and stored result contents,
including axes/conventions, for inspection. None of the readers accesses current markets,
gathers factors, reprices or computes a missing total.

## Independent acceptance examples

These targets assume the proposed +1 bp finite convention. Record explicit tolerances,
for example absolute `1e-10` currency units for these small fixtures and a separately
justified tolerance for large cancellation-heavy batches. Do not obtain expected answers
by snapshotting the implementation being tested.

### Opposite trades with different payment dates

Both groups reference the same live contract at price 80 and fixed price 70. Normalized
signed exposures are +10 and -10. Use as-of 2027-01-04; payment dates 2028-01-04 and
2029-01-03 are 365 and 730 actual days later. This is a synthetic economic fixture,
not an exchange payment convention. A public-creator fixture must resolve these dates
through explicit valid payment lags/calendars, rather than bypass trade creation.

One feasible setup is a synthetic schedule with boundary Z26 expiring 2026-12-31,
traded F27 expiring 2027-01-04, and later F29 expiring 2029-01-05. With `lastday`, a
one-unit quantity specification and a weekday-only payment calendar, F27 rows of +10
and -10 at 70 with lags `+261bd` and `+522bd` resolve the two payment dates above.

| Group | Exposure | Fixed leg | Live floating leg | Net payment | DF | NPV | Contract delta contribution | DV01 contribution |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | +10 | -700 | +800 | +100 | 0.95 | +95 | +9.5 | -0.00949952501583294 |
| B | -10 | +700 | -800 | -100 | 0.90 | -90 | -9.0 | +0.0179982001199940 |
| Aggregate | 0 | 0 | 0 | 0 | — | **5** | **0.5** | **0.00849867510416106** |

This fixture catches compression before discounting and loss of payment ownership.

| Change from the base case | Mark | Cash | Delta | DV01 |
|---|---:|---:|---:|---:|
| Price 80 to 81, same curve | 5.5 | 0 | 0.5 | 0.00934854261457717 |
| DFs 0.96 / 0.92, price still 80 | 4 | 0 | 0.4 | 0.00879864010666093 |

Use an additional off-anchor case: curve anchors at day 0, DF 1, and day 730, DF 0.90.
The day-365 factor is 0.95. A +100 payment's DV01 is -0.00949952501583294. This prevents
an implementation from substituting anchor bumping/reinterpolation for the agreed bump.
The first table's analytic approximation would be 0.0085; that is not its finite target.

### Live, fixed and paid

One exposure +10, fixed price 70, observation on day 0, payment on day 365. Use fresh
all-one curves starting on each valuation date. Choose a synthetic calendar where the
observation and payment are valid business dates. The market must retain a later unused
contract so these fixtures do not depend on the deferred entirely-ended-calendar case.

| State | Mark | Cash | Delta | DV01 |
|---|---:|---:|---:|---:|
| Day 0, price 80; observation still live on its own day | 100 | 0 | 10 | -0.00999950001666625 |
| Day 0, price ticks to 81 | 110 | 0 | 10 | -0.01099945001833288 |
| Day 1, prior observation fixed at 82 | 120 | 0 | 0 | -0.01196652659067438 |
| Day 364, fixed and still unpaid | 120 | 0 | 0 | -0.0000328767078251083 |
| Day 365, modeled paid | 0 | 120 | 0 | 0 |

Day 1 uses 364/365 years, not one year. Add a non-unit-factor fixed-but-unpaid case:
payment 120 and DF 0.99 gives mark 118.8, then full cash 120 on the payment date.
Include a batch with one group paid and another unpaid, and a correction of a known fixing.

### Properties, boundaries and work

- Batch equals the sum of compatible singletons for all measures and aligned risk vectors;
  permutation preserves economics and duplicate occurrences count. Include mixed methods,
  month/calday quantities, unit selections, signed and zero quantities, strips and partial Asians.
- Discounted delta matches an independent one-quote-unit move in each reference. DV01
  matches independent scalar payment repricing under the declared shift, without calling
  the production bump helper to build its expected factors. Include a leap-day span.
- Same-payment-date groups can aggregate without changing answers; different dates stay
  distinct. A net-zero amount can still have commodity delta, and a raw-zero contract delta
  can become nonzero after discounting. Zero quantities retain normal validation.
- Missing discounting, the wrong preparation/history, wrong curve start and uncovered unpaid
  dates fail loudly. A fixed unpaid date still needs coverage. An all-paid batch accepts a
  matching one-day curve, reads no payment factors, returns only nominal cash and zero risks.
- Cleared numerical expectations stay unchanged. Cleared plus discounting and bilateral
  physical valuation fail by profile. Preserve all current missing-fixing and coverage refusals.
- Work/allocation budgets distinguish components, slots, groups, distinct unpaid dates and
  live references. A commodity tick reads each distinct live reference once, folds no fixings,
  rebuilds no schedules/conversions/payment dates, gathers no new curve factors and computes
  no time fractions or bump exponentials. Readers perform no valuation. Rate-only changes
  do not rebuild trade encoding or history preparation. Use counts, not timing gates.
- Lifetime tests retain an old result across price/rate ticks, then roll history and recover
  from a failed curve binding. Assert immutable old answers and release when owners disappear.

## Delivery

Treat this as a small feature arc above the reviewed mixed-fields prototype, not an instruction
to merge the stack. Two implementation PRs are a reasonable starting split:

1. **Discounting preparation:** settle and document the conventions, implement the binding
   and `_PrepareDiscounting`, identity/date/coverage rules, readback, factor/bump math and
   focused work/lifetime tests. Bilateral evaluation still refuses until the next slice.
2. **Bilateral evaluation and reports:** wire the binding into the existing evaluator,
   complete all four measures together, retain risk/contribution vectors, and add the
   independent examples through registered functions and the kept workbook. Update the
   smoke/host checks, public help, kernel, binding and result documentation together.

Run the full `check.ps1` gate for each PR and state meaningful work counts and retained-memory
changes. Review existing golden changes separately under the repository rule; workbook caches
and production snapshots do not establish the financial expectations.

Then UAT realistic cleared and bilateral batches side by side, including mixed schedules,
payment dates, partial fixings, commodity ticks, rate ticks and date rolls. Record ergonomic
and numerical findings before deciding what should be rebuilt on main.

Outside this arc: mixed routes or currencies in one batch, multiple discount curves, curve
bootstrapping, market-quote/key-rate DV01, rate-dependent commodity projections, collateral,
credit/funding adjustments, physical delivery, margining, actual-payment reconciliation,
intraday discounting, additional schedule methods and per-trade reporting.

## Reference for the financial convention

Payment-level present value uses a factor for the payment currency/date; Strata documents
that separation in its [payment pricer](https://strata.opengamma.io/apidocs/com/opengamma/strata/pricer/DiscountingPaymentPricer.html).
Its [risk measures](https://strata.opengamma.io/apidocs/com/opengamma/strata/measure/Measures.html)
also distinguish curve-parameter and market-quote PV01. Those references support the
distinctions, not our particular choice of sign, ACT/365F or finite parallel shift; those
are the explicit local conventions proposed above.
