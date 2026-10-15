# Bilateral valuation and risk in Excel

[Pipeline overview](README.md) · [Bilateral agreement](bilateral-discounting-and-dv01.md) ·
[Calculation kernel](bilateral-calculation-kernel.md) · [UAT notes](surface-uat-notes.md)

**Status:** Built in #177 on `claude/bilateral-excel`, stacked on the reviewed PR #176 at
`7557d8b`, 11 October 2026; owner UAT follows. The final planned implementation slice of the
first bilateral arc. PR #176's review fixes, the finite-output guards and the payment-date
mapping made once at preparation, are in that PR and carried forward untouched here. PR #175
supplies the booked fields.

**Suggested PR title:** `feat(excel): expose bilateral valuation and risk`

## Outcome and dependency

Let a user evaluate bilateral financial trades on a sheet by supplying the current
discount curve to the existing evaluation function. Return complete saved results and
read their values, nominal and discounted lot delta, and analytic DV01 through the
existing reports. One trade and many use the same path.

This PR connects the corrected kernel to Excel. The bilateral calculation remains a
path inside the existing evaluator, with private helpers as needed. There is no new
public evaluation function, preparation stage, handle kind or reader basis selector.

Keep the PR #176 fixes in that PR: refuse nonfinite returned amounts, totals and risk
vectors; retain stable payment-date/group mappings outside the tick; and exercise the
work and allocation budgets with distinct payment dates and long Asian schedules.
Carry those fixes forward without recreating their arithmetic or guards in the seam.

## Public functions

```text
_CreateTradeTemplate(instrument, fields, values) -> template
_CreateTrades(index, fields, trade_rows, template) -> trades
_PrepareTrades(trades, history) -> prepared
_EvaluateTrades(prepared, market, [discount_curve]) -> results

_ReportValues(results)
_ReportRisk(results)
_ReportDelta(results, [bucket])
_ReportReserves(results)
util_ReadHandle(results)
```

Only `_EvaluateTrades` gains an argument, optional and last. Use the seam's existing
optional-handle declaration, `Handle[DiscountCurve] | None = None`, and the existing
discount-curve creator. The seam resolves the supplied handle once and passes its object
to the private evaluator. The private parameter's name/order is not a second public API.

| Evaluated route | Curve argument | Valuation behavior |
|---|---|---|
| Cleared | Omitted | Existing undiscounted mark/cash; both lot-delta measures equal; DV01 zero |
| Cleared | Supplied | Refuse; do not ignore a supplied curve |
| Bilateral financial | Supplied | Payment-date discounted mark, nominal cash, both lot-delta measures and signed DV01 |
| Bilateral financial | Omitted | Refuse, including when every payment is already paid |
| Bilateral physical | Either | Existing unsupported-profile refusal; no invented payment terms |

Omission remains different from a blank cell. Blank, empty text, a number, a dead handle,
a handle of the wrong kind and a creator's failure follow the existing seam rules.
The library owns route, settlement, identity, curve-date and coverage rules. Preserve
the kernel's validation order after the seam has checked the arguments. A failed
evaluation publishes no result; downstream readers receive the existing failure behavior.

There is one explicitly supplied curve per evaluated batch. The curve is a changing
market input, not a trade/template field or a selection inferred from counterparty.
No implicit default, global curve, rebasing or silent re-preparation is introduced.

## Existing economic rules carried through the surface

- The market's history must be the exact prepared history. The curve starts at that
  history's `as_of`. A date mismatch fails, including for an all-paid batch.
- Each unpaid payment group uses its own payment-date factor before aggregation.
  Every unpaid date needs coverage, including fixed-but-unpaid and zero-amount groups.
  Missing coverage fails rather than extrapolating or substituting 1.
- Paid amounts are cumulative nominal cash, with no historical factor lookup and
  zero remaining NPV or risk. An all-paid batch still supplies a matching curve;
  a one-day curve is sufficient. Keep the existing market/calendar support limits.
- `nominal_delta` is remaining undiscounted exposure in the index's reporting lots.
  `delta` is the exposure weighted by the route's valuation treatment: identical for
  cleared, payment-date discounted for bilateral.
- DV01 is the signed analytic sensitivity to a parallel +1 bp rise in continuously
  compounded zero rates, ACT/365F: `-0.0001 * tau * NPV` per unpaid group, summed.
  Receivables have negative DV01 and payables positive. A zero-rate curve can still
  have DV01. No curve bump or second evaluation takes place in a reader.
