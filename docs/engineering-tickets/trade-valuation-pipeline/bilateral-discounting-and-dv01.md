# Bilateral discounting and DV01

[Pipeline overview](README.md) · [Mixed trade fields](mixed-trade-fields.md) ·
[Result meanings](result-fields-by-route.md) ·
[Existing discount curve](../../library/globals/discount-curve.md)

**Status:** Planning ticket, 8 October 2026, against the prototype through PR #163,
reviewed at `14130240`. The next agreed direction is bilateral valuation and DV01,
then broader Excel UAT, with rebuilding conditional on what that UAT reveals.
This ticket does not authorize landing the prototype stack or require a rebuild.
Updated 10 October against the discussion after reviewed PR #173: the owner agreed to
pass a discount curve directly to evaluation as an optional final argument, with no
additional public preparation step initially. Agreed since: DV01 is the analytic signed
sensitivity of the discounted mark to a one basis point rise in continuously compounded zero
rates, ACT/365F, not a finite bump, and the readers expose both lot deltas as distinct columns,
`nominal_delta` and `delta`. The curve-date policy is agreed too: the curve is anchored at `as_of`,
its start date the valuation day and a mismatch refused. No bilateral valuation is implemented by
this ticket. Counterparty and marketing reserve are built in #175.

**Subsequent UAT steer:** The owner expects reported delta in **lots**. The monetary
delta formulas below remain valuation sensitivities; the reporting is settled as two lot columns,
`nominal_delta` and `delta`, beside the monetary sensitivity. The agreed index-specific basis
and cleared implementation are in [Lot-delta reporting](lot-delta-reporting.md).
The owner now wants **both nominal and discounted lot delta**, separately named, alongside
DV01; the desk generally hedges to discounted delta. Neither measure replaces the other.
Changing curve data must not dirty the static trade or repeat unchanged fixing work.
One explicitly supplied curve applies to the evaluated batch in this first slice.
Combining risk across evaluated batches is deferred until these individual measures are right.

