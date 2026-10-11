# Retain and report delta by day month and year

[Pipeline overview](README.md) · [UAT notes](surface-uat-notes.md#7-observation-dates-appear-out-of-order-in-the-results-readback) ·
[Lot reporting](lot-delta-reporting.md) · [Calendar driven Asians](calendar-driven-asian-references.md)

**Status:** Built in #166 on the prototype stack above #165, the page as a ticket; the
reader contract below is superseded since #178 by [unified-risk-reporting.md](unified-risk-reporting.md):
`_ReportRisk(results, risk, bucket)` spills these views as `nominal_delta` and `delta`, the
saved Total above the dated rows, and `_ReportDelta` is retired; the vectors and their
ownership stand as this page says. The
[As built](#as-built-166) section at the end says what was built and what was not.
Engineering ticket, updated 9 October 2026. The owner agreed to saved delta
vectors for day, month and year, prepared once and selected by a reader parameter.
Quarters are excluded. The inspected prototype is PR #165 at `f1f1b916`; implement on
its current successor as one focused PR. This replaces the earlier daily-only reader
proposal in this same ticket. The concrete table layout below is the recommended surface.

**Suggested PR title:** `feat(trades): report saved delta by day month and year`

## Outcome

Show the evaluated collection's **net remaining delta in reporting lots**, grouped by
observation day, calendar month or calendar year, in chronological order. Sum compatible
contributions across trades, schedule methods and payment groups. An Asian contributing
1 lot and a pen contributing 3 lots on the same observation day produce one daily entry
of 4 lots; those 4 lots also contribute to that day's month and year.

Retain all three vectors during preparation and carry them into results by reference.
Reading selects a saved vector and must not price, group, sort or convert trades again.
All three reports can appear beside one another from the same results handle. One trade
and many use the same path. Initial scope is the supported cleared, single-index linear model.

Payment groups remain the valuation structure. They determine which fixed leg and
floating amounts belong together and when mark moves to cash. The reporting vectors
are risk views of that structure; they do not replace it.

## Why the current spill is surprising

The existing slots are `(payment group, observation date)`. Groups are ordered by
booked contract and payment date; dates are ordered within each group. The prepared
and results debug spills preserve that order. Consequently, a pen observing 30 December
and paying 31 December can appear before an Asian observing 1 December and paying
4 January. There is no schedule-method sort.

Sorting those rows by date would still leave several rows for one day's risk. The
requested outcome is **aggregation by date as well as chronological presentation**.
The current `contract_lot_delta` debug column repeats a contract total beside each of
its slots and must never be summed to construct daily risk. Start from each slot's own
live exposure or `dated_live_lots`.

## Risk meaning and axis

For the current cleared model:

```text
daily_delta[d] = sum(dated_live_lots[s] for slots s observed on date d)
month_delta[m] = sum(daily_delta[d] for dates d in calendar month m)
year_delta[y]  = sum(month_delta[m] for months m in calendar year y)
```

Use the index's designated reporting specification and its already-resolved conversion.
The answer is signed and may be fractional. Fixed observations contribute zero whether
their payments are still unpaid or have become cash. An observation remains live on
its own date under the existing fixing cutoff. Payment date is not the date risk rolls off.
This is an observation-date view, not a delivery-day allocation: `calday` quantities
still distribute through their existing pricing observations and weights.

Keep the distinct observation dates in ascending order as a stable axis for this batch.
Include zero entries after fixing and after netting, including an entirely fixed or
zero-quantity batch. Do not expand to calendar dates without observations or drop dates
as `as_of` advances. Opposite contributions on different dates stay on different rows,
even if their contract delta or total delta nets to zero.

Monthly and annual axes contain the distinct months and years represented by those
observation dates, in ascending order, including zero buckets. Keys include the year:
December 2026 and December 2027 are different months. Coarser views may net opposite
dates in the same bucket; the daily vector still retains both dates. Do not insert
months or years with no observations, renormalize remaining weights, or average the
daily deltas. These are signed sums, not average daily positions.

Bucket membership follows observation dates, not payment dates, booked contract months
or pricing-contract labels. A December observation priced by F27 belongs in December
2026 and calendar year 2026; its contract risk still belongs to F27. A December payment
made in January does not move the exposure into January's risk bucket.

Retain the pricing reference aligned with every daily entry. Today a batch has one
index and its calendar assigns one pricing contract to a date, so date aggregation is
unambiguous even when payment ownership differs. The axis must reconcile to the
existing risk by pricing contract, not by booked contract. This ticket does not combine
indices or define how multiple pricing references on one day would net.

This selector controls reporting aggregation, not native market resolution. Keep daily
observation coordinates in this slice. Do not add a resolution field to the index or
valuation parameters, or change a trade's economics when a different report is selected.
Hourly observations require a later index/calendar/history design; annual reporting
here uses calendar years, not fiscal years or rolling twelve-month windows.

## Responsibilities and retained state

Use the existing records and array operations; the names below describe responsibilities
and need not become public Python types or handles.

| Stage | Work and retained facts |
|---|---|
| Creation and encoding | Build sorted day, month and year axes and their aggregation mappings from existing slots. Retain the pricing reference for every observation day. These facts are static for the created batch. |
| Preparation | Aggregate live slot exposure into daily reporting lots, then into monthly and annual signed sums. Retain all three immutable vectors with the history used. |
| Evaluation | Reuse all three prepared vectors and their static axes by reference, as existing contract risk is reused. Publish them with the result snapshot. |
| Delta reader | Validate the selector, select one saved view, and format its axis, delta and context into an Excel table. No numerical aggregation, market access, sorting or preparation. |

The static mapping may be derived with a unique-date/inverse operation over compact
slots, with day-to-month and month-to-year mappings; no dense trade-by-calendar matrix
is needed. Compute the static axes and mappings once during encoding, not on every
history change. Retain bucket-start dates in the shape the reader needs. Build all
three live numerical vectors at preparation, not on every quote tick or on first read.
Reuse existing slot exposures and lot conversion rather than redoing specification
or unit lookups. Do not materialize a separate trade matrix for each reporting bucket.

A new history or valuation date requires the existing new preparation. A tick shares
the same daily, monthly and annual arrays; old results remain unchanged. A fixing
correction can change mark/cash while leaving all three linear risk views unchanged
when the fixed/live flags are the same. Preserve all identity, coverage and existing
refusal rules.

Validate newly aggregated numeric values before publishing a prepared handle. The
daily, monthly and annual vectors must remain finite; preserve the existing slot, contract
and total-risk checks. A new aggregation overflow names the affected day, month or year
before preparation publishes a handle. Array summation may differ by ordinary
floating-point rounding, so numerical reconciliation uses the repository's appropriate
tolerances rather than exact equality.

## Worksheet reader

Add one dedicated reader:

```text
_ReportDelta(results, [bucket = "day"]) -> mixed table

_ReportDelta(A12)          // daily view
_ReportDelta(A12, "month") // calendar-month sums
_ReportDelta(A12, "year")  // calendar-year sums
```

`results` is the existing `_EvaluateTrades` result handle, required and resolved through
the normal seam. `bucket` is optional text, last, with the exact choices `day`, `month`
and `year`. Only an omitted argument defaults to `day`; a blank cell and empty text
follow existing seam refusals. Unsupported choices, including `quarter`, fail with
the allowed choices. Do not add abbreviations or case-folding aliases in this slice.

The selector only chooses retained data. Changing it never re-prepares the batch or
creates another valuation snapshot. Implement one dispatch over the defined choices,
following the repository's enum/match convention. No public daily-only alias, separate
month/year functions, optional filter, market argument or new handle is needed.

Use the usual header row, type row and data rows:

| bucket_start | delta | delta_unit | as_of |
|---|---|---|---|
| datetime64[D] | float64 | str | datetime64[D] |
| 29-Dec-2026 | 1 | lots of LOT (1000 BBL) | 1-Dec-2026 |
| 30-Dec-2026 | 4 | lots of LOT (1000 BBL) | 1-Dec-2026 |
| 31-Dec-2026 | 1 | lots of LOT (1000 BBL) | 1-Dec-2026 |

These are the final three rows of the worked example's `day` view, not its complete
output. Use the same four columns for every selector. `bucket_start` is an Excel date:
the observation date for `day`, the first calendar day of the month for `month`, or
1 January of the calendar year for `year`. It identifies the bucket boundary, not a
new observation. Preserve real dates rather than returning formatted date strings.

For that same all-live result, `month` returns one row starting 1-Dec-2026 with delta
25; `year` returns one row starting 1-Jan-2026 with delta 25. Their dates are bucket
labels even though the batch has no observation on 1 January. Unit and valuation
date repeat as context; the formula's selector states the chosen aggregation.

Pricing references remain attached to the saved daily axis internally; a month or
year may contain several references. Keep method, source trade and payment ownership
out of this reader; existing debug readbacks expose slots and references when needed.

`_ReportRisk(results)` continues to return aggregate delta, DV01 and context;
`_ReportValues(results)` continues to return mark/cash and context. `util_ReadHandle`
keeps its current slot-based debugging layout. This new reader supplies the three
time-bucket views without overloading the aggregate report or changing a debug table.
Existing creator, preparation and evaluation signatures stay unchanged.

## Independent worked acceptance

Use a synthetic month-aligned futures index, not a claimed exchange specification:

- X26 expires 30 November 2026 and bounds the calendar; Z26 expires 31 December 2026;
  F27 expires 29 January 2027 so markets remain valid throughout the payment states.
- Both pricing and payment calendars exclude weekends, 25 December and 1 January.
  December has 22 pricing days; the penultimate observation is 30 December.
- Quote USD/BBL, settle USD, and designate a reporting LOT of 1,000 BBL.
- Book a cleared financial December Asian of **22 LOT**, `quantity_per = month`,
  and a cleared financial Z26 penultimate of **3 LOT**, also `month`.
- Both have a fixed price of 70 and payment lag `+1bd`. Use quotes of 75 and fixings
  of 75 on every priced historical date required by the market.

The Asian contributes 1 lot on each of its 22 observation dates and pays 4 January.
The pen contributes 3 lots on 30 December and pays 31 December. There are two payment
groups, 23 valuation slots, and **22 daily risk entries**. All dates have delta 1 except
30 December, which has delta 4. Total live delta on 1 December is 25 lots. Each remaining
lot corresponds to 1,000 USD of sensitivity to a +1 USD/BBL move.

| as_of | Daily delta on 30 Dec | Daily delta on 31 Dec | Total live lots | Mark USD | Cash USD |
|---|---:|---:|---:|---:|---:|
| 1-Dec-2026 | 4 | 1 | 25 | 125,000 | 0 |
| 30-Dec-2026 | 4 | 1 | 5 | 125,000 | 0 |
| 31-Dec-2026 | 0 | 1 | 1 | 110,000 | 15,000 |
| 1-Jan-2027 | 0 | 0 | 0 | 110,000 | 15,000 |
| 4-Jan-2027 | 0 | 0 | 0 | 0 | 125,000 |

On 30 December the other 20 dates are zero; every state retains the same 22 dates.
Supply complete history and the correctly rolled positional quote vector at each
state. On 1 January and 4 January the market still has F27 live, while this batch
requests no live price.

Reverse the ticket rows and require the same daily vector. Then change the pen lag
to `+2bd`: both payments become 4 January, the valuation slots coalesce to 22, and the
daily, monthly and annual risk vectors stay identical in every state. Mark/cash still
follow the revised payment timing; on 31 December the revised mark is 125,000 and cash is zero.

In every state above, the single December bucket and single 2026 bucket equal the
table's total live lots: 25, 5, 1, 0 and 0. Both zero buckets remain in the January
reports because their axes belong to the created batch, not the current valuation month.

## Month and year boundary acceptance

Use the rolling WTI-like fixture from the Asian ticket: Z26 expiry 20-Nov-2026, F27
21-Dec-2026, G27 20-Jan-2027, H27 22-Feb-2027; weekends and 25 December/1 January
closed; a reporting LOT of 1,000 BBL. Book two cleared financial Asians, both at `+2bd`:

- 30-Dec-2026 through 5-Jan-2027, quantity 1 LOT per calendar day. The December
  component has two calendar days and two pricing days, 1 lot each. January has
  five calendar days and two pricing days, 4 and 5 January, 2.5 lots each.
- 1-Feb-2027 through 2-Feb-2027, quantity 3 LOT per month. Its two observations
  contribute 1.5 lots each.

On 30 December, before any of these observations has fixed, the saved daily view is:

| Observation date | Pricing reference retained | Delta in lots |
|---|---|---:|
| 30-Dec-2026 | G27 | 1 |
| 31-Dec-2026 | G27 | 1 |
| 4-Jan-2027 | G27 | 2.5 |
| 5-Jan-2027 | G27 | 2.5 |
| 1-Feb-2027 | H27 | 1.5 |
| 2-Feb-2027 | H27 | 1.5 |

The monthly report has bucket starts 1-Dec-2026, 1-Jan-2027 and 1-Feb-2027 with
deltas `[2, 5, 3]`. The annual report has 1-Jan-2026 and 1-Jan-2027 with `[2, 8]`.
Every view totals 10. Contract risk is G27 = 7 and H27 = 3: contract aggregation
is a distinct view and must not substitute for aggregation by observation time.

December's payment is 5 January, January's is 7 January and February's is 4 February.
Those dates do not affect bucket membership. On 1 January, monthly deltas are
`[0, 5, 3]` and annual deltas `[0, 8]`; on 5 January, they are `[0, 2.5, 3]` and
`[0, 5.5]`. Daily dates and month/year axes remain unchanged through those states.
Supply the complete history and correct positional price vectors as in the Asian
ticket; do not bypass the public market to construct these cases.

Separately, book 3 LOT of F27 under `lastday`, using its full January contract period
and `quantity_per = month`. It observes 21-Dec-2026 and pays 23 December at `+2bd`.
As of 18 December it contributes 3 lots to the 21 December day, December 2026 month
and 2026 year, despite its booked January month. Pin this case so the implementation
cannot substitute the booked contract's month for observation time.

## Additional acceptance and work budgets

- Reconcile each view's total to `_ReportRisk`'s `delta_total`, monthly buckets to
  the corresponding daily sums, and annual buckets to their monthly sums. Reconcile
  daily sums by retained pricing reference to the saved contract lot vector. In the
  first worked example all totals reconcile to 25 lots when fully live.
- Reuse the rolling Asian ticket's six-date WTI example: daily lots are 0.2 on each
  date initially, references F27 for the first two and G27 for the other four; the
  contract vector is `[0.4, 0.8]`, total 1.2. On 22 December the first two daily
  entries are zero, the other four remain 0.2, and the axis is unchanged.
- Cover equal observation dates belonging to different booked months as well as
  different payment dates. Combine their cleared daily risk without combining their
  valuation groups. Include mixed methods, entry units, `month`/`calday`, signs,
  duplicates, zero rows, partial periods and strips through existing public creators.
- Same-date opposite quantities net to zero and retain that date. Opposite quantities
  on different dates retain both signed daily entries while netting in a shared month
  or year. Include different months within one year and the same month number in
  different years. Batch views equal separately created singletons aligned by their
  bucket starts and summed; ticket reordering changes no meaning.
- An all-fixed batch returns its dated zeros without reading a live quote. Keep the
  existing refusal for an expired physical future; this reader does not turn it into
  a valid result. Bilateral evaluation remains outside the supported scope.
- Pin tick reuse and immutable snapshots for all three views. Repeated reader calls,
  including switching `day` to `month` to `year`, do not rebuild axes or aggregate
  exposures, access the market, read fixings or look up conversions. Pin default and
  explicit `day` equivalence plus blank, wrong-type and unsupported-choice refusals.
- Measure static axis/mapping construction and all three preparation aggregates with the
  existing work-count tools at small and large batch sizes. Report before/after work
  and retained array sizes by valuation slots and distinct days, months and years.
  Arrays scale with buckets present, not trade count times a dense calendar. Tick
  work remains the existing gather/multiply/sum path; reader work is table formatting.

Add the worked mixed-method example and all three reports side by side to the kept workbook.
Update registration/help, library pages, discovery, host and smoke expectations. Run the
full repository gate and follow the separate-review rule for any existing golden changes.

## Scope and completion

One PR adds the static aggregation mappings, all three retained prepared vectors,
shared result state and parameterized reader together. It does not add a new pricing
kernel, alter payment grouping, replace contract risk, or change the aggregate readers.
It does not add daily DV01, bilateral discounting, quarterly/weekly buckets, hourly
resolution, multiple indices, multiple references per day, per-trade attribution,
a roll-off forecast function, display-name metadata or date-entry UX.

Daily delta here is remaining observation exposure in reporting lots under the current
undiscounted model. A future bilateral implementation must distinguish it from discounted
price sensitivity; grouping away payment ownership in the valuation kernel would prevent
that distinction. Preserve those facts now without designing the rate model in this PR.

Done means users can select day, month or year from the same result and read chronological
net delta with correct lot units and fixing progression. All three vectors reconcile,
exist before the reader runs and are reused on every tick; daily references continue
to reconcile to contract risk while payment ownership remains intact for valuation.

## As built, #166

Engineering's record of what landed, in the ticket's terms.
[report-risk.md](../../library/trades/report-risk.md), which holds this reader's views since #178,
[kernel.md](../../library/trades/kernel.md),
[prepare-trades.md](../../library/trades/prepare-trades.md) and
[evaluate-trades.md](../../library/trades/evaluate-trades.md) are the pages.

- **The axes.** `_the_buckets` in `src/goosedove/trades/encoding.py` gives `Encoded` seven arrays
  more, static for the batch: `days`, the distinct observation days, `day_of_slot` and
  `day_reference`, each day's pricing contract, its first slot's; `months`, the first day of each
  calendar month those days fall in, and `month_of_day`; `years`, the first day of each
  calendar year, and `year_of_month`. Three uniques over the slots, no dense matrix, nothing
  per trade, no day, month or year without an observation, and nothing read on a tick.
- **The vectors.** `prepared_trades` sums the live lots onto the days, the days onto the
  months and the months onto the years, one bincount each, and keeps `daily_lots`,
  `monthly_lots` and `yearly_lots` frozen beside the contract vector, each checked finite after
  the slot, contract and total rules and before the record is made, the first bucket past the
  largest number named, `the day 2026-11-23 has inf of lot delta in all, expected a finite
  number of lots of BTU (1 BTU); its exposures in lots sum past the largest number`, a day's or
  a month's sum able to outrun what the contract's sum, taken in slot order, did not; a year's
  check stands beside them though no construction found reaches it before the total's. A tick
  shares all three; a new history makes them again with the rest.
- **The reader.** `_ReportDelta(results, [bucket = "day"])` in `src/goosedove/excel/trades.py`:
  the bucket read by the templates' `choice` into the kernel's `Bucket`, one match over its three
  members, `bucket is 'quarter', expected day, month or year` for any other word, a blank, empty
  text and a number the seam's refusals, and only an omitted argument `day`; `bucketed` hands
  the axis and the vector back by reference and the reader lays out `bucket_start`, `delta`,
  `delta_unit` and `as_of`, the unit and the valuation day on every row, summing, sorting and
  converting nothing. `_ReportRisk`, `_ReportValues` and `util_ReadHandle` are unchanged; the
  day's pricing contract is retained on the axis and spilled by no reader.
- **The numbers pinned.** The asian and the pen through the ticket's five states, by day, month
  and year, 25, 5, 1, 0 and 0 in the one December and the one 2026 bucket, 125,000 and 110,000
  of mark, 15,000 and 125,000 of cash, the rows reversed the same, the pen at +2bd coalescing
  the slots to 22 and changing no view, 125,000 and no cash on the 31st; the boundary case,
  1, 1, 2.5, 2.5, 1.5 and 1.5 by day off G27 then H27, 2, 5 and 3 by month, 2 and 8 by year,
  7 and 3 by contract, 0, 5, 3 and 0, 8 on 1 January and 0, 2.5, 3 and 0, 5.5 on the 5th, the
  payments on 5 and 7 January and 4 February moving nothing; the lastday F27 in December; the
  six-day asian at 0.2 a day and 1.2 in its month and year, zero on two days after the roll;
  same-day opposites a kept zero, two-day opposites 1.2 and -1.2 netting to a month of zero; two
  Decembers two months in two years. The same through resolution, the registered functions, the
  host, the smoke and the kept workbook.
- **The work.** The encoding's ledger has `_the_buckets` once; the preparation's numpy ledger
  looks, freezes and reduces three arrays more, `ndarray.any` 3 to 6, `ndarray.setflags` 10 to
  13, `ufunc.reduce` 7 to 10; the tick's ledger is unchanged, the three views shared and never
  made again, and a reader call formats a table. Retained: eight bytes a day, a month and a year
  in the preparation, 3,096 for the daily batch's 360 slots over 360 days, 24 months and 3
  years, and the encoding's axes 11,928; the preparation's least-of-three peak 30,972 bytes at
  360 slots, 86 a slot, the pin of 98 a slot unmoved.
- **Not in this slice.** No DV01 by bucket, no discounting, no quarter, week or hour, no second
  index, no two references on a day, no attribution to a trade or a method, no roll-off
  forecast, no display name and no date-entry UX, as the ticket bounds it; the readable index
  name of the UAT notes stays a note.