- Brokerage, clearing and marketing remain booked reserves. They affect neither
  mark/cash nor risk and do not change when a curve, quote, fixing or payment changes.

The curve currently carries no currency metadata. Explicit supply associates it with
the batch's settlement currency; do not claim independent source-currency validation.

## Exact report contracts

Preserve the existing header row, type row and data-row format. Both routes use the same
risk layouts. These are read operations on completed results, with no market access,
factor gathering, valuation, unit conversion, risk summing or handle publication.

### Values

`_ReportValues(results)` stays three rows by four columns:

```text
cleared_mark   | cleared_cash   | currency | as_of
bilateral_mark | bilateral_cash | currency | as_of
```

Those are the alternative header rows selected by route, not two rows in one report.
The type row stays `float64 | float64 | str | datetime64[D]`; the final row holds the
stored scalars. Bilateral mark is unpaid NPV, and bilateral cash is nominal paid cash.

### Aggregate risk

`_ReportRisk(results)` becomes three rows by six columns:

```text
nominal_delta | delta   | delta_unit | dv01    | dv01_unit | as_of
float64       | float64 | str        | float64 | str       | datetime64[D]
```

The third row contains the stored totals. Both deltas use the same reporting-lot unit.
DV01 is in the settlement currency unit per basis point, for example `USD per basis point`.
Replace the current `delta_total` header with this layout; do not retain an alias column.

In the reviewed kernel, `lot_delta_total` is nominal and
`discounted_lot_delta_total` is valuation-weighted. Read the corresponding saved values;
do not assume an internal field named `lot_delta` already means bilateral discounted risk.

### Risk by observation time

`_ReportDelta(results, [bucket])` has five columns and two heading rows plus one row per
stored bucket:

```text
bucket_start  | nominal_delta | delta   | delta_unit | as_of
datetime64[D] | float64       | float64 | str        | datetime64[D]
```

Keep `bucket = day | month | year`, the existing day default and exact accepted spelling.
The two columns use the same existing chronological observation-time axis. Fixed dates
keep their zero rows. Payment dates determine discount weights, not the bucket labels.
Each column reconciles to its corresponding scalar and contract vector.

Select nominal vectors retained through preparation and discounted vectors saved by
evaluation. Today's nominal-only `bucketed(prepared, ...)` cannot supply both bilateral
columns. Cleared results may share the same immutable arrays for the two bases. There
is no new selector, sorting, summation or discounting inside this reader, and no DV01
column in the time-bucket report.

### Reserves and debugging

`_ReportReserves` keeps its existing signature, layout and booked totals.

Extend `util_ReadHandle(results)` to make the bilateral snapshot inspectable through
the existing debug surface. Preserve the undiscounted meanings of `live_coefficient`,
`live_lots` and `live_contribution`. Distinguish nominal contract risk from discounted
contract risk explicitly in the column names/help; an existing nominal field must not
silently become a discounted one.

Expose the retained payment factors, payment amounts, group NPV and group DV01 with
their booked contract/payment-date ownership. Prefer showing an additive group amount
once per group, with the existing dash convention on its other slot rows, so summing
displayed amounts does not count the same payment repeatedly. A factor can repeat on
its group's slots. Keep reserves shown once per batch as today. Pin the chosen debug
layout and explain any repeated contract-level values; this is a view of saved data,
not trade-level valuation or a new decomposition calculation.

For cleared results, do not manufacture curve/group arrays solely for readback. Their
bilateral-only fields may remain absent, as the kernel allows. Selecting and formatting
stored values is permitted; calculating missing risk or contributions in a reader is not.

## Worked worksheet acceptance

Reuse the kernel's synthetic one-unit reporting lot and valid creator fixture. On
4 January 2027, two F27 components have quantities +10 and -10, fixed price 70 and
current quote 80. They pay on 4 January 2028 and 3 January 2029, 365 and 730 days later,
using the fixture's `+261bd` and `+522bd` payment lags. Curve anchors are 1 at as_of,
0.95 at the first payment and 0.90 at the second. These are test terms, not exchange rules.

| State | Bilateral mark | Cash | nominal_delta | delta | DV01 |
|---|---:|---:|---:|---:|---:|
| Base quote 80, DFs 0.95 / 0.90 | 5 | 0 | 0 | 0.5 | 0.0085 |
| Quote changes to 81, same preparation and curve | 5.5 | 0 | 0 | 0.5 | 0.00935 |
| Quote 80, replacement curve with DFs 0.96 / 0.92 | 4 | 0 | 0 | 0.4 | 0.0088 |