**Counterparty reminder, 9 October:** Include a `counterparty` field in the instrument
definition when implementing bilateral trades. Support normal template/ticket entry and
retain it on the resolved trade. The owner subsequently agreed: required for bilateral,
absent for cleared. This is tracked in [UAT item 11](surface-uat-notes.md#11-counterparty-on-bilateral-trades).

**Owner steer, 10 October: representation first.** Break the bilateral work into
manageable PRs, starting with the instrument and booked fields. Include an optional,
manually entered marketing reserve: a one-time booked amount with no release schedule,
accrual or effect on valuation or DV01. Reuse the existing reserve summary and
`_ReportReserves`; compute the static total at creation and carry it into results.
The field is `marketing_reserve`, matching the existing report column. The owner
confirmed positive-cost reporting like brokerage and clearing: allow finite amounts
greater than or equal to zero, and reject negative amounts. The agreed entry basis is
one amount in the index's settlement currency unit per entered trade occurrence,
counted once even for a strip, with omission giving zero. The field is optional on
either route, as agreed by the owner.
If supplied by a template, the amount applies once to each resulting trade
row; duplicate occurrences count independently. It is not a per-lot reserve rate.

**Agreed catalog rename, 10 October:** Replace the broad instrument identifier `future`
with `fixed_float`. This is one renamed definition, not a second instrument or pricing
path. Implementation and migration of catalog discovery, templates, help, errors,
tests and kept workbook callers belong in the
[rename-only first PR](rename-instrument-fixed-float.md); no compatibility alias. Do not
rename actual futures products, index kinds or futures schedules merely because their
names contain "future". `route = cleared | bilateral` already exists; bilateral work
enables its valuation rather than adding a third route. Preserve the current settlement
rules and pipeline responsibilities through the rename. This document records the
decision; the prototype exposes `fixed_float` since #174.

## Trade representation field inventory

There are 16 existing fields and two additions. The table describes the intended
`fixed_float` representation, agreed by the owner and built in #174 and #175.
The public pipeline signatures remain:

```text
_CreateTradeTemplate(instrument, fields, values) -> template
_CreateTrades(index, fields, trade_rows, template) -> trades
```

`instrument = "fixed_float"` is selected once on the template. The index is supplied
once to `_CreateTrades`; neither is a ticket field. Template and ticket fields are
disjoint, with exact headers and no overrides. The required template may supply the
shared terms; row-specific values complete each trade.

| Field | Type and permitted values/examples | Requiredness and meaning |
|---|---|---|
| `trade_id` | Whole number of at most 15 digits, such as `123456`; zero and signed IDs remain valid | Optional. External attribution; duplicates keep separate occurrences. |
| `trade_date` | Excel date | Required. Actual execution date, independent of market as_of. |
| `contract_code` | Existing case-insensitive period text, such as `Z26`, `CAL27`, `X26-Z26` | Required when no complete date pair supplies the period. Complete dates take precedence; any entered code is then retained as inactive text. |
| `start_date` | Excel date | With `end_date`, inclusive booked period. Both dates or neither; partial periods remain subject to method support. |
| `end_date` | Excel date on or after start | With `start_date`; a half-supplied pair fails, even with a code. |
| `schedule_method` | `lastday`, `penultimate`, `last3day`, `asian` | Required. Existing index/method compatibility remains: IFERC supports lastday only; partial months use asian. |
| `route` | `cleared`, `bilateral` | Required; one route per batch. |
| `settlement_method` | `physical`, `financial` | Required; one settlement method per batch. First bilateral valuation scope is financial; existing physical restrictions remain. |
| `clearing_house` | Text, such as `CME Clearing` | Required for cleared and absent for bilateral under the current rule. Attribution does not select payment terms or reserve rates. |
| `counterparty` (new) | Text, such as `Example Energy` | Required for bilateral and absent for cleared; retained per trade, available from template or ticket. No implicit curve selection or counterparty netting. |
| `broker` | Text | Optional attribution. Does not determine the brokerage rate. |
| `quantity` | Signed whole number, including zero | Required. Count of the selected quantity specification. |
| `quantity_unit` | Exact name of a specification supplied by the index; `LOT`, `BBL` or another name only if defined there | Required. The index supplies its size/unit conversion. |
| `quantity_per` | `month`, `calday` | Required. Per booked monthly component, or per covered calendar day. |
| `fixed_price` | Finite number in the index's quote units | Required. Signed prices remain allowed; the entered price applies to each component of the row. |
| `payment_time_lag` | Positive whole business-day lag, such as `+1bd` or `+5bd` | Required for financial settlement and absent for physical. Existing product anchor applies; zero/negative lags remain unsupported here. |
| `payment_holiday_calendar` | Holiday-calendar handle | Required for financial settlement and absent for physical. Supplies payment holidays. |
| `marketing_reserve` (new) | Finite number >= 0, in the index's settlement currency unit | Optional static cost on either route; omit the field for zero. One entered amount per trade occurrence, not per component, lot, day or payment. |

Existing period rules allow blank or exact empty-text cells in the three period fields.
Other present fields retain strict cell validation. In particular, under the current
seam policy an omitted `marketing_reserve` field can default to zero, but a supplied
column contains numbers, including explicit zeros; its blank cells do not silently
become zero. Any broader blank policy must be agreed separately.

Payment dates are resolved facts rather than another input column. On a futures index,
the current anchor is the component's last observation; on an IFERC index it is the
month's last trading date. These initial payment rules do not cover every bilateral
agreement. Do not change their meaning through the instrument rename.

Brokerage and clearing reserve rates still come from the selected index specification,
not new manual trade fields. The current discount curve is a changing market input;
this field inventory adds no curve object to the static trade. Evaluation receives the
curve explicitly in the next slice. Retain one index per batch
and existing mixed schedules, units, quantity bases and payment terms.

The owner agreed the representation inventory, including counterparty required on
bilateral only and marketing reserve optional on either route. The subsequent discussion
settled the evaluation boundary and separate risk measures. Detailed rate conventions
and report layouts below are agreed, not yet implemented behavior.

## Static encoding and changing rate inputs

The owner reaffirmed this boundary on 10 October: a replacement discount curve must not
recreate trades, resolve schedules or reread commodity fixings. Static trades hold the
payment dates, currency, fixed-leg amounts and observation exposures. Current discount
factors and rate-risk weights are supplied or calculated during evaluation.

Inspected prototype through PR #173 already has the necessary payment ownership:
`Encoded.payment_date`, `offset_of_group` and `slot_group`, and preparation's
`set_amount`, `is_settled` and live-slot exposures. No new static curve field or redesign
of the encoding is needed for the proposed one-curve-per-batch slice. The evaluator must
use these payment-group amounts, rather than discounting its convenience totals
`offset_unsettled` and `set_unsettled` after payment dates have been summed together.

Agreed wiring: `_PrepareTrades(trades, history)` remains the fixing preparation;
`_EvaluateTrades(prepared, market, [discount_curve])` consumes the current commodity
market and, for bilateral financial trades, the current curve. The previously proposed
`_PrepareDiscounting` is not part of the initial surface. Keep rate gathering and weighting
in small internal functions; do not introduce an implicit cache or reprepare history.

Commodity and rate ticks reuse static trades and history preparation. Either tick creates
new evaluated results and initially repeats rate gathering and discounted-risk arithmetic.
A history change rebuilds preparation before evaluation. Record the work rather than
assuming payment groups and dated slots are small. A later explicit reusable rate binding
would require evidence and a separate surface decision.

First scope: one explicitly supplied curve for the evaluated batch's settlement currency.
No curve selection inferred from counterparty. If multiple curve
assignments are introduced later, define their stable selection and retain their payment
ownership before allowing compression across them. Curve-date alignment is agreed, the curve anchored at `as_of`, its start date the valuation day;
the DV01 convention is the analytic derivative below and the readers
expose both lot-risk measures as `nominal_delta` and `delta`.

## Outcome

Evaluate a batch of bilateral financial trades into its aggregate discounted mark,
cumulative nominal cash, nominal and discounted commodity lot deltas, and signed DV01.
Keep the existing trade creation, history preparation, dated slots and payment ownership.
One trade and many use the same path; evaluation does not produce individual trade values.

The essential change is to discount each unpaid payment group before aggregating.
Opposite exposures on the same contract can have different payment dates, so their raw
contract totals are insufficient for either NPV or discounted delta.

Keep the agreed names: `bilateral_mark` is the NPV of unpaid payments and
`bilateral_cash` is cumulative modeled paid cash. `_ReportValues` exposes these names;
the risk readers must distinguish nominal and discounted lots explicitly. Their final
column names/selection contract remain open. Readers consume a completed snapshot.
Fees remain reserves and affect none of these measures.

## Scope and proposed conventions

| Topic | First implementation |
|---|---|
| Product | Broad definition renamed to `fixed_float`, `route = bilateral`, `settlement_method = financial`; renamed in #174, the two booking fields added in #175 |
| Batch | One index, route, settlement treatment and settlement currency unit, as today; existing mixed schedule methods, quantity terms and payment terms remain supported |
| Rate input | Agreed: existing `DiscountCurve` as optional final evaluation argument, required for bilateral; no rate curve on the static trade or template |
| Commodity risk | Agreed: retain nominal remaining lots and discounted lot equivalents as distinct vectors and totals, alongside monetary NPV sensitivity |
| Curve date — agreed | Require `curve.start_date == history.calendar.valuation_date.as_of`; the existing first factor is exactly 1. Refuse mismatches rather than implicitly rebase an old curve |
| Curve coverage | Every unpaid group's payment date must be covered, including fixed-but-unpaid groups. Paid dates require no factors. No extrapolation |
| DV01 — agreed | The analytic signed sensitivity of the discounted mark to a **+1 bp** parallel rise in continuously compounded zero rates, holding commodity prices, fixings, dates and quantities fixed: `-0.0001 * tau * D * payment_amount` per unpaid group, summed; negative for an amount receivable, positive for one payable |
| Time basis | ACT/365F: actual calendar days from valuation date to payment divided by 365; day-level valuation, without `day_fraction_elapsed` |
| No bump | The derivative is taken on the already resolved payment-date factor: no finite shift, no bumped anchors re-interpolated and no second evaluation |
| Payment cutoff | Existing rule: all observations fixed and `payment_date <= as_of`; full signed payment moves to cash, not yesterday's discounted value |

These are deliberately narrow conventions, not assertions that every desk defines DV01
this way. Every convention above is agreed; confirm the wording, not the choices, before
implementation. The curve is never rebased: a curve starting on another day is refused.

Reuse `_CreateDiscountCurve(header_row, table)`: it already builds daily factors from
anchors, interpolating linearly on discount factors. Do not add a zero-rate builder,
bootstrap, interpolation mode or valuation-parameters framework for this work.
Its current positive, non-increasing factors remain a limitation of this slice; negative-rate
curve support is a separate change.

The existing curve has **no currency metadata**. Supplying it explicitly associates it
with this batch's settlement currency; retain that association in results.
Do not claim that the curve's source currency was independently validated. The present
unit system supports USD and its scaled units such as CENT; discount factors are
dimensionless, and values and risks retain the index's settlement unit. A later multi-currency
feature must address curve identity and currency validation before allowing those combinations.

## Excel connections and ownership

Agreed initial path: one optional final curve argument at the existing evaluation boundary.
History preparation has no new curve dependency.

```text
trades      = _CreateTrades(index, fields, trade_rows, template)
prepared    = _PrepareTrades(trades, history)
curve       = _CreateDiscountCurve(curve_headers, curve_anchors)
results     = _EvaluateTrades(prepared, market, curve)
values      = _ReportValues(results)
risk        = _ReportRisk(results)
```

`_EvaluateTrades(prepared, market, [discount_curve])` gains an optional final argument.
For bilateral financial trades it is required, even when the batch is fully paid.
For cleared trades it is absent; supplying it fails rather than silently ignoring it.
A supplied blank remains a seam failure, not an omitted argument. The cleared two-argument
path preserves its current undiscounted mark, cash, nominal lot delta and model-zero DV01.
Cleared payment delays still control mark-to-cash timing; they do not trigger DF lookup.
Under that valuation treatment, its discounted-equivalent lot measure equals nominal lots
without reading a curve.

The new bilateral evaluation branch accepts only the supported financial profile. Physical
trades have no modeled payment dates for this purpose and continue to fail rather than
acquire invented financial terms. Market creation and `_PrepareTrades` signatures stay unchanged.

Results retain the exact prepared object, market and supplied curve by reference, the
valuation date, settlement unit and risk convention. Evaluation checks:

1. The market's history is the prepared history, as today.
2. Route and supplied curve agree with the supported profile.
3. The curve date and unpaid payment coverage satisfy the agreed policies.

The internal rate-input function owns curve-date and payment-coverage checks. Report the first uncovered
group in stable group order, its contract/payment date and the curve's range. Keep the
existing index/history and live-price coverage checks. Failure publishes no partial result;
evaluation never silently prepares history again. Gathering current rate inputs is explicit
evaluation work, counted on every call.

Use the host's existing ownership and release machinery. A reference to an old result must
keep its old inputs and answers alive; subsequent price/rate changes cannot mutate them.
No global history or rate cache is required by this design.

## Calculation and compression

Retain the current financial grouping key `(booked contract, payment date)`. With one
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

npv_by_group[g]  = payment_amount[g] * D[g]
dv01_by_group[g] = -0.0001 * tau[g] * D[g] * payment_amount[g]

bilateral_mark = sum(npv_by_group)
dv01           = sum(dv01_by_group)
bilateral_cash = prepared.cash
```

`offset_of_group` is the existing code's name for the signed fixed leg. The above labels
explain the economics; this ticket does not require a repository-wide rename.
Fixed and set floating amounts both receive the payment's factor. Do not discount only
the live portion, and do not discount the batch's already-summed undiscounted mark.

The DV01 is analytic: the derivative of `payment_amount * D` with respect to a parallel rise of
the continuously compounded zero rate, taken on the **already resolved payment-date factor**, so
`-0.0001 * tau * D` per unit of payment is the specification itself. It is no second market
input: bumping sparse curve anchors and interpolating again would give a different number, and
no second trade evaluation or mutated curve is needed.

Keep commodity exposure and NPV sensitivity distinct. With `lot_coefficient` the index's
existing reporting-lot coefficient, compute the following on the stable pricing-contract axis:

```text
nominal_lots[r] = sum(prepared.dated_live_lots[s] for slots referencing r)
discounted_lots[r] = sum(prepared.dated_live_lots[s] * D[group(s)] for slots referencing r)
price_sensitivity[r] = discounted_lots[r] * lot_coefficient

nominal_lots_total = sum(nominal_lots)
discounted_lots_total = sum(discounted_lots)
```

The stable contract axis stays unchanged; fixed contracts retain zero entries. Build the
discounted vector from live slots and their groups, **not** from the nominal contract vector
after it has netted payment dates together. Retain both lot vectors and totals in results;
nominal quantities can be shared with preparation. Monetary `price_sensitivity` retains
its meaning as the NPV change for one quote-unit move and therefore is discounted for
bilateral trades. Nominal lot exposure must not quietly acquire a new meaning by route.

For example, 10 fully live lots of 1,000 units each, fixed price 70, current price 74 and
one payment DF of 0.98 gives payment 40,000, NPV 39,200, nominal delta 10 lots and
discounted delta 9.8 lots. A commodity quote move changes the payment and NPV, but neither
lot delta in this linear model. A DF change changes discounted lots while nominal lots stay put.

Paid groups have zero remaining NPV, commodity delta and DV01. Their full signed amount is
cash, even when their payment date predates the supplied curve. A fully fixed but unpaid
group has zero commodity delta but generally nonzero DV01. A zero-rate curve with all
factors equal to 1 still has bilateral rate sensitivity, `-0.0001 * tau` per unit of payment.

## Preparation and tick work

Evaluation gathers factors once per distinct unpaid payment date, maps them to groups,
computes the time fractions and builds discounted delta. Distinct dates and group
mappings come from stable encoded/prepared state rather than repeated trade interpretation.
Time fractions depend on valuation date and payment dates; work already held in preparation
may be reused without a new public step. Record exactly what is computed and what is reused.
Do not copy or scan the full daily curve, expand a dense trade-by-date matrix, or repeat
unit conversion and schedule work. No hidden cache is part of the initial design.

Performance is an explicit acceptance concern. Count groups, distinct unpaid dates and live
slots, as well as operations over them; none is guaranteed to be a small constant. Different
payment dates can leave one group per component. Include concentrated portfolios and
portfolios with many payment dates, plus long Asian schedules and partial fixing states.
Report retained and temporary array bytes alongside work counts. Compare the added work
with the current cleared baseline before deciding whether a reusable binding is worthwhile.

For the first implementation, evaluate live contributions once, reduce them into the
existing payment groups, form group amounts, then calculate group NPV and DV01 together.
Both measures share the same price read and amounts. Adding the already prepared fixed and
set vectors is arithmetic, not another traversal of trades or history. More aggressive
compression into rate-weighted contract vectors can follow measurements; it is not required
to establish the correct payment amounts and stored contributions in this slice.

| Change | Reuse | Recalculate |
|---|---|---|
| Commodity price tick | Trades, history preparation and nominal delta | Live group amounts, rate gathering/weighting, discounted delta, mark, DV01 and result snapshot; both lot deltas numerically unchanged for the same curve/history |
| Discount curve update, same as-of/history | Trades, history preparation and nominal delta | Evaluation including rate gathering, discounted delta, mark, DV01 and result snapshot; no fixing reads |
| Fixing correction | Static trades/encoding; curve may remain the same if its date still matches | History preparation and evaluation; a corrected paid amount can change cumulative modeled cash |
| Valuation-date roll | Static trades/encoding | History preparation and payment status, a matching curve under the agreed date policy, evaluation |
| Ticket or template change | Independent market inputs where compatible | Trade creation and all dependent preparation/results |

A price tick **can change DV01** because it changes future payment amounts. A rate tick
**can change discounted commodity delta**, but not nominal delta, because it changes the
value of receiving that exposure on its payment date. Test these dependencies explicitly.

## Saved results and readers

Retain aggregate mark, cash, both lot-delta totals and DV01, plus the following immutable arrays or
references. Names and record placement below describe required meaning, not new public fields.

| Content | Axis and meaning |
|---|---|
| Nominal lot delta | Existing stable contract axis, remaining exposure in reporting lots; shared with preparation; zero after fixing |
| Discounted lot delta | Same stable contract axis; payment-weighted live lots summed by pricing reference; zero after fixing |
| Monetary price sensitivity | Same axis; NPV sensitivity in settlement currency per quote unit, consistent with discounted lots and the reporting-lot coefficient |
| Payment amounts and NPV contributions | Existing payment-group axis; paid groups have zero NPV and their nominal amount remains inspectable |
| DV01 contributions | Existing payment-group axis, paid entries zero; additive contributions to the **same parallel rise**, the analytic derivative per group, not independent curve-node or market-quote sensitivities |
| Dated live contributions | Preserve today's slot-level undiscounted price-times-exposure meaning; retain resolved payment factors and their mapping for inspection |
| Context | Prepared trades, commodity market, supplied curve, as-of, route, settlement unit, both risk bases and precise DV01 convention |

There is one curve-level DV01 total in this slice. Keep its payment contributions as a
vector so later inspection does not require repricing; do not mislabel those contributions
as key-rate risk. Keep both commodity lot-risk vectors too. No per-trade results or dense
group-by-contract matrix are required.

Result contribution vectors use the full, stable payment-group axis. Results may keep
factors only for unpaid groups with a mapping; do not invent discount factors for paid groups.

`_ReportValues` already derives its mark/cash headers from route. The risk readers expose both
lot measures as distinct columns, agreed: `nominal_delta`, the remaining exposure in reporting
lots as today, and `delta`, the discounted lots the desk hedges to, in the scalar risk report and
in the day, month and year buckets alike; no basis selector. The current risk layout changes by
those columns and by the DV01 beside them.
In particular, `_ReportDelta` currently reads nominal day/month/year buckets from preparation:
it must not label those as discounted or silently disagree with the scalar risk report.
Any reported discounted time buckets must be computed during evaluation and saved, preserving
payment ownership until after weighting. DV01 help must state its direction, a one basis point
rise, its ACT/365F time basis and its units. `util_ReadHandle` shows stored contents and their axes/conventions for inspection.
Readers access no current markets, gather no factors, reprice nothing and calculate no
missing total. Combining separate evaluated batches is outside this slice.

## Independent acceptance examples

These targets use the agreed analytic convention, `-0.0001 * tau * D * payment_amount` per unpaid
group. Record explicit tolerances,
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

| Group | Nominal lots (one-unit reporting lot) | Fixed leg | Live floating leg | Net payment | DF | NPV | Discounted lot contribution | DV01 contribution |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | +10 | -700 | +800 | +100 | 0.95 | +95 | +9.5 | -0.0095 |
| B | -10 | +700 | -800 | -100 | 0.90 | -90 | -9.0 | +0.018 |
| Aggregate | 0 | 0 | 0 | 0 | — | **5** | **0.5** | **+0.0085** |

This fixture catches compression before discounting and loss of payment ownership.

| Change from the base case | Mark | Cash | Discounted lots | DV01 |
|---|---:|---:|---:|---:|
| Price 80 to 81, same curve | 5.5 | 0 | 0.5 | +0.00935 |
| DFs 0.96 / 0.92, price still 80 | 4 | 0 | 0.4 | +0.0088 |

Nominal aggregate lot delta remains zero in both changes; retain it alongside discounted lots.

Use an additional off-anchor case: curve anchors at day 0, DF 1, and day 730, DF 0.90.
The day-365 factor is 0.95, linear on the factor, and a +100 payment's DV01 there is -0.0095:
the derivative is taken on the resolved factor, never by bumping the anchors and interpolating
again, which would give another number.

### Live, fixed and paid

One exposure +10, fixed price 70, observation on day 0, payment on day 365. Use fresh
all-one curves starting on each valuation date. Choose a synthetic calendar where the
observation and payment are valid business dates. The market must retain a later unused
contract so these fixtures do not depend on the deferred entirely-ended-calendar case.

| State | Mark | Cash | Nominal and discounted lots (DF = 1) | DV01 |
|---|---:|---:|---:|---:|
| Day 0, price 80; observation still live on its own day | 100 | 0 | 10 | -0.01 |
| Day 0, price ticks to 81 | 110 | 0 | 10 | -0.011 |
| Day 1, prior observation fixed at 82 | 120 | 0 | 0 | -0.0119671232877 |
| Day 364, fixed and still unpaid | 120 | 0 | 0 | -0.0000328767123288 |
| Day 365, modeled paid | 0 | 120 | 0 | 0 |

Day 1 uses 364/365 years, not one year. Add a non-unit-factor fixed-but-unpaid case:
payment 120 and DF 0.99 gives mark 118.8, then full cash 120 on the payment date.
Include a batch with one group paid and another unpaid, and a correction of a known fixing.

### Properties, boundaries and work

- Batch equals the sum of compatible singletons for all measures and aligned risk vectors;
  permutation preserves economics and duplicate occurrences count. Include mixed methods,
  month/calday quantities, unit selections, signed and zero quantities, strips and partial Asians.
- Discounted lots times the reporting-lot coefficient match an independent one-quote-unit
  move in each reference; nominal lots match the live observation weights. DV01
  matches the independent sum of `-0.0001 * tau * D * payment` over the unpaid groups, computed
  in the test from the resolved factors and day counts, not by the production code. Include a
  leap-day span.
- Same-payment-date groups can aggregate without changing answers; different dates stay
  distinct. A net-zero amount can still have commodity delta, and a raw-zero contract delta
  can become nonzero after discounting. Zero quantities retain normal validation.
- Missing curve, the wrong preparation/history, wrong curve start and uncovered unpaid
  dates fail loudly. A fixed unpaid date still needs coverage. An all-paid batch accepts a
  matching one-day curve, reads no payment factors, returns only nominal cash and zero risks.
- Cleared numerical expectations stay unchanged. Cleared plus a curve and bilateral
  physical valuation fail by profile. Preserve all current missing-fixing and coverage refusals.
- Work/allocation budgets distinguish components, slots, groups, distinct unpaid dates and
  live references. A commodity tick reads each distinct live reference once, folds no fixings,
  rebuilds no schedules/conversions/payment dates, and counts factors gathered, groups valued,
  live slots discounted and risk aggregations on every evaluation. Count time fractions where
  actually computed; do not preserve the superseded zero-rate-work
  tick budget. Readers perform no valuation. Rate-only changes do not rebuild trade encoding
  or history preparation. Use counts and allocation evidence, not timing gates; do not claim
  acceptable performance from vectorization alone.
- Lifetime tests retain an old result across price/rate ticks, then roll history and recover
  from failed rate inputs. Assert immutable old answers and release when owners disappear.

## Delivery

Treat this as a small feature arc above the reviewed prototype, not an instruction to merge
the stack. The first PR is agreed as rename-only; remaining PR boundaries can be refined:

1. **Instrument rename only:** [rename `future` to `fixed_float`](rename-instrument-fixed-float.md), built in #174,
   migrating discovery, templates, help, tests and kept workbook callers. Preserve the
   entire current schema and numerical behavior; no new fields or bilateral valuation.
2. **Representation additions:** the agreed counterparty and marketing-reserve fields, built in #175,
   preserving static encoding and the stated reserve treatment.
3. **Bilateral evaluation and risks:** settle the outstanding conventions and reader contract,
   add the optional curve argument and private rate-input arithmetic, complete valuation and
   all three risk measures, retain vectors/context, and pin work/allocation and lifetime tests.
   No public `_PrepareDiscounting` function or handle is part of this slice.
4. **Surface acceptance:** independent examples through registered functions and the kept
   workbook, with corresponding smoke/host checks, public help, kernel and result docs.
   These checks may accompany the relevant implementation PR rather than form another PR.

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
distinctions, not our particular choice of sign, ACT/365F or analytic parallel rise; those
are the explicit local conventions proposed above.
