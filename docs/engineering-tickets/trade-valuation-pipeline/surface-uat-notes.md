# Trade surface UAT notes

[Pipeline overview](README.md) · [Bilateral discounting and DV01](bilateral-discounting-and-dv01.md)

Running list started 8 October 2026 while testing the trade prototype in Excel.
Status and suggested handoff order updated **10 October 2026**. Item numbers are stable
references to the detailed notes below; the pending-work order is a recommendation.

## Implemented and reviewed: release testing

These twelve changes are implemented on the prototype stack through **PR #NN**, the last awaiting
review.
Implementation and review do not imply a merge to main. For the planned **10 October release**,
confirm the packaged build includes this revision or a reviewed successor before testing
these additions. This is an implementation checklist, not confirmation of release contents.

| Test order / UAT item | Implemented change | Reviewed PR | What to try in Excel |
|---|---|---|---|
| 1 / item 1 | [Delta in index-defined lots](lot-delta-reporting.md) | [#164](https://github.com/gobbles404/goosedove/pull/164), `414b6e0` | ETE `1 LOT`, `1000 BBL` and `42000 GAL` each report 1 live lot; all three together report 3. Check the index's reporting-lot selection and a partially fixed Asian. |
| 2 / item 5 | [Calendar-driven Asian pricing references](calendar-driven-asian-references.md) | [#165](https://github.com/gobbles404/goosedove/pull/165), `f1f1b91` | Book a December crude Asian that spans the F27/G27 roll. Inspect both pricing references, then advance history across the roll and check remaining live risk. |
| 3 / item 7 | [Delta by day, month and year](daily-risk-vector.md) | [#166](https://github.com/gobbles404/goosedove/pull/166), `df2bec9` | Use `_ReportDelta` with `day`, `month` and `year`. Mix Asian and pen trades with different payment dates: risk sums by observation date, each bucket view totals to `_ReportRisk`, and fixed dates retain zero rows. |
| 4 / item 10 | [IFERC basis futures](iferc-basis-futures.md) | [#167](https://github.com/gobbles404/goosedove/pull/167), `9117a39`; payment-help finding closed | Book a Waha/HSC-style basis future with `lastday` and `+3bd`. Verify payment from last trading, fixing from publication, and the live -> fixed-unpaid -> cash progression. The synthetic 1-lot Waha example marks $500 at -0.30 against -0.50, then $750 at a -0.20 fixing, then $750 cash on payment. |
| 5 / item 2 | [Numeric trade IDs](numeric-trade-ids.md) | [#168](https://github.com/gobbles404/goosedove/pull/168), `d1633d7`; reviewed clean | Enter numeric IDs, including a 15-digit value and a repeated ID. Read back numeric values; duplicates keep both trade occurrences. Fractional values and text IDs fail. |
| 6 / item 6 | [Readable index names](readable-index-names.md) | [#169](https://github.com/gobbles404/goosedove/pull/169), `3c10318`; workbook-selector corrections verified in the #170 review | Supply required `display_name` after `name` in `_CreateIndex`. Inspect the description beside the existing name; price-vector matching and handle labels still use `name`. |
| 7 / item 8 | [Reserve totals](reserve-totals.md) | [#170](https://github.com/gobbles404/goosedove/pull/170), `716a236`; reviewed clean | `_ReportReserves(results)` reports gross brokerage and clearing costs, zero marketing and currency. The ticket example gives 50 / 20 / 0 / USD, unchanged by a tick, fixing or payment. |
| 8 / item 9 | [Date-offset utility](date-offset-utility.md) | [#171](https://github.com/gobbles404/goosedove/pull/171), `0803f6f`; both review findings closed | `util_ShiftDate(date, offset, [holiday_calendar])` returns one date. Try signed `bd`, `cd` and `em`, weekend anchors, a supplied holiday calendar and zero offsets. |
| 9 / item 4 | [Contract codes and dates on one ticket](contract-codes-and-dates.md) | [#172](https://github.com/gobbles404/goosedove/pull/172), `7f14a83`; reviewed clean, inherited test typing warnings cleared | Keep all three period columns. Mix code-only rows with complete date pairs, using blanks and formula-empty cells. Dates win; half a pair fails. Inspect entered codes separately from resolved contracts. The worked batch reports 580 USD and 0.29 lots. |
| 10 / item 3 | [BAL dates from a valuation-date handle](date-helper-inputs.md) | [#173](https://github.com/gobbles404/goosedove/pull/173), `92d49b3`; reviewed clean, full gate passed | Supply the valuation-date handle as the second helper input. Try mixed-case BAL, future/current months and an expired month. Both helpers reject expired BAL; paste dates as values before booking. The kept example gives 400 USD / 0.2 lots for helper and frozen dates, and 240 / 0.12 when deliberately rebooked from the later day. |
| 11 / bilateral first slice | [Instrument rename to fixed_float](rename-instrument-fixed-float.md) | [#174](https://github.com/gobbles404/goosedove/pull/174), `29fe38f`; reviewed clean, full gate passed | Select `fixed_float` in catalog/template cells. Old `future` selectors fail normally. Check existing bookings retain the same fields, values and risks; actual futures index/schedule names stay unchanged. |
| 12 / items 8 and 11 | [Counterparty and marketing reserve](booking-fields-and-marketing-reserve.md) | [#NN](https://github.com/gobbles404/goosedove/pull/NN), awaiting review | Add `marketing_reserve` to a ticket or a template: `_ReportReserves` shows the amounts summed once per row, a strip once, a zero-quantity row in full, and value and risk do not move. Book a bilateral template with `counterparty` in place of `clearing_house`: the batch is made and read back per row, and evaluation still refuses. |

Test lot normalization before the newer risk views so unit mistakes do not obscure the
results. The Asian roll then exercises reference mapping; the daily report checks its
aggregation; IFERC exercises the distinct monthly fixing and payment dates. Existing
case-insensitive BAL helpers now take an explicit valuation-date handle under PR #173,
with future periods returning their full dates and expired periods refused. Raw-date
second arguments must migrate to handles. Date passthrough remains deferred. Mixed
period entry in PR #172 consumes the helper dates, pasted as values to freeze a booking.

Run these through the normal create -> prepare -> evaluate -> report chain. Include one
live-price tick reusing preparation and one history/as-of refresh replacing it; confirm
the sheet updates and the saved risk views remain consistent with the scalar reports.

## Not implemented: suggested engineering order

| Order / UAT item | Work to hand off | Readiness and reason for this position |
|---|---|---|
| 1 / bilateral calculation | [Private bilateral kernel](bilateral-discounting-and-dv01.md#delivery) | Payment-date factors anchored at as_of, unpaid NPV, nominal/discounted lot vectors and analytic signed DV01. Independent hand examples and measured work before public integration. |
| 2 / bilateral integration | [Evaluation and risk reporting](bilateral-discounting-and-dv01.md#delivery) | Optional curve at evaluation, saved complete results and both nominal_delta/delta columns in scalar and time-bucket readers; DV01 in the scalar risk report. Excel/lifetime acceptance, then UAT. No extra preparation function or reader basis parameter. |

Readable index names, reserve totals, date offsets, mixed period entry and BAL helper
inputs have moved to release testing above. Bilateral is the remaining main arc; its
curve-date, analytic DV01 and dual-column risk reporting are now agreed for implementation.
The owner has brought optional
manual marketing reserves into its representation work; existing brokerage and clearing
totals remain implemented. Detailed decisions and examples follow.

## 1. Delta reporting

Implemented in the reviewed prototype PR #164. The UAT description below records the
problem that prompted the change; the reported delta now uses the index's selected lot.

For the fully live ETE example, `1 LOT`, `1000 BBL` and `42000 GAL` each represent
one lot of exposure. Three positive trades entered together represent three lots.

With a CENT/GAL quote and USD settlement, the current encoding produces a coefficient
of 420 USD per one-cent/gallon move per equivalent trade. That coefficient is useful
for valuation, but it is not the lot delta the owner expects to read. Preserve the
pricing arithmetic and distinguish its monetary sensitivity from the requested lot view.

The agreed reporting basis is one designated existing specification on the index.
Each entry specification already has its own size and unit; the reporting selection is
independent of which row a trade uses. Remaining Asian lot delta follows the live
observation weights. See [Report trade delta in index-defined lots](lot-delta-reporting.md)
for the recommended selection mechanism, calculation and acceptance cases.

On 10 October the owner agreed to retain nominal lot delta, discounted lot delta and DV01
as separate measures; the desk generally hedges to discounted delta. The bilateral reader
contract now spills `nominal_delta` and `delta` together in scalar and day/month/year views,
with unchanged signatures and no basis selector. Cleared columns are equal; bilateral
`delta` is discounted. DV01 uses the agreed analytic sensitivity, not finite bumped P&L.

## 2. Trade identifiers

The owner clarified on 9 October that the source system uses numeric IDs, superseding
the earlier alphanumeric proposal, and confirmed whole numbers of at most 15 digits
without meaningful leading zeros. PR #168 at `d1633d7` implements numeric entry and
readback and has been reviewed clean; the earlier text-only limitation is resolved.

The owner also confirmed the field can be a whole integer. The
[numeric trade IDs ticket](numeric-trade-ids.md) changes this field to numeric entry,
integer retained identity and numeric readback, using existing seam support. It preserves
optional omission, template/ticket disjointness, original-row attribution and duplicate
occurrences. IDs remain attribution rather than an economic grouping or deduplication key.
The implementation accepts finite whole values within the 15-digit range, without text
coercion, including zero and signed IDs.

## 3. Dates and period labels through the same helpers

Implemented in PR #173 and reviewed clean at `92d49b3`, with the full gate passing on
10 October. The [BAL date-helper ticket](date-helper-inputs.md) supersedes the earlier
raw-reference-date and date-passthrough proposal. Independent boundary/handle probes
and the kept workbook's migrated calls and frozen-date examples matched the agreement.

Keep the function names and argument order; change the optional second input to the
existing valuation-date handle:

```text
util_StartDate(period, [valuation_date]) -> date
util_EndDate(period, [valuation_date])   -> date
```

BAL requires the handle and reads its `as_of`, ignoring the fraction of the day elapsed.
There is no implicit global date or clock lookup. Ordinary labels need no handle, and
retain their full-period meaning; a supplied handle still undergoes normal validation.

| Period | Handle `as_of` | Start helper | End helper |
|---|---|---|---|
| `v26` | omitted | 1-Oct-2026 | 31-Oct-2026 |
| `balv26` | 20-Sep-2026 | 1-Oct-2026 | 31-Oct-2026 |
| `BALV26` or `BalV26` | 12-Oct-2026 | 12-Oct-2026 | 31-Oct-2026 |
| `balv26` | 31-Oct-2026 | 31-Oct-2026 | 31-Oct-2026 |
| `balv26` | 1-Nov-2026 | Error | Error |
| `balf26` | 1-Feb-2026 | Error | Error |

Return calendar dates without business-day rolling: start is `max(as_of, period_start)`
and end is `period_end`. Both helpers fail when `as_of > period_end`, naming the entered
code, as_of and period end. Do not clamp an expired period to a one-day trade. Preserve
case-insensitive BAL and existing period grammar, nonvolatile registration and normal
missing/blank distinctions. Raw dates no longer belong in the second argument.

The user types a BAL label, inspects the helper dates, then **pastes both dates as values**
before booking. Only then may the user clear the source code for visual clarity.
PR #172 already supports complete dates with either a blank code or retained inactive text.
Formulas recalculate when the supplied handle changes; booked hardcoded dates stay static.

The earlier idea of passing an actual Excel date through the first argument remains
deferred. It is unnecessary for this workflow: fixed dates go directly into the ticket.
No automatic snapshot or active BAL-code resolution is added to `_CreateTrades`.

## 4. Contract codes and dates on one ticket

Implemented in PR #172 and reviewed clean through `7f14a83` on 10 October 2026, with
the full gate passing. The separate cleanup commit clears six inherited test-fixture
typing warnings without changing production code, expected results or performance budgets.
The [engineering ticket](contract-codes-and-dates.md) specifies the entry contract,
bounded seam change, readback and acceptance.

The ticket supports all three period columns together. Resolve the period **per
row**, after combining the template and ticket, without changing `_CreateTrades`' arguments.
This replaces the prototype's requirement for one exclusive period form across the batch.

| `contract_code` | `start_date` | `end_date` | Agreed resolution |
|---|---|---|---|
| `V26` | blank | blank | Full October 2026 from the code |
| `V26` | 8-Oct-2026 | 31-Oct-2026 | Explicit dates take precedence |
| blank | 8-Oct-2026 | 31-Oct-2026 | Explicit dates |
| `V26` | 8-Oct-2026 | blank | Fail: incomplete date pair |
| blank | blank | blank | Fail: no period supplied |

A complete date pair selects the period; the code does not constrain or expand it.
Invalid or reversed dates fail rather than falling back to the code. With neither date,
the code must resolve normally. Missing columns can still supply neither date; retaining
all three columns requires a bounded allowance for unused period cells, not a general
relaxation of required-field validation.

Inactive-code handling: require text when populated, but skip code parsing and
schedule lookup when dates select the period. This lets a BAL entry label stay on the
ticket beside its helper-generated dates. Any retained entered code must be clearly
distinguished from the resolved component contracts; readback must make the effective
dates and contracts unambiguous.

Owner-approved absence rule: a true blank and exact empty text, including a formula
returning `""`, count as not supplied in these three fields only, on template and ticket
paths. Whitespace is not absence. Other fields keep their current rules. Header ownership
still controls overlap: an absent value never authorizes the same field on both sides.
Defer template code parsing until trade creation knows whether the code is active.

Keep the refusal of duplicate fields across template and ticket. Dates still resolve
against the supplied index; partial-month method restrictions and zero-quantity validation
still apply. Resolution and encoding happen once at creation, with no new market-date
dependency. Mixed code/date rows must match their separately created singletons, including
the same dates entered with and without a superseded code.

## 5. Asian crude observations across a futures roll

Implemented in the reviewed prototype PR #165. The creation failure described below
is the original UAT case, now supported by calendar-driven pricing references.

The general correction is specified in [Calendar driven Asian pricing references](calendar-driven-asian-references.md):
one calendar-driven rule across supported commodities, independent of the booked month.

UAT of a December 2026 Asian fails at creation: the trade's December component is Z26,
but 1 December is a day of F27 prices in its index calendar. The downstream results
error propagates that creation failure.

The requested economics are supported by the exchange examples. [ICE WTI 1st Line](https://www.ice.com/products/6753542/WTI-1st-Line-Future)
averages NYMEX front-month WTI settlement prices over the production month.
[CME WTI Financial Futures, chapter 510](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf)
likewise averages first-nearby settlements over the calendar month. December names the
averaging period; its observations can reference January futures and then February futures.

In prototype `14130240`, `encoding._the_references` already derives the reference from
each observation date, then refuses it when it differs from the component's named contract.
The [first Asian slice](asian-trades.md) deliberately restricted support to a month whose
observations all reference that same contract. This UAT case requires extending that scope.

Agreed approach for this daily-prompt Asian:

- Keep the booked month/window, quantity, fixed leg and payment ownership together.
- Resolve each observation's pricing reference from the index calendar, even when that
  differs from the booked month. Preserve the own-contract checks for expiry-based methods.
- Apply history by observation date; project live observations from their resolved futures
  references. Attribute contract delta to those references, not the averaging-month label.
- Retain the date/reference mapping at creation. A tick reads the distinct live references
  and does no observation expansion or fixing work.

The existing dated slots already distinguish payment groups from pricing references.
The one-settle-per-day history can support this case when its daily reference convention
matches the swap's. Pin the roll boundary explicitly: today's calendar includes the
expiring contract on its expiry day and switches the following day. Do not apply that
convention indiscriminately to other products: the
[Brent leg of ICE's WTI/Brent BALMO specification](https://www.ice.com/products/31687082/Crude-Diff---WTI-1st-Line-vs-Brent-1st-Line-Balmo-Future)
explicitly rolls on expiry day.

Acceptance needs a calendar-month example spanning a real futures roll: observations on
both sides and on expiry day, separate forward prices and deltas, partial fixing, payment
and cash, and mixed batches with existing futures and month-aligned Asians. Readback must
distinguish the booked period from its pricing references. These requirements were
implemented and reviewed in PR #165 without changing the creator signatures.

## 6. Human-readable index names

Implemented in PR #169; its workbook-selector corrections at `3c10318` were verified
with the PR #170 review. The [readable index names ticket](readable-index-names.md)
records the contract. Retain the index's existing `name` used by the current market and
price-vector matching. Add required `display_name` text immediately after `name` in
`_CreateIndex`, store it on the index and expose it immediately beside `name` through
`util_ReadHandle`.

| `name` | Illustrative `display_name` |
|---|---|
| `WTI` | West Texas Intermediate crude oil - NYMEX |
| `NG` | Henry Hub natural gas - NYMEX |

This is descriptive text, supplied at creation and available for inspection. No new
selector or report consumes it. Pricing and binding continue to use the existing names
and object references; conventions and product behavior are not inferred from the text.
Use the existing required-text validation and normal index recreation when inputs change.
Migrate kept constructor calls, help and examples together with the field.

## 7. Observation dates appear out of order in the results readback

Corroborated on PR #165 head `f1f1b916` through `_CreateTrades`, `_PrepareTrades`,
`_EvaluateTrades` and `util_ReadHandle`. The result readback preserves the encoded slot
order: booked contract in schedule order, then payment date, then observation date within
that payment group. `schedule_method` is not a sort key. Different methods often resolve
different payment dates, which can make the displayed order look method-driven.

Synthetic reproduction: Z26 expires 31 December 2026; the pricing/payment calendar closes
25 December and 1 January as well as weekends. Book a 22-BBL December Asian and a 3-BBL
penultimate, both with `+1bd`. The pen observes 30 December and pays 31 December; the Asian
observes the month's 22 pricing days and pays 4 January 2027. The readback begins:

| Observation date | Payment date | Source in this example | Live exposure in BBL |
|---|---|---|---:|
| 30-Dec-2026 | 31-Dec-2026 | Penultimate | 3 |
| 1-Dec-2026 | 4-Jan-2027 | Asian | 1 |
| 2-Dec-2026 | 4-Jan-2027 | Asian | 1 |

The source labels above explain the example; the compressed result does not contain a
method column. Reversing the ticket rows leaves the spill identical. Giving the pen a
`+2bd` lag makes both trades pay 4 January, creates one payment group, and produces 22
chronologically ordered observation rows; the 30 December exposure is then 4 BBL.

This corroborates the displayed ordering, not a valuation or risk error. The owner clarified
the desired view: one observation date with its net live delta, irrespective of source
method or payment group. An Asian contribution of 1 lot and a pen contribution of 3 lots
on one day should appear as 4 lots on that day. Sorting the existing rows alone is insufficient.

Agreed direction, refined 9 October: retain the daily vector and its calendar-month and
calendar-year aggregates at preparation, carry all three into results, and select the
saved view with `_ReportDelta(results, [bucket = "day"])`. Allowed buckets are `day`,
`month` and `year`; quarters are excluded. Sum each slot's own live lots, never the
repeated contract-total columns from the debug spill. The reader selects and formats
saved values, without numerical aggregation or reading the debug table.

Buckets follow observation dates, independently of payment dates, booked months and
pricing-contract labels. Preserve references on the daily axis and payment ownership
for valuation/cash. Keep zero entries as dates fix and the axes stable for the batch.
This is reporting aggregation; there is no new index-level or valuation-parameter
resolution setting. The [revised ticket](daily-risk-vector.md) retains the existing
aggregate reports and raw debug layout, and replaces its earlier daily-only reader
proposal. PR #166 implements this direction in the prototype.

The owner sent the revised day/month/year ticket to engineering on 9 October 2026.
The implementation was reviewed at `df2bec9` with no actionable findings and the full
gate passing. This records the reviewed prototype, not a merge to main.

## 8. Clearing brokerage and marketing reserves

Implemented and reviewed clean in PR #170 at `716a236`, with the full gate passing.
The [reserve-totals ticket](reserve-totals.md) records the contract. Reserves do not
affect trade valuation, cash or market risk.

Before this change, the inspected prototype through PR #168 stored
`brokerage_rate_per_lot` and `clearing_rate_per_lot`, in the index's settlement currency
per lot of each specification row. `util_ReadHandle(specifications)` exposes both.
The trade pipeline did not calculate reserve amounts from them. PR #170 now books
those amounts during creation; the instrument still has no marketing-reserve field.

Owner direction, refined 9 October: compute brokerage and clearing reserves once during
trade creation and carry the three totals, including zero marketing, with their currency
into evaluated results. `_ReportReserves(results)` reads those saved scalars and formats
them, with no summation, market access or reserve calculation. This supersedes the earlier
proposal to aggregate anew during evaluation. One trade and many use the same path.

These are static booked reserves. Fixings, payment dates, valuation-date rolls and price
ticks do not release or reduce them. This replaces the earlier proposal to expose the
reserve summary directly from a trade handle; the user wants it on evaluated results.

Keep all three categories in the output. Marketing is zero in the delivered #170 slice,
without a placeholder in the template. **Owner steer, 10 October:** add an optional,
manually entered marketing reserve while defining the bilateral booking fields. It is
a one-time booked amount, with no release schedule or valuation/DV01 effect. This replaces
the earlier plan to leave its definition until after bilateral valuation.

The field is `marketing_reserve`, matching the existing report column. The owner confirmed
positive-cost reporting like brokerage and clearing: finite amounts >= 0, negative values
refused. Agreed basis is a settlement-currency amount per trade row, counted once even
for a strip, omitted as zero. Preserve the static creation-time total and existing result
reader. The owner agreed the field is optional on either route. Present blank cells
retain the existing refusal; use zero in a supplied column.
Implemented in PR #NN, awaiting review: `marketing_reserve` on the `fixed_float`, booked once per
original row, the strip, duplicate and zero-quantity examples pinned, as
[counterparty and marketing reserve](booking-fields-and-marketing-reserve.md) specifies.

Use positive cost amounts: absolute resolved component quantities multiplied by each
entry specification's brokerage and clearing rates, then summed. The entry specification's
basis is distinct from the index's reporting lot; rates already use settlement currency.
Preserve gross activity before exposure netting, so offsetting buys and sells both count.
Do not infer missing rates. The ticket pins strips, calendar-day quantities, equivalent
entry units, finite amounts and unchanged reserves across ticks and payment dates.

## 9. Date offsets from text

Implemented in PR #171 and reviewed through `0803f6f`; both review findings are closed.
Long zero-padded counts now normalize before integer conversion, and the seam history's
original UTF-8 text is restored. The [date-offset utility ticket](date-offset-utility.md)
records the contract. This utility does not resolve the separate BAL-context question.

Provide `util_ShiftDate(date, offset, [holiday_calendar])` returning an Excel date.
The date is explicit, the offset is one signed whole-number instruction, and the optional
calendar is an existing holiday-calendar handle. Omission means Monday to Friday with
no additional holidays. Supplied arguments follow normal seam validation; a blank
calendar is not omission. The function is deterministic and nonvolatile.

| Offset | Meaning |
|---|---|
| `+1bd` | First business day strictly after the date |
| `-1bd` | First business day strictly before the date |
| `+7cd` | Seven calendar days later |
| `-7cd` | Seven calendar days earlier |
| `+0em` | Last calendar day of the current month |
| `+1em` | Last calendar day of the next month |
| `-1em` | Last calendar day of the previous month |

Read suffixes case-insensitively. A small full-match parser can separate the signed
count from `bd`, `cd` or `em`; unsupported text fails. Use date/calendar operations
for the arithmetic. `em` follows `EOMONTH(date, count)` semantics, including a weekend
or holiday month-end. Only `bd` uses the holiday calendar. Zero `bd` or `cd` leaves
the date unchanged; zero `em` still selects the current month-end.

Business-day counting excludes the anchor even when it is closed: Saturday `+1bd`
is Monday and Sunday `-1bd` is Friday on a weekday-only calendar. With NumPy, roll
backward before a positive offset and forward before a negative one; handle zero
without rolling. Do not roll forward and then add an extra business day for `+1bd`.

Reuse calendar machinery without widening the trade's existing positive-only
`payment_time_lag` grammar. This utility does not add compound instructions, intraday
time, a month-end business-day adjustment, or a dependency on today's date.

## 10. IFERC market accepted but trade creation refused

Implemented in prototype PR #167 and reviewed through the payment-help fix at `9117a39`,
with no outstanding review findings and the full gate passing. The PR remains open.
The original UAT refusal and its resolution are recorded below.

UAT reported: `index is an IFERC index, expected a futures index for a future`.
In prototype `df2bec9`, `trades.terms.futures_schedule_of` deliberately refused any
index whose kind was not `FUTURES`. Trade resolution and the kernel used this boundary.

The library already supported an IFERC index, schedule, fixings, calendar and market.
The trade path had not been extended to consume them. Its observations and
fixing lookup assumed a daily futures calendar; an IFERC calendar instead has one row
per contract month, dated by the index's publication date. The IFERC schedule retains
last trading and publication dates separately.

Changing the template's schedule method could not remove this boundary. Removing the kind
check alone would not connect monthly observations and fixing lookup to the trade kernel.

Owner direction, 9 October: use the existing `future` instrument for ICE Waha/HSC basis
futures on a single IFERC index. The index supplies the traded basis in both its live
quotes and monthly fixings; the trade does not construct two legs or subtract Henry Hub.
Keep `route = cleared` and `settlement_method = financial`. The schedule already retains
the last trading date: template `payment_time_lag = +3bd` counts from that date on the
supplied payment holiday calendar. Publication date separately determines fixing state.

The [IFERC basis futures ticket](iferc-basis-futures.md) contains the exchange evidence,
mapping, payment/cash and lot-delta examples, and acceptance. PR #167 implements required
`lastday` for one monthly publication fixing on an IFERC index, while preserving expiry-day
`lastday` on a futures index. It supports full-month bullets/strips and existing quantity
bases, with the usual separate preparation and evaluation. The help now states each
index kind's correct payment anchor. Partial months, other IFERC schedule methods,
Gas Daily trades and bilateral valuation remain outside this slice.

## 11. Counterparty on bilateral trades

Owner reminder, 9 October: add `counterparty` to the instrument definition as part of
the bilateral work, available through the normal template/ticket entry and retained
on the resolved trade. Specified in
[counterparty and marketing reserve](booking-fields-and-marketing-reserve.md) and implemented in
PR #NN, awaiting review: counterparty is required for bilateral and absent for cleared, a label
kept per row and read back.

PR #174, reviewed at `29fe38f` on 10 October, renamed the broad `future` instrument to
`fixed_float`, with the existing cleared and bilateral route choices. The
[consolidated 18-field inventory](bilateral-discounting-and-dv01.md#trade-representation-field-inventory)
preserves the 16 existing fields and adds counterparty and marketing reserve (item 8).
Those representation choices are built in #NN. The subsequent agreed
valuation path passes the current curve directly to evaluation, keeping it outside static
trades so rate updates reuse trades and commodity fixing preparation. There is no new
public preparation step in this arc.
