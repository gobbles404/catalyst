# Trade surface UAT notes

[Pipeline overview](README.md) · [Bilateral discounting and DV01](bilateral-discounting-and-dv01.md)

Running list started 8 October 2026 while testing the trade prototype in Excel.
Status and suggested handoff order updated **11 October 2026**. Item numbers are stable
references to the detailed notes below; the pending-work order is a recommendation.

## ZIP installation verification

Reported 18 October 2026: setup from a source ZIP fails in the documentation link test,
which requires a Git index that archives do not contain. The local fix explicitly skips
that repository scan for source ZIPs and skips its Git-dependent fixtures when Git is not
installed. Other tests continue; developer checkouts and CI retain the strict link check.
See the [check's owner](../../seam/working.md#11-checking-the-links).

UAT: run setup verification from a fresh ZIP, with and without Git on PATH. Confirm the
documented skips and successful remaining checks; installing Git or running `git init`
must not be necessary. The fix is pending release.

## Implemented and reviewed: release testing

These fifteen changes are implemented on the prototype stack through **PR #178**, the last
awaiting review.
Implementation and review do not imply a merge to main. For the planned **10 October release**,
confirm the packaged build includes this revision or a reviewed successor before testing
these additions. This is an implementation checklist, not confirmation of release contents.

| Test order / UAT item | Implemented change | Reviewed PR | What to try in Excel |
|---|---|---|---|
| 1 / item 1 | [Delta in index-defined lots](lot-delta-reporting.md) | [#164](https://github.com/gobbles404/goosedove/pull/164), `414b6e0` | ETE `1 LOT`, `1000 BBL` and `42000 GAL` each report 1 live lot; all three together report 3. Check the index's reporting-lot selection and a partially fixed Asian. |
| 2 / item 5 | [Calendar-driven Asian pricing references](calendar-driven-asian-references.md) | [#165](https://github.com/gobbles404/goosedove/pull/165), `f1f1b91` | Book a December crude Asian that spans the F27/G27 roll. Inspect both pricing references, then advance history across the roll and check remaining live risk. |
| 3 / item 7 | [Delta by day, month and year](daily-risk-vector.md) | [#166](https://github.com/gobbles404/goosedove/pull/166), `df2bec9` | Use `_ReportRisk(results, "nominal_delta", bucket)` with `day`, `month` and `year`, `_ReportDelta` until #178 retired it. Mix Asian and pen trades with different payment dates: risk sums by observation date, each bucket view's rows total to the Total row above them, and fixed dates retain zero rows. |
| 4 / item 10 | [IFERC basis futures](iferc-basis-futures.md) | [#167](https://github.com/gobbles404/goosedove/pull/167), `9117a39`; payment-help finding closed | Book a Waha/HSC-style basis future with `lastday` and `+3bd`. Verify payment from last trading, fixing from publication, and the live -> fixed-unpaid -> cash progression. The synthetic 1-lot Waha example marks $500 at -0.30 against -0.50, then $750 at a -0.20 fixing, then $750 cash on payment. |
| 5 / item 2 | [Numeric trade IDs](numeric-trade-ids.md) | [#168](https://github.com/gobbles404/goosedove/pull/168), `d1633d7`; reviewed clean | Enter numeric IDs, including a 15-digit value and a repeated ID. Read back numeric values; duplicates keep both trade occurrences. Fractional values and text IDs fail. |
| 6 / item 6 | [Readable index names](readable-index-names.md) | [#169](https://github.com/gobbles404/goosedove/pull/169), `3c10318`; workbook-selector corrections verified in the #170 review | Supply required `display_name` after `name` in `_CreateIndex`. Inspect the description beside the existing name; price-vector matching and handle labels still use `name`. |
| 7 / item 8 | [Reserve totals](reserve-totals.md) | [#170](https://github.com/gobbles404/goosedove/pull/170), `716a236`; reviewed clean | `_ReportReserves(results)` reports gross brokerage and clearing costs, zero marketing and currency. The ticket example gives 50 / 20 / 0 / USD, unchanged by a tick, fixing or payment. |
| 8 / item 9 | [Date-offset utility](date-offset-utility.md) | [#171](https://github.com/gobbles404/goosedove/pull/171), `0803f6f`; both review findings closed | `util_ShiftDate(date, offset, [holiday_calendar])` returns one date. Try signed `bd`, `cd` and `em`, weekend anchors, a supplied holiday calendar and zero offsets. |
| 9 / item 4 | [Contract codes and dates on one ticket](contract-codes-and-dates.md) | [#172](https://github.com/gobbles404/goosedove/pull/172), `7f14a83`; reviewed clean, inherited test typing warnings cleared | Keep all three period columns. Mix code-only rows with complete date pairs, using blanks and formula-empty cells. Dates win; half a pair fails. Inspect entered codes separately from resolved contracts. The worked batch reports 580 USD and 0.29 lots. |
| 10 / item 3 | [BAL dates from a valuation-date handle](date-helper-inputs.md) | [#173](https://github.com/gobbles404/goosedove/pull/173), `92d49b3`; reviewed clean, full gate passed | Supply the valuation-date handle as the second helper input. Try mixed-case BAL, future/current months and an expired month. Both helpers reject expired BAL; paste dates as values before booking. The kept example gives 400 USD / 0.2 lots for helper and frozen dates, and 240 / 0.12 when deliberately rebooked from the later day. |
| 11 / bilateral first slice | [Instrument rename to fixed_float](rename-instrument-fixed-float.md) | [#174](https://github.com/gobbles404/goosedove/pull/174), `29fe38f`; reviewed clean, full gate passed | Select `fixed_float` in catalog/template cells. Old `future` selectors fail normally. Check existing bookings retain the same fields, values and risks; actual futures index/schedule names stay unchanged. |
| 12 / items 8 and 11 | [Counterparty and marketing reserve](booking-fields-and-marketing-reserve.md) | [#175](https://github.com/gobbles404/goosedove/pull/175), awaiting review | Add `marketing_reserve` to a ticket or a template: `_ReportReserves` shows the amounts summed once per row, a strip once, a zero-quantity row in full, and value and risk do not move. Book a bilateral template with `counterparty` in place of `clearing_house`: the batch is made and read back per row, and evaluation still refuses. |
| 13 / bilateral calculation | [Bilateral calculation kernel](bilateral-calculation-kernel.md) | [#176](https://github.com/gobbles404/goosedove/pull/176), reviewed clean, full gate passed | Nothing new to try on the sheet in this one: the evaluator values a bilateral batch on a discount curve privately, pinned by hand-priced tests; the sheet's curve argument is item 14's. |
| 14 / bilateral integration | [Bilateral valuation and risk in Excel](bilateral-excel-integration.md) | [#177](https://github.com/gobbles404/goosedove/pull/177), awaiting review | Give `_EvaluateTrades` a `_CreateDiscountCurve` handle as its third argument for a bilateral batch, the curve starting on the valuation day and reaching past every unpaid payment: `_ReportValues` reads `bilateral_mark` and `bilateral_cash`, `_ReportRisk` `nominal_delta`, `delta` and the signed DV01 by day, month or year since #178, item 15, and `util_ReadHandle` the payment factors, amounts, group NPVs and DV01s. Leave the curve out for a cleared batch; a cleared batch given one, a curve on another day or one ending early is refused in the library's words. The kept workbook's block from row 2020 holds the two groups, the tick, the replacement curve and the one receivable's three days. |
| 15 / item 12 | [Unified risk reporting with totals first](unified-risk-reporting.md) | [#178](https://github.com/gobbles404/goosedove/pull/178), awaiting review | Call `_ReportRisk(results, risk, bucket)` with every argument: `nominal_delta`, `delta`, `dv01` or `all` and `day`, `month` or `year`, exactly so. Read the Total row under the context, heading and type rows, then the dated rows: the deltas on observation days, the DV01 on payment days, `all` on their union with zero where only the other kind has a date. On the bilateral block, `all` by month is the ticket's spill, 0, 0.5 and 0.0085 over January 2027, 2028 and 2029; a cleared batch's `dv01` is the Total of nothing over no row. A left-out or blank selector, a case or a quarter is refused. `_ReportDelta` is gone; the kept workbook's reports stand beside their blocks. |
| 16 / item 12 | [Aggregate evaluated risk in Excel](aggregate-risk-excel-integration.md) | [#180](https://github.com/gobbles404/goosedove/pull/180), awaiting review | Point `_AggregateResults` at a cell, a row or a column of `_EvaluateTrades` cells, B2:B5 say, and hand the collection's cell to `_ReportRisk(collection, risk, bucket)` as you would a single result's: one column per index for the deltas, one per curve and currency for the DV01, the saved Totals first. Repeat a cell and watch it count again; collect two results of one index over different quotes and read the refusal; read the membership with `util_ReadHandle`. The kept workbook's block from row 2380 is the ticket's example. |
| 17 / item 9 | [Compound date offsets](compound-date-offsets.md) | [#181](https://github.com/gobbles404/goosedove/pull/181), awaiting review | Type a chain such as `+3em+25cd-1bd+1bd` into `util_ShiftDate` and into a template's or a ticket's `payment_time_lag`; read the payment day beside the rule as written in `util_ReadHandle`. The order is the rule: `-1bd+1bd` keeps an open day and moves a closed one; a chain ending in `cd` or `em` may land on a closed day, and a rule paying on or before the last observation is refused as before. |
| 18 / item 15 | [Half-year strip labels](half-year-strips.md) | [#182](https://github.com/gobbles404/goosedove/pull/182), awaiting review | Book `1h27` or `2H27` in `contract_code` on an index whose schedule has the six months and read back six components with the code as typed; compare with `F27-M27` and six monthly rows, the same values and risk; try `H27`, which is March, `0H27`, which is refused, and `util_StartDate("BAL1H27", B1)` with a valuation-date handle inside the half. |
| 19 / item 16 | [Combine holiday calendars](combine-holiday-calendars.md) | [#183](https://github.com/gobbles404/goosedove/pull/183), awaiting review | Create two calendars and combine them with `_CombineHolidayCalendars(B2:B3)`; read the result back and see each day once in order; shift 9 October 2026 by `+1bd` on the combination and on each source; point a template's `payment_holiday_calendar` at the combination and read the trade's payment day back; change a source's day and watch the combination and the payment day follow. |
| 20 / item 17 | [Risk reporting by pricing contract month](risk-contract-month-bucketing.md) | [#186](https://github.com/gobbles404/goosedove/pull/186), awaiting review | Hold +10 X26 and +5 Z26 of an NG-like index on 14 October 2026 and read `_ReportRisk(results,"nominal_delta","month")`: October 0, November 10, December 5 under a Total of 15, the day view 10 on the 28th and 5 on the 25th; an October ethane asian in October; the same window on NG split November and December by the contract pricing each day; roll the valuation date and watch the start move; try a schedule that keeps a September contract live into October and read the refusal. The kept workbook's block from row 2639 shows the three cases: the hand example, the roll to November and the refusal. |
| 22 / cross-gamma | [Cross gamma of commodity delta to one discount curve](single-curve-cross-gamma.md) | [#197](https://github.com/gobbles404/goosedove/pull/197), awaiting review | Evaluate a bilateral batch on a curve and read `_ReportRisk(results,"cross_gamma","month")`: the Total in lots per basis point over the contract's months, negative for lots bought and paid for later; `all` ends with the column; tick the quote and watch it stand, move a factor and watch it move; collect a cleared and a bilateral batch of one index and read the cleared pair's zero column beside the curve's; read `contract_cross_gamma` and `cross_gamma_unit` at the end of `util_ReadHandle` on the results. The kept workbook's block from row 2767 holds the ticket's example with its quote and curve moves. |
| 21 / item 18 | [Brokerage and clearing applicability](reserve-fee-applicability.md) | [#188](https://github.com/gobbles404/goosedove/pull/188), awaiting review | On a specification charging 10 brokerage and 4 clearing per LOT, book one +10 LOT month four ways and read `_ReportReserves`: bilateral direct 0/0, bilateral brokered 100/0, cleared direct 0/40, cleared brokered 100/40; type `None`, `none` or `NONE` as the broker and see no brokerage; mix `ION` and `None` in a ticket column; move the broker between template and ticket; sell instead of buy; read the kept workbook's block from row 2722. |
| 23 / item 21 | [Linear interpolation of contract prices](interpolate-contract-prices.md) | [#198](https://github.com/gobbles404/goosedove/pull/198), awaiting review | Point `util_InterpolateContracts` at an index handle, a column of two or more contract months as codes or as CME spells them, `202704`, typed as text, and a column of their prices: the spill names every month from the first anchor's through the last's with its futures expiry and its price on the line between the anchors by calendar days, the ticket's `J27` at 70 and `M27` at 76 putting `K27` at 72.949, 29 of 59 days along. Feed the price column to `_CreatePriceVector` from the market's prompt; move an anchor price or a schedule expiry and watch the spill, the market and the mark follow; type the anchors out of order, twice, or as numbers and read the refusals. The kept workbook's block from row 2812 holds the example with its two moves and the same mark on the prices typed by hand. |
| 24 / item 22 | [Bump a discount curve](bump-discount-curve.md) | [#199](https://github.com/gobbles404/goosedove/pull/199), awaiting review | Point `util_BumpDiscountCurve` at a curve handle and a signed number of basis points, `1`, `-1`, `0.5` or `0`: the result is an ordinary curve, read back with `util_ReadHandle`, 0.95 a year out becoming 0.9499050047498416 under +1 and 0.9500950047501583 under -1, the first factor 1 and every day kept; evaluate the same prepared trades and market on the curve bumped each way and compare half the difference of the marks with the saved DV01 and half the difference of the deltas with the saved cross-gamma; bump a curve of ones down and read the refusal; type `+1bp` and read the seam's. The kept workbook's block from row 2849 holds the cross-gamma block's curve bumped each way with the centered checks. |
| 25 / item 23 | [Cashflow instrument](cashflow-instrument.md) | [#200](https://github.com/gobbles404/goosedove/pull/200), awaiting review | Make a template with `_CreateTradeTemplate("cashflow", ...)` holding `currency` USD and a `counterparty`; book rows of `trade_id`, `trade_date`, `amount`, `payment_date` and `description` with `_CreateCashflows`; value them with `_EvaluateCashflows` on a valuation-date handle and a curve starting on that day; read `_ReportValues` for `cashflow_mark` and `cashflow_cash`, `_ReportRisk(results,"dv01","year")` and `util_ReadHandle` on both handles; move a factor, roll the day onto a payment, type `CENT` or `usd`, a fixed_float template and `delta`, and read the refusals. The kept workbook's block from row 2864 holds the ticket's example. |

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
| 1 / owner UAT | [Bilateral valuation and risk in Excel](bilateral-excel-integration.md), built in #177, and [unified risk reporting](unified-risk-reporting.md), built in #178 | Use the kept workbook's bilateral block and realistic desk batches: verify cleared and bilateral values, both delta bases, DV01 by payment day, month and year, different payment days, partial fixings and independent quote and curve updates before closing the arc. |

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
saved view with `_ReportDelta(results, [bucket = "day"])`, since #178 with
`_ReportRisk(results, risk, bucket)`, item 12, both selectors required. Allowed buckets are `day`,
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
Implemented in PR #175, awaiting review: `marketing_reserve` on the `fixed_float`, booked once per
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

Since #181, [compound-date-offsets.md](compound-date-offsets.md): an offset is one or more
instructions applied left to right, `+3em+25cd-1bd+1bd`, in the utility and in the trade's
`payment_time_lag` alike, one shared reading and arithmetic, the anchors and the payment-after-
observation check unchanged.

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
PR #175, awaiting review: counterparty is required for bilateral and absent for cleared, a label
kept per row and read back.

PR #174, reviewed at `29fe38f` on 10 October, renamed the broad `future` instrument to
`fixed_float`, with the existing cleared and bilateral route choices. The
[consolidated 18-field inventory](bilateral-discounting-and-dv01.md#trade-representation-field-inventory)
preserves the 16 existing fields and adds counterparty and marketing reserve (item 8).
Those representation choices are built in #175. The subsequent agreed
valuation path passes the current curve directly to evaluation, keeping it outside static
trades so rate updates reuse trades and commodity fixing preparation. There is no new
public preparation step in this arc.

## 12. Aggregate evaluated results

Owner direction, 10 October: collect an array of evaluated-result handles, cardinality
agnostic, and retain risk vectors through time rather than only scalar totals. Compatible
cleared and bilateral commodity delta combines by index and observation date; different
indexes retain separate lot risk. DV01 is included, attributed by payment date and grouped by
curve and currency. Month and year reports are sums of those dated entries. Quote and curve
updates flow through evaluation into the collection and its readers via ordinary Excel
dependencies.

Owner refinement, 11 October: one `_ReportRisk(results, risk, bucket)` for evaluated results
and, later, their aggregate. All parameters are required. Risk is `nominal_delta`, `delta`,
`dv01` or `all`; bucket is `day`, `month` or `year`. Spill wide risk columns with the saved
**Total first**, followed by chronological dated buckets. There is no default, summary view,
separate aggregate reader or scalar-only bucket in this specification. Keep fixed and paid
zero buckets. With `all`, rows are the sorted union of observation and payment buckets, with
each column's date meaning and unit explicit. Unrelated indexes' lots never sum to a grand
total. Index groups follow first supplied appearance.

The [series specification](aggregate-evaluated-results.md) records this direction and
supersedes the earlier collector-first plan. The [first ticket](unified-risk-reporting.md) is
built in #178: the single-result report and the saved payment-time DV01, `_ReportDelta` retired
and the kept callers migrated, the heading and context layout as proposed, with the owner's
answers of 11 October recorded on the page. The [second ticket](aggregate-risk-kernel.md) is
built in #179, privately: the collector combines results by the exact index object, refusing
distinct indexes of one name, and DV01 by the exact curve object and currency, every
occurrence counted, nothing priced again, the owner's three clarifications recorded on its
page. The [third ticket](aggregate-risk-excel-integration.md) is built in #180: `_AggregateResults`
over a cell, a row or a column of results handles, the same `_ReportRisk` taking the collection's
handle, the readback showing the membership alone by the owner's revision of 11 October, and the
two seam forms the functions need.

## 15. Half-year strip labels

Owner request, 12 October: allow `1h27` and `2h27` in `contract_code` for quoted
and traded half-year strips. The [focused ticket](half-year-strips.md) is built in #182;
UAT is pending.

`1H27` means January to June 2027 and `2H27` July to December 2027, in either case.
`H27` remains March. A half resolves into the existing six monthly components, retaining
the normal quantity bases, observation methods and payment dates. The shared start and end
helpers, ranges and their existing BAL wrapper inherit the labels. No new instrument,
signature, market contract or reporting bucket is needed.

## 16. Combine payment holiday calendars

Owner agreement, 12 October: combine multiple calendars for payment rules that
require every included calendar to be open. The [focused ticket](combine-holiday-calendars.md)
is built in #183; UAT is pending.

`_CombineHolidayCalendars(calendar_handles)` accepts a cell, row or column of
calendar handles and returns an ordinary holiday-calendar handle containing the
sorted unique union of their holiday dates. Use it in `payment_holiday_calendar`
or `util_ShiftDate` without changing either consumer. Source calendars remain
unchanged, and price ticks perform no combining work.

UAT: a holiday in either source excludes that day, overlapping holidays count
once, repeated/reordered inputs produce the same dates, and changing a source
updates dependent payment dates while held snapshots remain unchanged. Counting
on one calendar then rolling on another is outside this ticket.

## 17. Risk buckets by pricing contract month

Owner agreement, 14 October: monthly delta should follow the pricing contract's
month. November NG belongs in November even though it expires in October;
October ethane Asian exposure belongs in October when V26 supplies its price.
A rolling Asian splits between its pricing contracts. The period spill should
start with the calendar month containing the result's as_of, so 14 October starts
at October even if that row is zero.

The [focused ticket](risk-contract-month-bucketing.md) separates attribution and
display into two commits, built in #186; UAT is pending. It specifies month/year
contract buckets, preserves the daily observation view and payment-date DV01, and
applies to single and collected results.

UAT: November NG shown in November, October ethane in October, an Asian across a
roll split correctly, October as the initial zero row where appropriate, and
unchanged scalar totals, discounting and DV01. Check year boundaries, mixed-index
collections and held results across an as_of change. Earlier nonzero risk must
never be silently removed by the new display start.

## 18. Brokerage and clearing applicability

Owner agreement, 15 October: specification rates alone must not incur fees. Apply
brokerage only when the trade names a broker, the text `none` in any case naming none,
so a screen trade can say so; apply clearing only on the cleared route. Bilateral direct
trades reserve neither; bilateral brokered trades reserve brokerage only. Cleared trades
retain their required clearing house and reserve brokerage only if a broker is named.

The [focused ticket](reserve-fee-applicability.md) is built in #188 as one PR with two
commits: fee applicability first, then the related instrument descriptions used in the
template/ticket workflow. UAT is pending. A template's broker applies to every row and a
ticket column may mix named brokers and `none`; existing blank-cell, duplicate-field and
route rules remain. Specification rates and quantity sizing remain the same, as do marketing
reserves and all valuation/risk calculations.

UAT: on a specification charging 10 brokerage and 4 clearing per LOT, a 10 LOT one-month
batch reports brokerage/clearing of 0/0 for bilateral direct, 100/0 for bilateral brokered,
0/40 for cleared direct and 100/40 for cleared brokered; two +10 LOT rows with `ION` and
`None` report 100/80 cleared and 100/0 bilateral. Check template/ticket parity, equal
costs for buys and sells, and unchanged totals through quote, curve and history updates of
the same created batch.

## 19. Cross gamma of commodity delta to one discount curve

Not a UAT item but the next feature after the consolidation arc, agreed 17 October: the
sensitivity of the discounted lot delta to a one-basis-point parallel rise in the curve's
continuously compounded zero rates, `cross_gamma`, in reporting lots per basis point, the
convention the DV01 already moves by. It explains why the commodity hedge moves when rates move,
including where the NPV and the DV01 are nothing.

The [focused ticket](single-curve-cross-gamma.md) is built in #197 as one PR with two commits:
the analytic calculation and the saved vectors first, then the selector, the collection's cross
groups by index and curve pair, the readbacks and the Excel surface. One curve per batch as
before; several curves in one trade array are the next ticket's.

UAT: on the ticket's example, A +10 at 70 paying a year out at 0.95 and B -5 at 74 paying two
years out at 0.90, both observing G27 on 1 February 2027 and quoted 72, the cross-gamma is
-0.00005 of 5 lots of delta, -0.00095 and +0.0009 by trade; quoted 73 it stands while the NPV
and the DV01 move; at 0.96 and 0.92 it is -0.00004 under the same 5 lots of delta. Check the
widened `all`, the cleared zero column in a mixed collection, and the two readback columns.

## 20. Ticket and reference-data hygiene

Owner steer, 17 October: revisit consistent counterparty and broker identities, entry
guards and possible future CTRM interoperability around the quoting arc. This is separate
from cross-gamma and has no implementation ticket yet. The entry mechanism remains open;
dropdowns have not been selected. No reference-data registry or trade-validation change is
part of item 19.

## 21. Linear interpolation of contract prices

Owner agreement, 17 October: a focused interpolation utility before multiple discount curves
within a trade array, independent of the cross-gamma work. The
[focused ticket](interpolate-contract-prices.md) is built in #198 as one feature PR;
[interpolate-contracts.md](../../library/utilities/interpolate-contracts.md) owns the function.

`util_InterpolateContracts(index, anchor_contracts, anchor_prices)` takes outright month
codes or the months as CME spells them, as text, and infers every monthly contract from the
first anchor's through the last's, inclusive. The weights are the calendar days between the
index's scheduled futures expiries. The spill is `contract_code`, `future_expiry` and `price`
in contract-month order. A month the schedule lacks, or has twice, is refused. The sheet
selects the price rows the existing price-vector creator takes, from the market's prompt; no
valuation-date dependency, extrapolation, seasonal model or new market handle.

UAT: the CL-style expiry-weighted example, `K27` at 72.949 between `J27` at 70 and `M27` at 76;
December to December giving thirteen monthly rows; a code and its CME text the same month; an
anchor's own price exact; the contract, date and price paired in view; a missing month refused;
and the price column feeding an ordinary vector and market through an anchor-price move and an
expiry move, with the same mark on the same prices typed by hand. The kept workbook's block
from row 2812 holds the example.

## 22. Bump a discount curve

Owner agreement, 17 October: `util_BumpDiscountCurve(curve, bump_bps)` takes a curve handle
and a signed numeric bump in basis points, including fractional and zero bumps. It returns
an ordinary discount curve for `util_ReadHandle` and `_EvaluateTrades`. The
[focused ticket](bump-discount-curve.md) is built in #199 as one feature PR;
[bump-discount-curve.md](../../library/utilities/bump-discount-curve.md) owns the function.

Use the same parallel continuously compounded rate shift and ACT/365F convention as DV01
and cross-gamma, applied to every stored daily factor from the curve's own start. Retain
existing curve checks: downward bumps are accepted only when the resulting factors remain
valid. Do not add a valuation-date parameter or change the source curve.

UAT: a factor of 0.95 at 365 days becomes 0.9499050047498416 under +1 bp and
0.9500950047501583 under -1 bp. Check the date/factor spill, unchanged source, fractional
and zero bumps, and visible refusal of a downward bump on a curve of ones. Reevaluate the
same prepared trades and market with each bumped curve: centered changes in discounted
delta and NPV should agree with the original cross-gamma and DV01, within numerical tolerance.
The kept workbook's block from row 2849 holds the checks on the cross-gamma block's curve.

## 23. Cashflow instrument

The next instrument after the utilities: one known signed monetary amount on one explicit
payment date, for a fee, a rebate or a termination payment, with no commodity index. The
[ticket](cashflow-instrument.md) is built in #200 as the first of its two PRs. The agreed
path reuses `_CreateTradeTemplate("cashflow", fields, values)`, then
`_CreateCashflows(fields, cashflow_rows, template)` and
`_EvaluateCashflows(cashflows, valuation_date, discount_curve)`, with no preparation,
commodity index, history or market. Cashflows have their own records and entry functions,
[create-cashflows.md](../../library/cashflows/create-cashflows.md) and
[evaluate-cashflows.md](../../library/cashflows/evaluate-cashflows.md), sharing the payment
arithmetic, the templates, the readers and the reports; the collection through
`_AggregateResults` is the second PR's. The owner's decisions of 17 October 2026: USD alone, one
currency per batch; the labels `cashflow_mark` and `cashflow_cash`; `dv01` by day, month and
year, `all` the DV01 alone and the commodity selectors refused by name; the currency in the
handle; the batch read back row by row and the results by payment day with the totals once.

UAT: the ticket's two future payments of +10,000 and -10,000 USD on different dates give 500
of mark and 0.85 USD per basis point of DV01, and the past rebate 250 of cash. Check signs,
fractional and zero amounts, duplicate rows, different payment dates, a curve update and a
date roll to payment; a fixed_float template refused; `delta` refused. The kept workbook's
block from row 2864 holds the example over the cross-gamma block's curve and valuation date,
and the receipt of a hundred on the two curves and on its payment day.
