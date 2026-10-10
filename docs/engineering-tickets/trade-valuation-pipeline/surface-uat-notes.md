# Trade surface UAT notes

[Pipeline overview](README.md) · [Bilateral discounting and DV01](bilateral-discounting-and-dv01.md)

Running list started 8 October 2026 while testing the trade prototype in Excel.
Status and suggested handoff order updated **9 October 2026**. Item numbers are stable
references to the detailed notes below; the pending-work order is a recommendation.

## Implemented and reviewed: release testing

These five items are implemented on the prototype stack through **PR #168 at `d1633d7`**.
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

Test lot normalization before the newer risk views so unit mistakes do not obscure the
results. The Asian roll then exercises reference mapping; the daily report checks its
aggregation; IFERC exercises the distinct monthly fixing and payment dates. Existing
case-insensitive BAL helpers are already available, using an explicit fixed booking reference.
They do not yet include the date-passthrough or mixed period-entry requests below.

Run these through the normal create -> prepare -> evaluate -> report chain. Include one
live-price tick reusing preparation and one history/as-of refresh replacing it; confirm
the sheet updates and the saved risk views remain consistent with the scalar reports.

## Not implemented: suggested engineering order

| Order / UAT item | Work to hand off | Readiness and reason for this position |
|---|---|---|
| 1 / item 3 | [Date helper inputs](date-helper-inputs.md): accept actual Excel dates alongside period/BAL labels | Revisit before handoff. The owner wants one-argument BAL using valuation context; the library has no implicitly selected valuation date. The earlier ticket needs alignment on that connection and the rule for a reference before the period. |
| 2 / item 4 | [Contract code and dates on one ticket](#4-contract-codes-and-dates-on-one-ticket): resolve per row, complete dates take precedence | Finish the blank versus formula-empty-text decision and write the ticket. Follow the helper work for one coherent date-entry UAT pass; this is a UX sequence, not a hard code dependency. |
| 3 / item 9 | [Date-offset utility](#9-date-offsets-from-text): signed `bd`, `cd`, `em`, optional holiday calendar | Direction is specified; focused ticket still needed. Independent of the preceding work and can proceed alongside it. It is not a prerequisite for existing trade payment lags. |
| 4 / item 6 | [Readable index names](readable-index-names.md): keep `name`, add `display_name` | Built in #169. Required text immediately after `name`; stored on the index and exposed in readback only. |
| 5 / item 8 | [Reserve totals](reserve-totals.md): calculate static brokerage/clearing totals at creation, carry them into evaluated results and expose a pure reader | Built in #170. Positive costs from absolute component quantities and entry-specification rates, before netting. Marketing returns zero; its inputs and calculation follow bilateral. |
| 6 / item 11 and the bilateral plan | [Counterparty plus bilateral discounting and DV01](bilateral-discounting-and-dv01.md) | Keep `counterparty` in the bilateral field scope. Align curve binding, valuation-date policy, DV01 convention and nominal-versus-discounted risk reporting before implementation. Plan the arc now; coding need not wait for the unrelated utility or name changes if this becomes the priority. |

Readable index names and the bounded reserve-totals ticket are ready for handoff while
the date-helper interface is reconsidered. The numbered order above retains the earlier
sequencing context; it is not a dependency order. Bilateral's remaining economic choices
still need alignment, and marketing reserves follow bilateral.

The six pending UAT items remain pending until implemented and reviewed. The broader
bilateral valuation plan is included in the last row to give item 11 its proper context;
it is not an additional completed UAT feature. Detailed decisions and examples follow.

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

The relationship to discounted monetary sensitivity remains a bilateral design choice.
The pending bilateral ticket's report contract must incorporate that distinction before
it is finalized.

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

Not implemented; revisit before handoff. The [date-helper inputs draft](date-helper-inputs.md)
and the details below record the earlier explicit-reference proposal. The owner now wants
one-argument BAL with a start of the later of `as_of` and the period's first day. How that
helper selects an existing valuation date remains open; work has moved to readable names.

Keep the existing worksheet call shapes:

```text
util_StartDate(period, [reference_date]) -> date
util_EndDate(period, [reference_date])   -> date
```

Interpret the requested date support as accepting an actual Excel date in the first
argument and returning that date unchanged from either helper. Period labels keep their
existing meanings. This widens accepted input types without adding or reordering arguments;
engineering must provide the seam support rather than assume date-or-text is supported today.
Do not introduce parsing of date strings such as `10/08/26`.

| First input | Reference date | Start helper | End helper |
|---|---|---|---|
| Excel date 8-Oct-2026 | omitted | 8-Oct-2026 | 8-Oct-2026 |
| `v26` | omitted | 1-Oct-2026 | 31-Oct-2026 |
| `balv26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |
| `BALV26` or `BalV26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |

BAL already works case-insensitively in the prototype. Preserve that behavior and its
explicit reference requirement. A valid reference supplied with an ordinary label or an
explicit date does not change the result; supplied arguments still undergo normal validation.
Keep the helpers deterministic and nonvolatile, with existing missing/blank distinctions.

The helper outputs populate the ticket's `start_date` and `end_date` columns. Today's
prototype requires omitting `contract_code`; item 4 proposes allowing it alongside them.
A BAL label can feed both helpers; independently entered start and
end dates feed their respective helpers. The booking reference stays fixed as market
`as_of` advances. These formulas do not snapshot a changing reference cell.

Acceptance should cover the table, existing BAL refusals, date validation through the seam,
and one worksheet example containing ordinary labels, BAL labels and explicit dates. This
is a helper-input extension; the separate ticket-period change is specified below.

## 4. Contract codes and dates on one ticket

The ticket should support all three period columns together. Resolve the period **per
row**, after combining the template and ticket, without changing `_CreateTrades`' arguments.
This replaces the prototype's requirement for one exclusive period form across the batch.

| `contract_code` | `start_date` | `end_date` | Proposed resolution |
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

Proposed inactive-code handling: require text when populated, but skip code parsing and
schedule lookup when dates select the period. This lets a BAL entry label stay on the
ticket beside its helper-generated dates. Any retained entered code must be clearly
distinguished from the resolved component contracts; readback must make the effective
dates and contracts unambiguous.

Before implementation, settle one worksheet detail: whether formula-generated empty text
(`""`) counts as absent in these three fields as well as a truly blank cell. They are
different inputs today; do not silently broaden blank handling throughout the seam.

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

Built in #169; the [readable index names ticket](readable-index-names.md)'s
[As built](readable-index-names.md#as-built-169) section says what landed. Retain the index's existing `name` used by the current market and
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

Built in #170; the [reserve-totals ticket](reserve-totals.md)'s
[As built](reserve-totals.md#as-built-170) section says what landed.
Reserves do not affect trade valuation, cash or market risk.

In the inspected prototype through PR #168, contract specifications store
`brokerage_rate_per_lot` and `clearing_rate_per_lot`, in the index's settlement currency
per lot of each specification row. `util_ReadHandle(specifications)` exposes both.
The trade pipeline does not calculate reserve amounts from them, and the current
instrument has no implemented marketing-reserve field.

Owner direction, refined 9 October: compute brokerage and clearing reserves once during
trade creation and carry the three totals, including zero marketing, with their currency
into evaluated results. `_ReportReserves(results)` reads those saved scalars and formats
them, with no summation, market access or reserve calculation. This supersedes the earlier
proposal to aggregate anew during evaluation. One trade and many use the same path.

These are static booked reserves. Fixings, payment dates, valuation-date rolls and price
ticks do not release or reduce them. This replaces the earlier proposal to expose the
reserve summary directly from a trade handle; the user wants it on evaluated results.

Keep all three categories in the output. Marketing is zero in this slice, without a
placeholder in the template. Its inputs and calculation are explicitly deferred until
after bilateral valuation, as a separate ticket.

Use positive cost amounts: absolute resolved component quantities multiplied by each
entry specification's brokerage and clearing rates, then summed. The entry specification's
basis is distinct from the index's reporting lot; rates already use settlement currency.
Preserve gross activity before exposure netting, so offsetting buys and sells both count.
Do not infer missing rates. The ticket pins strips, calendar-day quantities, equivalent
entry units, finite amounts and unchanged reserves across ticks and payment dates.

## 9. Date offsets from text

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
on the resolved trade. Carry this into the [bilateral implementation ticket](bilateral-discounting-and-dv01.md).
Requiredness and validation details remain to be specified with that work; this records
the requested field, not an implemented change.