There is one observation day, so its nominal and discounted daily entries are 0 and
0.5 in the base case. Month and year reports have those same amounts under their
respective bucket-start dates. Readback retains both payment groups even though their
nominal aggregate exposure and payment amount net to zero.

Also keep a one-receivable lifecycle: +10 at 70, observation on 4 January 2027, payment
on 4 January 2028. With fresh all-one curves anchored on each as_of:

| State | Mark | Cash | nominal_delta | delta | DV01 |
|---|---:|---:|---:|---:|---:|
| Observation day, quote 80 | 100 | 0 | 10 | 10 | -0.01 |
| Next day, fixing 82, still unpaid | 120 | 0 | 0 | 0 | -0.0119671232876712 |
| Payment day, one-day curve | 0 | 120 | 0 | 0 | 0 |

At a payment DF of 0.99 in the fixed-unpaid state, mark is 118.8; the eventual cash
remains 120. A cleared version needs no curve and reports equal delta columns and zero
DV01. Include unchanged reserve totals in the demonstrations.

Use valid histories and a later unused contract so an entirely ended calendar does not
become a new dependency. Keep both tick types and the live/fixed-unpaid/paid states in
the workbook. Registered-surface tests additionally cover a rolling Asian, multiple
observation months/years, differing payment dates on the same observation day, and
mixed entry units/bases. Each delta basis must reconcile independently on every axis.

Expected financial answers come from the independent worked examples, not copied
implementation results or workbook caches. Carry the reviewed relative and absolute
tolerances forward, with cancellation cases and units documented.

## Dependencies and lifetime acceptance

Use the existing host ownership model. Prove the following with the worksheet chain:

| Change | Required behavior |
|---|---|
| No inputs change | Existing reuse; no new calculation/publication merely to read a report |
| Commodity quote changes | Reuse trades and preparation; evaluate against the new market and current curve |
| Only curve values change | Reuse trades, preparation and commodity market; evaluate against the new curve |
| Fixing changes | Build the new history/preparation, then evaluate; use the same curve if its date still matches |
| as_of advances | New history/preparation and matching curve; stale curve fails visibly |
| Curve fails validation, then is repaired | No partial results; normal failure propagation and recovery without leaking publications |

Hold an old results handle while price/curve inputs change. Its old values, vectors and
referenced curve remain unchanged and readable. Releasing the last owners releases the
appropriate publications; a retained snapshot must stay valid. Test closing the workbook
as well as dropping/replacing live results. Do not add caches or alter ownership rules.

Initially either tick reruns the kernel's rate gathering and discounted-risk arithmetic.
It does not resolve trades, convert units, rebuild payment-date mappings, reread fixings
or reconstruct nominal risk. Readers perform none of that work. Measure the additional
handle resolution and spill allocation honestly; wider reports need more output cells,
while the cleared kernel's calculation budget remains unchanged.

## Migration and completion

Update function metadata/help, active evaluation/report/debug pages, registered-surface
tests, host replay, smoke, lifetime scripts and the kept workbook together. Migrate both
header-based and positional consumers of the risk spills. Reserve sufficient worksheet
space for the sixth scalar-risk column and fifth time-risk column; no `#SPILL!` or stale
`INDEX` positions are acceptable. Do not preserve retired report headers as aliases.

Exercise all curve-argument failures through the seam, and prove the kernel's uncovered
date, zero-amount coverage, mismatched-history, mismatched-as_of and unsupported-profile
refusals reach the sheet without publishing results. Check actual booleans/date/numeric
cell types, saved-array immutability, one/many cardinality, and no reader-side arithmetic.

Run `check.ps1` and the kept workbook's recalculation/comparison workflow. Review existing
golden changes separately under the project's golden rule. Record the corrected PR #176
base and the delivered signature, layouts and work counts. Update the overview/UAT rows
selectively; do not replace current branch documents wholesale with older draft copies.

Completion means the existing create -> prepare -> evaluate -> report pipeline works
on a sheet for both routes, with the financial cases and dependency behavior above
verified and the owner able to perform bilateral UAT. UAT completion and stack landing
are separate from implementing this ticket.

Cross-result risk aggregation, multiple curves per batch, counterparty curve selection,
key-rate DV01, new instruments/schedules, negative-rate curve support and a separate
public rate-preparation function remain outside this first bilateral arc.

## As built

