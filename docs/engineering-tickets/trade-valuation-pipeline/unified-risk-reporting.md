# Unified risk reporting with totals first

[Series specification](aggregate-evaluated-results.md) · [Next ticket](aggregate-risk-kernel.md) ·
[Pipeline overview](README.md) ·
[UAT notes](surface-uat-notes.md#12-aggregate-evaluated-results) ·
[Bilateral integration](bilateral-excel-integration.md)

**Status:** Built in #178 on `claude/risk-vectors`, stacked on the reviewed PR #177 at `788e5a7`,
11 October 2026, the page as the ticket; the [As built](#as-built-178) section at the end says
what was built and what was not. The first reporting/aggregation slice, not an extension to
the bilateral integration PR; the owner's answers of 11 October are recorded there.

**PR title:** `feat(excel): report selected risk vectors with totals first`

## Outcome

A user selects nominal delta, discounted delta, DV01 or all three from one evaluated
trade array, explicitly chooses day/month/year, and sees the saved Total above the dated
risk vector. Establish this report before implementing collection of multiple results.

```excel
=_ReportRisk(results,"delta","month")
=_ReportRisk(results,"nominal_delta","day")
=_ReportRisk(results,"dv01","year")
=_ReportRisk(results,"all","month")
```

Use saved results throughout. Neither reporting nor preparing a display may reprice a
trade, read market data, gather discount factors or change the existing risk definitions.

## Public contract and cutover

```text
_ReportRisk(results, risk, bucket) -> mixed table
```

| Parameter | Type / choices | Rule |
|---|---|---|
| results | Handle[TradeResults] | One result of the existing evaluator |
| risk | Text: nominal_delta, delta, dv01, all | Required, exact accepted spelling |
| bucket | Text: day, month, year | Required, exact accepted spelling |

Keep normal seam checks for missing/blank/wrong-type arguments, dead/wrong-kind handles
and creator failures. The library validates selector meaning in argument order. No defaults,
trimming, implicit selection or fallback to all. A scalar-only `total` bucket and a `summary`
selector are not included; the first data row already provides each selected scalar.

Replace the old `_ReportRisk(results)` signature and retire `_ReportDelta` registration,
help and active function page in the same PR. Migrate all kept callers; no aliases or
compatibility wrappers. `_ReportValues`, `_ReportReserves`, creation, preparation and
evaluation signatures stay unchanged. `util_ReadHandle` remains the debug view.

Only TradeResults is accepted in this ticket. The later collector will add a second typed
handle kind to this same reader; do not build that seam extension now or widen to arbitrary
handles. Keep private selection/formatting usable for a collection of saved risk columns,
with this batch as the one-index case. No general reporting framework is required.

## Risk and date meanings

| Selection | Saved values | Dated rows |
|---|---|---|
| nominal_delta | Undiscounted live lots; scalar lot_delta_total | Observation dates |
| delta | Valuation-weighted live lots; scalar discounted_lot_delta_total | Observation dates |
| dv01 | Saved signed payment-group DV01; scalar dv01 | Payment dates |
| all | All three above | Sorted union of observation and payment buckets |

Cleared nominal_delta equals delta. Bilateral delta retains each payment group's discount
weight before summing onto observation dates. DV01 retains the existing analytic parallel
+1 bp zero-rate sensitivity, ACT/365F; payment-date attribution is not key-rate risk.

Day means the date itself; month/year mean the first calendar day of that period. Keep
actual date values, signed netting and all structural zero buckets. The first dated row
is the earliest represented date, which may precede as_of. No full-calendar expansion,
clipping at as_of, rolling observation dates to contract months, or dropping paid dates.

In `all`, the same row label has different meanings by column: delta concerns observations
in that period, DV01 concerns payments in that period. Zero-fill absent intersections of
valid saved axes. Do not substitute zero for missing inputs or failed calculations.

For cleared results, `dv01` has Total = 0 and no dated rate rows. Even a cleared financial
payment date is used for cash treatment, not rate risk. `all` uses observation buckets and
zero DV01. No curve or synthetic payment date is needed. For bilateral results, retain the
full payment-date axis after payments occur, with zero DV01 on paid groups/dates. Existing
bilateral curve requirements, including all-paid as_of matching, stay in force.

## Spill contract

The agreed body is Total first, then dates; risk columns run across. The following heading
arrangement is the concrete proposal for this ticket. It keeps unit/as_of context above
the numbers rather than adding metadata columns to every date row.

1. Context row: `as_of`, the actual valuation date, then `-` in remaining cells.
2. Header row: `period`, then the selected risk-column labels.
3. Type row: `str | datetime64[D]` for period, `float64` for each risk column.
4. First data row: text `Total`, then the corresponding stored scalar(s).
5. Dated rows: actual bucket-start dates and saved vector entries, ascending.

For a synthetic index HNG with reporting unit LOT and a bilateral USD curve:

| as_of | 4 Jan 2027 | - | - |
|---|---|---|---|
| period | HNG nominal_delta [LOT] | HNG delta [LOT] | curve_1 USD dv01 [USD per basis point] |
| str \| datetime64[D] | float64 | float64 | float64 |
| **Total** | **0** | **0.5** | **0.0085** |
| 1 Jan 2027 | 0 | 0.5 | 0 |
| 1 Jan 2028 | 0 | 0 | -0.0095 |
| 1 Jan 2029 | 0 | 0 | 0.018 |

This is `all / month`. A single-risk report has two columns, period and that risk. For
example `delta / month` has Total 0.5 and one dated row, 1 January 2027 = 0.5; it does not
acquire the payment-only dates. `dv01 / month` has Total 0.0085 and the two payment months.

Use the retained index name and reporting unit in delta headings. Use the result currency
for DV01; `curve_1` is a local group label for the one supplied curve, not a new curve name
or inferred currency property. A cleared DV01 heading is `cleared USD dv01 [USD per basis
point]` (substituting the currency), with no curve label. `all` orders nominal_delta, delta,
dv01. Later multi-index reporting repeats nominal/delta pairs by index and appends compatible
curve/currency DV01 groups; unrelated risks are never given a grand scalar total.

The full report has four heading/total rows plus its represented date count. A cleared
DV01-only report is four rows by two columns. No empty-text filler, fake date for Total,
text-formatted dates, NaN or missing cell is allowed. Formatting dates remains Excel's job.
Document this layout and pin it through the registered surface; it is an intentional
cutover from the old two-heading-row scalar/delta reports.

Use the existing mixed-output capabilities for the text/date period column. The uniform
column table builder cannot simply prepend a text Total to a date array. Keep large output
construction vectorized; do not route every dated cell through the small-grid cell builder
or add a generic seam feature unnecessarily. Output copying/formatting is real work and
must be measured.

## Where the work belongs

At baseline #177, results already have:

- Nominal daily/monthly/yearly lots retained through preparation.
- Discounted daily/monthly/yearly lots, contract risk and both scalar lot totals.
- Bilateral dv01_by_group aligned to encoded payment groups, plus scalar dv01.
- Payment dates and all existing ownership/curve context.

Add only the saved views/mappings necessary to read this report:

| Boundary | Work for this ticket |
|---|---|
| Static encoding | Distinct full bilateral payment dates, their month/year memberships, and observation/payment union axes with placement maps for all. Reuse existing mappings where applicable. |
| Preparation | Reuse existing nominal risk. Retain any additional static/context references without reading fixings again for reporting. |
| Evaluation | Sum existing dv01_by_group onto the saved day/month/year payment axes; retain immutable vectors. Keep existing scalars as the Total source. |
| Reader | Validate selectors, select saved axes/vectors/totals, copy through retained placements and format the spill. |

Do not use `prepared.unpaid_payments.days` as the report axis: it intentionally shrinks
as payments occur and serves factor gathering. The report axis comes from all encoded
payment groups. Do not alter the existing unpaid mapping to satisfy a display requirement.

For `all`, precompute the unions and placements outside the tick. Copying entries into an
output rectangle through saved placements is formatting, not a new reduction. Alternatively
retain aligned views if measured memory warrants it. Do not rediscover unions, sort, bucket
or sum in the reader. Share immutable arrays where possible rather than retaining duplicate
full matrices for each selector. Keep the choice small and state the retained-byte cost.

Refuse nonfinite day/month/year DV01 reductions before result publication, identifying the
affected period. Finite input groups and a finite overall total do not guarantee every
intermediate bucket is finite. Preserve existing numerical/refusal checks and immutable
snapshots. No extra factor lookup or recalculation of the DV01 formula is needed.

## Independent financial acceptance

Reuse the reviewed bilateral synthetic fixture, with one unit per reporting lot. On
4 January 2027, +10 and -10 observe the same quote 80 against fixed price 70. They pay
on 4 January 2028 (365 days, DF 0.95) and 3 January 2029 (730 days, DF 0.90).

| Payment | Amount | NPV | DV01 |
|---|---:|---:|---:|
| 4 Jan 2028 | 100 | 95 | -0.0095 |
| 3 Jan 2029 | -100 | -90 | 0.018 |
| Total | 0 | 5 | 0.0085 |

Nominal delta = 10 - 10 = 0; delta = 10 * 0.95 - 10 * 0.90 = 0.5. The spill above must
follow directly. Pin all risk selections and buckets, including the different observation
and payment years. In the day view the dates are 4 Jan 2027, 4 Jan 2028 and 3 Jan 2029;
month/year both use 1 January of the corresponding year in this particular fixture.

At quote 81: mark 5.5, nominal delta 0, delta 0.5; payment DV01 -0.01045 / +0.0198,
Total 0.00935. At original quote 80 and DFs 0.96 / 0.92: mark 4, delta 0.4;
payment DV01 -0.0096 / +0.0184, Total 0.0088. Axes do not change on either tick.

Also cover:

- Multiple groups paying on one day: reduce once by date, then by calendar month/year.
  Different payment days in the same month must produce a different day versus month
  shape; dates across December/January must verify the year boundary independently.
- An observation and another group's payment on the same day, and different dates that
  share a month/year bucket: `all` emits one shared row with the appropriate delta and
  DV01 side by side, not concatenated duplicate rows. Single-risk views retain their axes.
- Fixed-but-unpaid +10: fixing 82 gives amount 120, zero commodity deltas, and at DF 1
  with 364 days remaining DV01 -0.0119671232876712. Payment then gives cash 120, mark/risk
  zero, retaining the dated observation and payment rows.
- Mixed paid/unpaid, all-paid, zero-quantity and offsetting groups. Paid dates survive
  even when every risk number in their bucket is zero.
- Cleared financial and physical routes: equal lot bases, DV01 zero, no dated rate axis
  and no curve requirement. Clear Total-only behavior for dv01 and observation rows for all.
- Rolling Asian and mixed schedules/payment groups: preserve the existing observation
  risk; month buckets follow observation dates rather than futures labels. Fixed zero
  days remain visible and readers never sum repeated contract-total debug columns.

Use valid schedules/history and a later unused contract to stay within current calendar
support. Hand calculations supply expected values. Workbook caches are supporting evidence,
not independent financial oracles. Retain documented tolerances with cancellation coverage.

## Regression, work and surface acceptance

- Reconcile saved scalar, contract and observation vectors for each delta basis, and
  scalar/group/payment vectors for DV01. Verify that reporting reads the stored scalar
  rather than reconstructing Total from dated output. One trade/many trades use one path.
- Pin exact column order, four leading rows, actual date/number cell kinds, local context,
  all sparse unions and single-risk axes. Reject unknown selectors, case/space variants,
  omitted or blank args and invalid handles under the normal seam rules.
- Count payment groups and axis entries reduced/aligned, output cells and bytes. Exercise
  repeated/distinct payment dates, long Asian schedules and fully paid batches. Report
  temporary and retained memory and counts before/after.
- Preserve quote/fixing/factor-read counts. Tick reporting adds no sorting, trade resolution,
  unit conversion, fixing fold or extra curve reads. Reader reductions and date-discovery
  work are zero; the saved Total requires no arithmetic.
- Hold an old results handle through quote/curve/history changes; its reports remain
  unchanged. Normal publication, failure/recovery and final release still work. No new
  handle is published simply to read risk.

Migrate function registration/help, active report pages, Python/seam tests, performance
ledgers, host replay, smoke, lifetime and kept workbook in this PR. Search for both old
function names/signatures, positional INDEX reads and header-based consumers. Existing
scalar checks now select the Total row and measure explicitly; date-only consumers skip
the four leading rows. Do not blindly move column numbers. Give enlarged spills room and
leave no stale formulas, old help contract or #SPILL! cells.

The workbook demonstrates selected delta, selected DV01 and all for the base bilateral
case, one quote/curve update and fixed/paid cases, plus cleared behavior. Reuse existing
fixtures rather than creating an independent valuation path. Update the series/README/UAT
status selectively after implementation; historical tickets remain history with a forward
pointer where their reader contract is superseded.

Run check.ps1 and the kept workbook recalculation/comparison workflow. Review changes to
existing goldens separately under the project rule. Done means the one-result reporting
contract is fully usable and migrated, with the saved dated DV01 needed by the next slice.

## Outside this PR

No _AggregateResults, range of result handles, two-kind reader seam, multi-index grouping,
new curve identity/currency system, rate-key mapping, FX/unit conversion, changed risk
formulas, new discount-preparation function, or optional/default selectors. Collection
policies and multi-group headings are addressed in the next tickets of the series.

## As built (#178)

Built as agreed on 11 October, the owner's answers to the review's questions first: the heading
words are the index's `name` and the reporting specification's `name` in brackets, `UNIT
nominal_delta [UNIT]`, the DV01's `curve_1` and the currency, `cleared` where no curve values;
the PR is stacked on #177; the kept workbook's migration puts the new reports in free columns
beside their blocks and clears the old anchors, no row moved; the counting is one encoding
counter for a bilateral batch's distinct payment days, the tick's `risk_reductions` 4 to 7, and
the reader pinned by its call and numpy ledgers and its allocation, no counter in the reader.

- **The encoding.** `PaymentAxes` in `trades/encoding.py`, made once for a bilateral financial
  batch beside the observation axes: the distinct payment days of every group with each group's
  place, their months with each day's, their years with each month's, three uniques; and at each
  level the union of the observation axis and the payment axis with each axis's places on it,
  three unions and six searches, so that a report of all three copies saved vectors onto one
  axis through saved places. Every array frozen, `encoded_payment_days` counted, the record's
  last field; None for a cleared batch, whose DV01 has no dated axis, and a physical one, whose
  ledgers stand.
- **The evaluation.** `_discounted` sums `dv01_by_group` onto the three axes by three bincounts,
  a paid group's nothing on its day, checks each view finite naming the first period that is
  not, freezes and retains `dv01_by_day`, `dv01_by_month` and `dv01_by_year` on the result;
  `risk_reductions` 7. `Risk`, `RiskView` and `risk_view(results, risk, bucket)` in
  `trades/evaluation.py` replace `bucketed`: the observation axis with the preparation's or the
  result's vector for a delta, the payment axis with the result's for the DV01, a cleared
  result's no day and nothing, the union with every vector placed through its saved places for
  all, a cleared result's all on the observation axis with a DV01 column of zeros, the Totals the
  saved scalars; nothing summed, sorted or discovered.
- **The reader.** `_ReportRisk(results, risk, bucket)` in `excel/trades.py`, both words read by
  `choice` into `Risk` and `Bucket`, no default; `_risk_table` writes the rectangle by kind, the
  context row, the headings, the types, the Total and the dates, the two date columns through
  the table builder. `_ReportDelta` is gone from the module, its export list, its help and its
  page, with forward pointers where its contract stood.
- **The figures.** The ticket's spill cell for cell on the UNIT fixture, all by month and each
  risk on its own axis, 0, 0.5 and 0.0085 over 1 January 2027, 2028 and 2029 and -0.0095 and
  0.018 on the payment days; the tick to 81 and the replacement curve moving the payment days'
  DV01s and not the axes; the fixed-but-unpaid lot's observation day at zero beside its payment
  day's -0.0119671232876712; the paid day kept with nothing in it; the cleared twin's Total of
  nothing over no row. In the kernel: groups on one day summed by day, two January days one
  month, December against January two years; a payment on an observation day sharing its row
  under all, 10 and 5 lots beside -0.0001 times 732/365 of 90 and 737/365 of -90; a DV01 bucket
  past the largest number over 512 contracts refused by its payment day while every group, the
  mark and the DV01 in all stay finite.
- **The counts.** A bilateral tick 5,901 bytes at 2,500 trades over 24 slots, 5,093 before, the
  three views retained; the report of all three by day 6,263 bytes for its 48 dated rows, 3,591
  for the cleared batch's 24; a view by reference no numpy call and nothing allocated, all three
  three zeros over the union; the cleared encoding's, preparation's and tick's ledgers unchanged.
  2,585 Python tests, 314 host tests, 1,136 smoke formulas and 166
  lifetime checks on the final form.
- **Not done.** No collector, no range of result handles, no two-kind reader seam, no
  multi-index grouping, no curve identity or currency system, no rate-key mapping, no FX or unit
  conversion, no change to the risk formulas, no discount-preparation function and no optional
  selector, as the ticket keeps outside this PR. No golden file exists to change.
