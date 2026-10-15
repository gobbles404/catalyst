# Risk reporting by pricing contract month

[Pipeline](README.md) · [UAT notes](surface-uat-notes.md) ·
[Existing report design](unified-risk-reporting.md) ·
[Aggregate integration](aggregate-risk-excel-integration.md)

**Status:** Built in #NN on `claude/risk-contract-month`, stacked on PR #183 at `c72befe`, the
baseline inspected, 15 October 2026, the page as the ticket, two commits as asked; the
[As built](#as-built-nn) section at the end says what was built and what was not. This ticket
supersedes the earlier report design's observation-month/year bucketing and, for month/year
displays, its requirement to retain every past zero row; it does not claim the stack has
shipped.

## Outcome

Monthly commodity delta belongs to the month of the contract supplying its price.
November NG risk belongs in November even though that contract expires in October.
An October ethane Asian whose prices reference October ethane belongs in October.
A rolling Asian splits its live delta between its pricing contracts.

The monthly spill then starts with the calendar month containing the result's
`as_of`: 14 October 2026 starts at October 2026, equivalent to V26. This is a
display anchor; it does not select the prompt contract or assert that V26 is live.

Keep the public signature and required selectors:

```excel
=_ReportRisk(results,"delta","month")
=_ReportRisk(results,"nominal_delta","year")
=_ReportRisk(results,"all","month")
```

`results` continues to accept one evaluated batch or an aggregate. Preserve the
context/header/type rows, saved Total first, risk-column order, units and grouping
rules. This changes risk attribution and display, not valuation or risk formulas.

## Commit 1 Change the delta buckets

Suggested message: `fix(risk): bucket delta by pricing contract month`

| Risk | day | month | year |
|---|---|---|---|
| nominal_delta | Observation date, as today | Pricing contract month | Pricing contract year |
| delta | Observation date, as today | Pricing contract month | Pricing contract year |
| dv01 | Payment date, as today | Payment month, as today | Payment year, as today |

The daily delta view continues to answer when exposure fixes. Month/year views
answer which contracts carry the exposure. Consequently, grouping the displayed
daily rows by their calendar month will no longer reproduce the monthly delta
report. All three views must still reconcile to the same saved scalar total.

Use each live slot's resolved **pricing reference**, not its booked contract,
observation month, payment month or position in a price vector. This applies to
all supported schedule methods, futures indexes and IFERC indexes. A strip's
booked months and an Asian's pricing months can differ. Existing fixing cutoffs,
payment treatment and physical-expiry refusals stay in force.

For bilateral delta, retain the discount factor belonging to each payment group
before summing its contribution into pricing-contract buckets. Never replace
different payment factors with one representative factor. Nominal and discounted
deltas remain separate, and cleared contributions retain their current treatment.

For `all`, use the union of the selected delta and DV01 axes. At month/year level
the same row means a pricing-contract period for delta and a payment period for
DV01. Keep these meanings explicit in function help and the report page. Preserve
actual Excel dates as labels: first day of the contract month or year. Contract
codes in the examples below explain the dates; they are not new spill columns.

### Fit to the current pipeline

- Resolution already parses the whole index schedule's contract months. Retain
  that immutable mapping and gather it by the saved pricing references. At the
  inspected baseline the parsed month vector is not retained; booked component
  start dates cannot substitute for it because an Asian can reference another
  month. No contract-code parsing during preparation, evaluation or reporting.
- Encoding owns static reference-to-month/year mappings. Preserve observation
  dates and daily risk for fixing and roll-off inspection.
- Preparation saves nominal risk; evaluation saves discounted risk. Reuse the
  existing unique contract-risk vectors where possible rather than independently
  reducing every observation again. Keep all vectors immutable and finite.
- Collection sums compatible saved vectors on the new axes. Index identity,
  market/curve compatibility, duplicate occurrence counting, signed netting and
  separate columns for different indexes remain as implemented.
- Reporting selects saved axes, vectors and totals and formats them. It does no
  pricing, fixing reads, factor lookups, parsing or risk reductions. Do not sum the
  repeated contract-total columns in the debug spill.

This commit changes attribution only. Keep the existing sparse structural axes
and their zero buckets until commit 2, so its financial and display changes can
be reviewed independently.

## Commit 2 Start the period spill at as_of

Suggested message: `feat(risk): start period reports at the valuation month`

For month/year reports, use the `as_of` retained by the supplied results or
collection. Never read today's clock or mutable global valuation state. Held
results must retain the same report after the workbook's valuation date changes.

| Bucket | First dated row | Remaining rows |
|---|---|---|
| month | First day of the month containing as_of | Consecutive months through the last represented period of the selected risks |
| year | 1 January of the year containing as_of | Consecutive years through the last represented period of the selected risks |
| day | Existing observation/payment axis | Unchanged by this ticket |

Include the starting period even if its risk is zero or the index has no contract
row for that month. Fill intervening calendar periods with zero; do not fabricate
market quotes or schedule entries. Retain future structural zero periods through
the selected axis's end, so a price tick or netting of opposing exposures on
retained structural axes does not change the horizon. Removing or rebuilding
trades can change it. If every represented period is before the start, show just the
current period with zero below Total.

For `all`, the last period includes both delta and DV01, so a later payment can
extend the rectangle. For a single risk, only that risk determines the horizon.
Different indexes share the same calendar display axis while keeping separate
columns. No dense daily calendar is introduced.

Preserve the existing exception for a cleared-only `dv01` report: zero Total and
no dated rate rows. A real bilateral payment axis follows the month/year display
rule, including when its saved risk has become zero.

**Never hide nonzero risk to achieve the starting row.** A user-supplied schedule
can leave an older contract month live, for example through a later publication.
If any selected risk column has nonzero exposure before its requested display
start, refuse that report clearly, naming the index or rate group, period, measure
and as_of. The evaluated results remain valid and inspectable. Do not move this
risk into the current month, discard it, or check only a net total that could
conceal opposite exposures in different columns or periods. No display epsilon
may silently turn a nonzero value into zero.

This filters displayed period rows, not trades, observations, payment groups or
the retained contract-risk vectors. Prepare the refusal status and identifying
facts outside the reader; reporting only checks that saved status and raises,
without scanning or reducing risk vectors again.

Build the as_of-dependent display axes/placements outside the reader and outside
static trade encoding. Share them where possible through preparation, results
and collection. Keep each saved axis with the vector it describes: the existing
collector pairs encoded month axes with prepared vectors, and both sides must
move together if report vectors are padded or clipped. Count the padded output
and retained memory as real work.

## Hand acceptance examples

These are synthetic weekday-only calendars, with no holidays, to make the risk
arithmetic independent of exchange-calendar research. Use valid boundary and
later schedule entries and complete history. All amounts below are lots of each
index's own reporting specification; never add NG lots to ethane lots.

### NG futures and the current month

At as_of 14 October 2026, hold cleared financial lastday positions of +10 lots
X26 observing 28 October and +5 lots Z26 observing 25 November. Both are live.

| Monthly row | Current implementation | After commit 1 | After commit 2 |
|---|---:|---:|---:|
| Total | 15 | 15 | 15 |
| October 2026 | 10 | No row | 0 |
| November 2026 | 5 | 10 | 10 |
| December 2026 | No row | 5 | 5 |

Both delta measures agree for cleared results. The day view still reports +10 on
28 October and +5 on 25 November. Once the X26 observation fixes, its nominal and
discounted deltas are zero; payment lag does not retain commodity delta.

### October ethane Asian

Book +22 lots for October, equally weighted across its 22 weekdays. The October
ethane pricing contract V26 expires on 30 October. At as_of 14 October, nine
observations have fixed and thirteen remain live, including 14 October itself.
The monthly report shows October = 13 and Total = 13. No November bucket is
introduced merely because payment occurs in November.

### October NG Asian across a roll

Use the same +22-lot weekday averaging window on an NG calendar where X26 prices
through 28 October and Z26 from 29 October. At as_of 14 October, eleven remaining
observations reference X26 and two reference Z26. The monthly report after both
commits is October = 0, November = 11, December = 2, Total = 13. The booked code
V26 does not control those risk buckets. On 29 October, with prior days fixed,
November is zero and December remains 2.

### Discounting and collection

For the same live pricing contract X26, combine cleared +10 lots and bilateral
+10 lots whose payment factor is 0.95. November nominal delta is 20; November
delta is 19.5. The bilateral DV01 retains its actual payment-period attribution
and existing analytic value. Change the factor to 0.90: November delta becomes
19, nominal stays 20, and the risk dates do not move.

Repeat with two bilateral payment groups on X26 at different factors. Preserve
both contributions before aggregation. Collect NG and ethane results from the
examples above: October ethane and November/December NG must appear under their
own index columns on one month axis. Test duplicate and reordered sources.

## Regression and delivery

- Add a December observation referencing F27: it reports in January 2027 and
  year 2027, while its daily date remains in December 2026. This must distinguish
  contract year from observation year.
- Exercise lastday, penultimate, last3day, Asian, partial-month Asian and IFERC.
  A publication date different from the named contract month must still use the
  pricing contract month. Preserve zero quantities and signed offsets.
- Pin sparse commit-1 output and final contiguous commit-2 output independently.
  Cover current-period zeros, gaps, all-fixed/all-paid results, no future delta,
  separate DV01 horizons, month/year rollover and the earlier-nonzero-risk refusal.
- Check every selected column against its saved Total with existing numerical
  tolerances. Day and contract-month totals agree; their individual calendar
  buckets need not agree. Keep all finiteness/overflow checks before publishing
  calculated risk, including a finite overall total with an overflowing bucket.
- Confirm quote ticks reuse preparation, history/as_of updates prepare anew,
  curve updates change discounted risk without remapping contracts, and readers
  perform no reductions. Report work counts and temporary/retained bytes before
  and after, including long Asian windows and long reporting horizons.
- Update the existing report help, library pages, collector descriptions, seam
  tests, smoke, host replay and kept workbook examples affected by the new axes.
  Keep debug readback's pricing contract and observation date available. Do not
  introduce another report function, selector or public trade input field.
- Run the repository gate and workbook recalculation checks on the implementation
  branch. Retain immutable held-handle and lifetime coverage. Review existing
  golden changes separately under the repository rule.

Update active documentation to this contract; historical tickets need only a
forward pointer. Mark this ticket and the UAT entry implemented only after both
commits pass. New quoting behavior, contract-month hedging algorithms, rates
key-tenor attribution and quarterly/hourly reports are outside this PR.

## As built (#NN)

Built on `claude/risk-contract-month` above #183's `c72befe`, one pull request of two commits and
the number stamped after.

**Commit 1, `fix(risk): bucket delta by pricing contract month`.** The terms keep the schedule's
months the resolution read, `ResolvedTrades.schedule_month`, read by the builder itself when a
Python caller gives none. The encoding makes `contract_months` and `contract_years` from the
pricing references, the terms' months gathered by reference, two uniques over the references,
in place of the observation months and years; the day axis stands. The preparation sums the
delta by reference onto them and the evaluation the discounted lots likewise, each payment
group's factor kept before the sum; the collector unions the contract axes. The hand examples
hold: November NG in November, the October ethane asian in October, the rolling asian split
November 11 and December 2, a December observation of F27 in January 2027 and in 2027, cleared
and bilateral X26 collected at 20 and 19.5 or 19 with the DV01 on the payment's October. The
smoke's WTI rows and the kernel, creation and valuation tests moved with the attribution; the
budgets pin the terms' copy of the months, the two axis helpers and the day union alone.

**Commit 2, `feat(risk): start period reports at the valuation month`.** `trades/display_axes.py`
holds `PeriodAxis`, one per bucket on the preparation, the consecutive periods from the valuation
day's through the farthest saved period with every saved period's place and the first saved
period on or after the start, and `EarlyRisk`, the facts of a saved value before the start. The
preparation makes the axes and the nominal facts once, the evaluation the discounted and DV01
facts, a cleared result's delta sharing the nominal facts, so a tick scans nothing; the
collector makes its own display axes over the groups with facts per index and rate group. The
reader copies through the saved places from the first shown period on, by month and by year,
and raises the saved facts worded with the measure asked for; by day nothing changed. The
payment axes keep the day union alone. Counted as `display_periods` at preparation and in the
collector's `report_coordinates`.

**The kept workbook.** `workbooks/handles.xlsx` gains the block from row 2639: the ticket's NG, +10 X26
and +5 Z26 at 3 valued on 14 October 2026, the nominal delta by month from B2671 running October 0,
November 10, December 5 under the Total of 15, by day the 28th and the 25th, by year 2026, all three
by month from K2671; the same trades valued on 2 November from B2692, the spill starting at November
with X26's row kept at zero; and NG3, whose September contract trades to 15 October, +3 U26 valued on
the 14th refused by month in B2715 in the words above while E2715 and H2715 show it by day and by
year. The earlier blocks' all-by-month spills in D2055, D2432 and D2439 read all by year now, the
same three and two rows they showed, since the month view would run twenty-five and thirteen rows
from the valuation month into the tables below them; the half-year block's year view in O2591 gains
the valuation year, 2026, at zero above 2027's 6.

**Not here.** No new report function, selector or trade field; no dense daily calendar; no
display start the user chooses or one from the sheet's clock; no quoting behavior, hedging
algorithm, key-tenor attribution or quarterly report. The finiteness checks of the month and
year buckets stand though a month bucket is now one contract's delta and a year's overflow is
the total's refusal first.