PR #177 on `claude/bilateral-excel`, stacked on #176. The pages are
[evaluate-trades.md](../../library/trades/evaluate-trades.md), [report-risk.md](../../library/trades/report-risk.md),
[report-delta.md](../../library/trades/report-delta.md) and [report-values.md](../../library/trades/report-values.md),
with [kernel.md](../../library/trades/kernel.md#the-bilateral-path) for the arithmetic; the seam's
record is the #177 row of [history.md](../../seam/history.md).

- The signature: `_EvaluateTrades(prepared, market, [discount_curve])`, the curve declared
  `Handle[DiscountCurve] | None = None`, decision 39's form, resolved once by the seam and handed to
  `trade_results`; left out is nothing, a blank, empty text, a number, a dead handle and another
  kind are the seam's refusals in its words, `discount_curve is blank, expected discount curve
  handle`, and the library's rules follow in the kernel's order, a cleared batch given a curve,
  a physical bilateral batch, the curve missing, its start day, its coverage.
- The layouts, exactly as specified: `_ReportRisk` three rows by six, `nominal_delta | delta |
  delta_unit | dv01 | dv01_unit | as_of`; `_ReportDelta` five columns, `bucket_start |
  nominal_delta | delta | delta_unit | as_of`, over `bucketed(results, bucket)` in
  `trades/evaluation.py`, which selects the preparation's nominal view and the result's discounted
  view by reference; `_ReportValues` and `_ReportReserves` unchanged in shape, the values under
  `bilateral_mark` and `bilateral_cash` for the route. No `delta_total` alias.
- The debug readback, `util_ReadHandle(results)`, 22 columns for a financial batch: the slot's
  columns, `is_fixed`, `live_coefficient`, `live_lots`, `live_contribution`,
  `contract_sensitivity`, `contract_discounted_sensitivity`, `contract_lot_delta`,
  `contract_delta`, `sensitivity_unit`, `lot_unit`, `payment_factor`, `payment_amount`,
  `group_npv`, `group_dv01`, `brokerage_reserve`, `clearing_reserve`, `marketing_reserve`,
  `currency`. The four contract columns repeat the contract's number on each of its slots and
  say so; the factor is on every slot, its group's; the amount, NPV and DV01 appear once per
  group on its first slot row with a dash on the group's other rows; a cleared result shows a
  dash in the four payment columns on every row and its discounted twins are the nominal arrays.
- The worked acceptance on the sheet, `tests/unit/test_trade_valuation.py`: the two groups 5 / 0 /
  0 / 0.5 / 0.0085, the tick 5.5 / 0.00935, the replacement curve 4 / 0.4 / 0.0088; the one
  receivable 100 / 0 / 10 / 10 / -0.01, then 120 / 0 / 0 / 0 / -0.0119671232876712, 118.8 at
  0.99, then 0 / 120 / 0 / 0 / 0 on a one-day curve; the cleared twin's equal deltas and zero
  DV01; the marketing reserve of 5 a row unchanged throughout. The registered-surface
  reconciliation over a rolling asian across a year end, two payment days on one observation
  day and mixed units and bases: both deltas by day, month, year and contract, the group NPVs to
  the mark and the group DV01s to the DV01, each NPV its amount times its factor.
- The dependency and lifetime cases, `tools/excel_lifetime.ps1 -Groups valuation`: the bilateral
  lot of q26 beside the cleared chain; a quote tick remaking the results and reusing the
  preparation and the curve; a curve-only change remaking the curve and the results and reusing
  the market; a fixing change remaking the history, the preparations and both results and
  reusing the curve; the valuation day advanced with the curve left behind failing visibly in
  the kernel's words and recovering once the curve moves; a curve refused by its creator failing
  the results as its consumer and publishing nothing, recovering when repaired; an old results
  handle held while the curve changes, readable at its old mark, released with its curve when
  dropped; and the workbook closed releasing every publication.
- Counts: a bilateral tick through the seam resolves three handles and runs `trade_results`,
  `_the_curve`, `_discounted` and `Market.live_prices` once each, the same at five trades and at
  two thousand; its peak 5,093 bytes at 2,500 trades over 24 slots against the cleared tick's
  1,418, the time report 4,709 bytes for 24 rows and the risk report 2,079 with its sixth column;
  the kernel's and the cleared tick's ledgers did not move. The Python tests 2,560 to
  2,570, the smoke 976 formulas to 1,078, the host's 314 to 314, the
  lifetime's 128 to 166; the kept workbook's bilateral block in rows 2020 onward.
- Not done, as the ticket keeps outside the arc: no cross-result aggregation, no second curve or
  counterparty-chosen curve, no key-rate DV01, no negative-rate curve, no public rate preparation;
  no golden file exists to change.
