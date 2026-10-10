# Bilateral calculation kernel

[Pipeline overview](README.md) · [Bilateral agreement](bilateral-discounting-and-dv01.md) ·
[Preceding booking-fields ticket](booking-fields-and-marketing-reserve.md) ·
[UAT notes](surface-uat-notes.md)

**Status:** Built in #176, 10 October 2026, stacked on PR #175 at `529bc27`, awaiting review, the
owner having aligned on 10 October: a bilateral path inside the existing evaluation function, no
new public function or stage. [As built](#as-built) at the foot records what the build settled.
This is a calculation ticket, not permission to merge the prototype stack.

**Suggested PR title:** `feat(trades): calculate bilateral NPV and risk`

## Outcome and PR boundary

Prove the bilateral financial calculation using the existing static trades, history
preparation, commodity market and one explicitly supplied discount curve. Produce the
batch's unpaid NPV, nominal paid cash, nominal and discounted lot delta, and signed DV01,
with the vectors needed for later reporting. One trade and many use the same path.

This PR builds private library functions and tests. The following PR adds the optional
curve to `_EvaluateTrades`, publishes the completed result through Excel and updates
the readers. Until then the existing public bilateral-evaluation refusal remains.
No new worksheet function, handle or `_PrepareDiscounting` stage is introduced here.

## Inputs and responsibilities

An illustrative private entry point is:

```text
bilateral_calculation(prepared, market, discount_curve, counter) -> calculation
```

Names and record placement are engineering choices. This should be a small coordinator
over typed array operations, not another trade-resolution or fixing pipeline.

| Input | Already provides |
|---|---|
| `prepared` | Encoded payment groups, fixed leg, fixed floating amounts, live dated slots, nominal lot vectors, paid status and nominal cash |
| `market` | Current quotes for the distinct live pricing contracts; its history must be the exact prepared history |
| `discount_curve` | Existing immutable daily `DiscountCurve`, built through the current curve builder |
| `counter` | Counts of work actually performed |

Support `fixed_float`, `route = bilateral`, `settlement_method = financial`, using the
currently supported index kinds and schedule methods. Preserve one index, currency and
route per batch; one supplied curve applies to every payment group. Counterparty is
attribution and does not choose a curve. The curve has no currency metadata: explicit
supply associates it with this batch, without pretending to validate its source currency.

Reuse the existing private evaluator and live-price arithmetic where practical; the
illustrative entry point does not require a second evaluator or parallel results model.
Extending the private evaluator before exposing its curve argument is also acceptable.
If a shared helper needs extracting, keep that refactor identifiable and preserve cleared
numerical results and work budgets. Do not create a second interpretation of the trade
or call the cleared evaluator and discount its final scalar.

## Curve and payment rules

1. `as_of` is the prepared history's valuation date. Require
   `discount_curve.start_date == as_of`, including for an all-paid batch. No rebasing,
   clock lookup or use of `day_fraction_elapsed`.
2. Use each **payment date**, not its observation dates, to select the DF. Gather once
   per distinct unpaid payment date and map those factors to the existing groups.
3. Every unpaid group needs coverage, including fixed-but-unpaid and zero-amount groups.
   Missing coverage fails before returning a result, naming the first affected group in
   stable order, its booked contract/payment date and the available curve range.
4. Keep preparation's paid-state rule: all observations fixed and payment date on or
   before `as_of`. Paid amounts belong to cumulative nominal cash, with zero NPV and
   remaining risk. Their policy factor is 1; read no historical DF for them.
5. An all-paid batch still supplies a matching curve; a one-day curve is sufficient and
   requires zero payment-factor reads. Preserve the current market/calendar constraints.

The existing builder guarantees daily, positive, non-increasing factors starting at 1.
Use it unchanged: no extrapolation, new interpolation method, negative-rate support,
zero-rate builder or repeated validation of its entire array. Validate market identity,
the bilateral financial profile, then curve-date/coverage compatibility before calculation.
Keep existing live-price coverage failures. An identity mismatch never silently prepares again.

## Calculate payment amounts before discounting

Keep the existing group key `(booked contract, payment date)` and each dated slot's group
and pricing reference. Discount before compressing different payment dates together.

```text
floating_leg_live[g] = sum(live_exposure[s] * quote[reference(s)] for slots in g)
payment_amount[g]    = fixed_leg[g] + floating_leg_set[g] + floating_leg_live[g]

For unpaid groups:
    D[g]    = curve factor on payment_date[g]
    tau[g]  = actual calendar days from as_of to payment_date[g] / 365
    npv[g]  = payment_amount[g] * D[g]
    dv01[g] = -0.0001 * tau[g] * npv[g]

For paid groups:
    npv[g] = 0
    dv01[g] = 0

bilateral_mark = sum(npv)
bilateral_cash = prepared.cash
dv01           = sum(dv01)
```

`fixed_leg` maps to `encoded.offset_of_group`; `floating_leg_set` maps to
`prepared.set_amount`. Use these group arrays, not the already-summed convenience
values `offset_unsettled` and `set_unsettled`. The entire net unpaid payment is discounted.
Form live contributions once and reuse them for group amounts, NPV and DV01.

DV01 is the **signed analytic sensitivity to a parallel increase in continuously
compounded zero rates, scaled to one basis point**, using ACT/365F. Hold commodity
prices, fixings, dates and terms constant. Positive receivables have negative DV01;
payables have positive DV01. NPV 1,000 one year away gives -0.10 currency units per bp.
Do not bump anchors, reinterpolate, build a second curve or report finite bumped P&L.
Even a curve with all DFs equal to 1 can have bilateral DV01.

## Commodity risk and its axes

Retain preparation's nominal lot vectors and totals by reference. For each live slot:

```text
discounted_lots[s]        = prepared.dated_live_lots[s] * D[group(s)]
discounted_sensitivity[s] = prepared.dated_live_exposure[s] * D[group(s)]
```

Reduce these contributions onto the existing stable pricing-contract axis. Also reduce
discounted lots by observation day, then calendar month and year, using the existing
axis mappings. Fixed entries retain zero rows. Time buckets describe **observations**;
payment dates determine their weights, not their bucket positions.

Weight slots before either contract or day aggregation. Two slots with the same day
and reference but different payment dates can have different factors. The nominal
contract/daily totals have already lost that distinction and cannot be discounted later.
Do not discard a group or slot because its current net payment is zero.

The bilateral `delta` is discounted lots; `nominal_delta` is undiscounted remaining lots.
Monetary price sensitivity is in settlement currency per quote-unit move, not lots.
For each reference it must reconcile with discounted lots times the index's existing
reporting-lot coefficient. Reuse that coefficient; do no unit conversion on a tick.

## Retained calculation output

Keep one immutable calculation for the batch, ready for the following integration PR:

| Contents | Axis or meaning |
|---|---|
| Mark, cash, nominal delta total, delta total, DV01 | Completed scalars in their stated units |
| Nominal and discounted lot vectors | Same stable contract, day, month and year axes; nominal arrays shared from preparation |
| Discounted monetary sensitivity | Stable pricing-contract axis |
| Payment amounts, NPV and DV01 contributions | Full stable payment-group axis; paid NPV/DV01 entries zero |
| Undiscounted dated live contributions | Existing live-slot axis and price-times-exposure meaning |
| Used payment DFs and mapping | Unpaid dates/groups only is sufficient; no historical DF lookup for paid groups |
| Context | Exact prepared, market and curve references; as_of, units, axes and DV01 convention |

DV01's payment vector contributes to one parallel-curve sensitivity; it is not key-rate
risk. Existing reserves are shared unchanged and enter none of the calculations.
Keep source arrays immutable and old outputs stable across later ticks. Internal records
need not duplicate context already reachable by reference. No per-trade outputs or dense
trade-by-date/group-by-contract matrix is required.

Refuse nonfinite monetary amounts, NPV/DV01 contributions, returned totals and newly
computed risk vectors before returning a calculation. Errors identify the failing
quantity and its group/reference/date where applicable; aggregate overflow names the
aggregate. Apply new calculation checks without revalidating all static trade facts.

## Independent worked tests

### Opposite trades paying on different dates

Use the synthetic one-unit reporting lot from the bilateral plan. Both trades reference
the same live contract at 80, with fixed price 70. As-of is 4 January 2027; payments on
4 January 2028 and 3 January 2029 are 365 and 730 actual days later. These are deliberate
test terms, not exchange payment conventions.

| Group | Nominal lots | Payment amount | DF | NPV | Discounted lots | DV01 |
|---|---:|---:|---:|---:|---:|---:|
| A, one year | 10 | 100 | 0.95 | 95 | 9.5 | -0.0095 |
| B, two years | -10 | -100 | 0.90 | -90 | -9 | 0.018 |
| Total | **0** | **0** | | **5** | **0.5** | **0.0085** |

At quote 81, mark is 5.5 and DV01 is 0.00935; both lot measures are unchanged. At quote
80 with DFs 0.96/0.92, mark is 4, delta is 0.4 and DV01 is 0.0088; nominal delta stays 0.
Use the same prepared object for these evaluations. At least one end-to-end library
fixture must create and prepare actual trades rather than hand-construct every array;
the parent plan gives valid synthetic schedules and payment lags for these dates.

Also test an at-the-money live group: +10 one-unit lots, quote and fixed price both 70,
DF 0.95, payment one year away. Mark and DV01 are zero, but nominal delta is 10 and delta
is 9.5. A +1 quote move produces mark 9.5 and DV01 -0.00095.

Pin zero aggregate NPV with nonzero DV01 too: the original +100/-100 payments at
one/two years, both with DF 0.90, give mark 0 and DV01 +0.009. Do not derive DV01 from
the aggregate mark using a single time to payment.

### Fixed is not paid

An observation on 4 January 2027 has +10 exposure at fixed price 70 and pays on
4 January 2028. Use fresh all-one curves anchored on each valuation date:

| State | Mark | Cash | Nominal and discounted lots | DV01 |
|---|---:|---:|---:|---:|
| Observation day, quote 80 | 100 | 0 | 10 | -0.01 |
| Next day, fixing 82 | 120 | 0 | 0 | -0.0119671232876712 |
| Payment day | 0 | 120 | 0 | 0 |

With DF 0.99 in the fixed-unpaid state, mark is 118.8; payment later moves the full 120
to cash. Cover mixed paid/unpaid groups, a fixing correction and paid dates before the
curve starts. Keep a later unused contract in market fixtures so the tests do not depend
on support for an entirely ended calendar.

### Axes and refusals

- Pin individual contract and day/month/year entries with independently calculated
  expectations: two pricing references, observation dates across a month and year end,
  same-day slots with different payment dates, and fixed zero entries. Totals alone
  cannot reveal a value assigned to the wrong date or contract.
- Reconcile each nominal/discounted vector to its own scalar; batch equals aligned
  singletons, permutations preserve economics and duplicates count. Cover mixed methods,
  units, quantity bases, strips, partial Asians, signed and zero quantities.
- Require unpaid DF coverage even when amount or exposure nets to zero. Test matching
  start, mismatched start, first/last covered dates, first uncovered payment, fixed-unpaid
  coverage, all-paid one-day curve and no-live-price work. Existing market identity and
  unsupported-profile refusals remain explicit.
- Test an interpolated payment DF, not only curve anchors, and a leap-day span under
  ACT/365F. Expected DV01 comes from hand differentiation of payment PV. A diminishing
  central-difference check is supplementary; production output is the analytic measure.

Use documented floating-point tolerances, including cancellation-heavy batches. Expected
answers must not be generated by the helper being tested or taken from workbook caches.

## Work and completion

Keep static payment-date/group mappings in encoding or history preparation; no curve
values live there. No schedule, date parsing, unit conversion, fixing reads or nominal
risk rebuilding on a commodity or curve tick. Gather only needed quotes and payment DFs;
do not copy or scan the entire daily curve.

Initially each evaluation performs rate gathering, group valuation and discounted-risk
aggregation again, even if the same curve is supplied. Count that work honestly rather
than introducing a hidden cache. Record quote reads, distinct unpaid DFs, groups valued,
live slots weighted, time fractions/DV01 weights computed and risk reductions, with
retained and temporary array bytes. Existing reused values cost no recomputation count.

Pin workloads with many trades/few groups and many distinct payments, plus long Asian
schedules and partial fixing. Paid groups require no DFs and fixed groups no live quote.
Compare the new work with the unchanged cleared baseline; use counts/allocation evidence,
not timing gates. A curve-only change still runs the same evaluation path initially.

Deliver private kernel tests, meaningful work-budget tests and updated kernel/design
documentation. Run `check.ps1`; review existing golden changes separately. Public
signatures, report headers, workbook examples and Excel ownership/lifetime integration
belong to the next PR. This ticket is complete when the financial targets and work
boundaries are proven privately, with existing cleared behavior preserved.

Before engineering starts, confirm this PR boundary with the owner: the calculation
returns both delta bases and analytic DV01 now; the next PR makes those available on
the sheet. Rates, risk and curve-date meanings above carry forward the existing agreement.

## As built

PR #176 on `claude/bilateral-kernel`, stacked on #175. The page is
[kernel.md](../../library/trades/kernel.md#the-bilateral-path), with
[evaluate-trades.md](../../library/trades/evaluate-trades.md) for what the worksheet function does
and does not do yet; the seam's record is the #176 row of [history.md](../../seam/history.md).

- The owner's three clarifications, kept: the cleared tick's ledgers did not move and a cleared result
  shares the preparation's nominal arrays under the discounted names, its group vectors `None`; the
  counter reports factors read once per distinct unpaid payment day, groups valued, live slots
  weighted and reductions, with the peak and the retained bytes pinned beside; the tests hold the hand
  figures to `rtol=1e-12, atol=1e-12`, the absolute part justified by the cancelling batches whose
  mark is 0 exactly, and the tolerance stated per measure in the test module's docstring.
- The entry point is `trade_results(prepared, market, counter, curve=None)` in `trades/evaluation.py`,
  with `_the_curve` for the rules and `_discounted` for the bilateral snapshot; `_EvaluateTrades`
  passes no curve yet, so a bilateral batch is refused there asking for one, `discount_curve is
  missing, expected a discount curve with a bilateral batch, whose payments it discounts`, the words
  the seam will give once the argument exists.
- The rules, in order: a cleared batch with a curve refused; a physical bilateral batch refused; the
  curve required; its start the valuation date, `discount_curve starts on 2027-01-05, expected
  2027-01-04, the valuation date; a curve is never rebased`; every unpaid payment day covered, `the
  payment of F27 on 2029-01-03 is past the discount curve, which runs from 2027-01-04 to 2028-12-31;
  expected every unpaid payment day covered`.
- The arithmetic as specified: `npv[g] = amount[g] * D[g]`, `dv01[g] = -0.0001 * tau[g] * npv[g]`, the
  factor read by position on the daily curve once per distinct unpaid day, paid groups at the policy
  factor of one with nothing read; discounted lots per live slot before the sums by reference, day,
  month and year; the discounted sensitivity the lots times the reporting lot's coefficient.
- `TradeResults` gains `curve`, `discounted_lot_delta`, `discounted_lot_delta_total`,
  `discounted_price_sensitivity`, the three discounted time views, `payment_amount`, `npv_by_group`,
  `dv01_by_group` and `payment_factor`; the readback and the reports are untouched.
- The figures pinned in `tests/unit/test_bilateral_kernel.py`: the two groups, 5 / 0.5 / 0.0085, the
  tick 5.5 / 0.00935, the second curve 4 / 0.4 / 0.0088, the at-the-money 0 / 10 / 9.5 and 9.5 /
  -0.00095, both at 0.90 giving 0 and +0.009, fixed-is-not-paid 100 / -0.01, 120 / -0.0119671232876712,
  118.8, then cash 120, the axes on interpolated factors over two references and a year end, the
  singletons, the order, the duplicate, the cleared sharing, and the two trades made through the
  creators with `+261bd` and `+522bd`.
- Counts: the bilateral tick 8 functions and 13 numpy calls at five trades and at two thousand, against the cleared tick's 4 and
  4, which did not move; the counter one factor per distinct unpaid payment day, one unpaid group, one live slot and 4
  reductions; the peak 3,608 bytes for two groups and 7,600 for twenty-four with twenty live slots, within 128 a group, 48
  a live slot and four slacks, against 1,210 and 1,418 cleared; the retained arrays exactly the new vectors' bytes. The
  Python tests 2,528 to 2,543, the smoke 976 formulas to 976, the host's 314 to 314, the lifetime's 128
  unchanged; the workbook's one refusal text recalculated.
- Not done, as the ticket keeps separate: no curve argument on `_EvaluateTrades`, no reader column, no
  workbook example of a bilateral value; the public bilateral refusal reworded only, in the smoke, the
  host and the kept workbook. No golden file changed.
