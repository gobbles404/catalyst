# R4 Calendar day quantities and fixed BAL trade periods

[Pipeline overview](README.md) · [Calendar month Asian trades](asian-trades.md) ·
[Last three pricing days](last3day-trades.md)

**Status:** Slice A built in #159 on the prototype stack above #158, the page as a ticket; slices B
and C not started. The section at the end records what slice A built. Draft engineering ticket, 7
October 2026. Extends the prototype after the
[full-month Asian slice](asian-trades.md). The inspected baseline is PR #157 at `592a6bc`;
Asian is specified separately and must be available before the final integration slice.
No production changes or decision to land the prototype on main are part of this ticket.

## Outcome and delivery sequence

Book a balance-of-period trade using a familiar expression such as `BALX26` or
`BALCAL26`, resolve its concrete dates from a stable booking reference date, and value
that same booked trade as market time advances. Add calendar-day quantities without
changing the desk's meaning of monthly quantities.

Deliver one purpose per PR:

| Slice | Outcome | Dependency |
|---|---|---|
| A | `quantity_per = calday`, preserving `month` | Existing trade creation; use full-month components first |
| B | BAL parsing through the existing start/end date utilities | Existing period grammar; can be developed independently of A |
| C | Explicit dates as an alternative to `contract_code`, connected to creation and valuation | A, B and the Asian slice |

A then B then C is the recommended review order. B is a usable date utility increment;
the BAL booking is complete only when C connects the dates to trades. Do not describe
a parser-only change as completed BAL valuation.

Keep the same public trade pipeline. Do not introduce a separate BAL evaluator, a
preparation cache, a clock dependency, or a new trade handle kind.

## Agreed quantity meanings

**Keep `month`.** The entered quantity applies to each booked monthly component,
including a partial component. It is not prorated against a hypothetical full month.
A 2,000-unit BALMO booking means 2,000 units over the period booked for that month.

Add **`calday`** as the explicit calendar-day basis. The entered quantity applies to
every covered calendar day, including weekends and holidays. Use `calday` as the public
spelling; replace the unimplemented `day` choice in discovery/help rather than adding
two aliases. Preserve existing strict option spelling.

For each monthly component, before unit conversion:

```text
month:  component_quantity = entered_quantity
calday: component_quantity = entered_quantity * inclusive_covered_calendar_days
```

| Booked period | Entered quantity | Basis | November quantity | December quantity |
|---|---:|---|---:|---:|
| 12–30 November 2026 | 2000 | month | 2000 | — |
| 12 November–31 December 2026 | 2000 | month | 2000 | 2000 |
| 12 November–31 December 2026 | 100 | calday | 1900 | 3100 |

Thus `month` is per monthly component, not a total allocated across a multi-month strip.
A quantity stated as one total for a whole multi-month period is outside these two bases.

Calendar days determine **quantity**, while the selected schedule method determines
**pricing observations and weights**. An Asian's total component quantity is shared
equally over its eligible publication days. A closed pricing day still counts toward
`calday` quantity, but creates no observation and no extra weight on a nearby observation.
This does not implement Gas Daily weekend pricing or calendar-flow weighting.

## Slice A Quantity normalization

Normalize component quantities once in creation, before existing specification/unit
conversion, fixed-leg construction and observation weighting. Preserve entered quantity
and basis for inspection alongside the resulting component quantity; a readback must not
label an expanded monthly total as though it were the entered daily quantity.

Full-month contract and strip inputs initially provide the covered day counts. For a
December contract that expires in November, `calday` still counts December's covered
days, not its observation month or the days between futures expiries. Slice C will supply
the same calculation with clipped component boundaries.

The basis remains uniform within a batch under the current rules. Signed whole input
quantities, zero quantities, duplicates, specification selection and unit conversions
retain their existing validation and meaning. Preserve finite-value protections when
forming expanded quantities and amounts.

Acceptance:

- At 100 per calendar day, full December 2026 has 3,100 units, November has 3,000,
  February 2027 has 2,800 and February 2028 has 2,900.
- A full `X26-Z26` strip at 100 `calday` has component quantities `[3000, 3100]`;
  at 100 `month`, `[100, 100]`. Signed and duplicate rows preserve that arithmetic.
- Changing a pricing or payment holiday does not change covered calendar-day quantity.
  Changing pricing holidays may change observations and weights under the method.
- Existing methods use the normalized quantity once in value, fixed leg and risk.
  A tick neither recounts days nor normalizes quantities again.

Update the instrument definition, Show/help, creation/encoding documentation, readback
and work budgets in this PR. Do not widen quantity-basis mixing or payment groups.

## Slice B BAL parsing with a stable reference date

Extend the existing utilities rather than making the desk enter two hard-coded dates:

```text
util_StartDate(period, [reference_date]) -> date
util_EndDate(period, [reference_date])   -> date
```

The seam already supports an optional date argument. Missing and blank remain distinct:
an omitted reference is allowed for an ordinary expression; a supplied blank fails.
BAL requires an explicit valid reference date. Neither utility reads the system clock,
market, history, valuation date or a previously published result.

Recognize one case-insensitive `BAL` prefix on a complete existing period expression:

```text
BAL + X27
BAL + CAL26
BAL + X26-Z26
```

The prefix applies to the whole expression. Reuse the existing month, quarter, calendar
year, seasonal and range grammar, including two-digit years, chronological endpoints and
its refusal of spaces or malformed labels. Do not add separate grammars for BAL month,
BAL year and BAL strip, or accept nested BAL prefixes.

**Proposed reference convention for this draft:** the reference date is the first
included calendar day. Require it to lie inside the underlying ordinary period,
including either endpoint. An earlier or later reference fails with the period bounds;
do not silently clamp it or return an empty trade. Use the ordinary period expression
for a whole future period. A deal starting the following day supplies that day explicitly.

| Expression | Reference date | Start | End |
|---|---|---|---|
| `balx27` | 2027-11-12 | 2027-11-12 | 2027-11-30 |
| `balcal26` | 2026-10-07 | 2026-10-07 | 2026-12-31 |
| `balx26-z26` | 2026-11-12 | 2026-11-12 | 2026-12-31 |
| `BALZ26` | 2026-12-15 | 2026-12-15 | 2026-12-31 |
| `Z26` | omitted | 2026-12-01 | 2026-12-31 |

For an ordinary expression a supplied reference date is type-checked but does not change
the full period. This deliberate rule permits the same pair of worksheet formulas down
a column containing both ordinary and BAL labels.

Both utilities resolve and validate the complete expression, even when only its end is
requested. No business-day adjustment occurs here. A Saturday reference remains a
Saturday; the schedule method later selects pricing days inside the resolved period.

Resolve to concrete **days**. Do not send BAL through a months-only return path and lose
its partial start. Reuse the base parser under a small date-range resolver; internal
names and storage are engineering choices. Identical text with different references can
produce different dates, so any deduplication must account for both inputs. No persistent
cache is needed for these scalar functions.

Acceptance includes the table, mixed case, leap February, a year-end range, first/last
day references, a weekend reference, missing/blank/wrong-type reference, references
outside the base period, malformed ranges and repeated prefixes. Both helpers must
refuse the same invalid period. Existing one-argument formulas retain their answers.
The utilities remain deterministic, nonvolatile, and publish no handles.

## Slice C Explicit dates through trade creation

Add `start_date` and `end_date` to the shared `future` instrument definition. After
combining template and ticket fields, require exactly one complete period form:

| Form | Present | Absent |
|---|---|---|
| Ordinary contract or strip | `contract_code` | `start_date`, `end_date` |
| Explicit inclusive period | `start_date`, `end_date` | `contract_code` |

Refuse both forms together, either date alone, neither form, or reversed dates. Preserve
strict field names and the refusal of template/ticket field overlap even when values
match. Dates can come from worksheet helper cells; the library receives dates, not the
formulas that produced them. Validate meaning once in creation.

This is a column-level choice for a batch. The current table seam rejects blanks, so
do not promise rows with a code and empty date cells beside rows with dates and an empty
code cell. A date-based ticket omits the `contract_code` column entirely. Ordinary and
BAL expressions can both feed fully populated date columns through the helpers.

BAL labels are supported through those helpers in this sequence. They are not accepted
directly in the trade's `contract_code` field, which has no booking reference argument.
This avoids inventing a second anchor field or implicitly treating `trade_date` as the
averaging start. No `_CreateTrades` signature change is needed.

### Resolve once and retain the booked period

For either input form, retain the concrete booked start/end dates and split the period
at calendar-month boundaries. Each component keeps its intersection with that month,
its index contract reference and normalized quantity. For example, 12 November through
31 December resolves to X26 covering 12–30 November and Z26 covering 1–31 December.
Missing or ambiguous contract mapping fails as it does for code entry.

For Asian, generate the eligible publication dates within each component's intersection
and normalize weights within that component. A component with no eligible pricing day
fails; do not drop it. The existing own-reference and schedule-coverage rules still apply.

Full-month explicit dates must reproduce ordinary code entry for supported methods.
Partial periods are supported for Asian in this slice. For `lastday`, `penultimate`
and `last3day`, reject a partial component rather than silently clipping or redefining
their expiry-based observations. Full-month period boundaries are coverage dates, not
requirements that expiry observations occur within that calendar month.

For financial Asian components, payment continues to count from the last observation
using the booked lag/calendar. Shortening the end can therefore change payment. The
kernel still requires **one payment date per contract group**: incompatible payment
dates in one batch fail visibly. Do not widen that grouping in this PR. Different start
dates with compatible payment dates can share a batch and compress by dated exposure.

Retain both entered quantity/basis and resolved component quantities and dates in the
trade's inspectable state. Code-based trades also expose their derived dates. Keep
contract references available for binding even when no code was supplied by the user.
Preparation and evaluation consume this state without parsing periods or reading a clock.

### Excel booking example

Use helper columns beside the ticket:

| Cell | Content |
|---|---|
| A2 | `BALZ26` |
| B2 | Stored booking reference date, 15-Dec-2026 |
| C2 | `=util_StartDate(A2,B2)` |
| D2 | `=util_EndDate(A2,B2)` |

The actual ticket uses C2 and D2 as `start_date` and `end_date`, with quantity 2,000,
`quantity_per = month`, `schedule_method = asian`, and the other required terms supplied
by its template or row. No duplicate `contract_code` enters trade creation.

Changing market `as_of` to 16 December leaves C2/D2, the booked quantity and all encoded
weights unchanged. It only moves eligible observations from live to fixed. The reference
cell B2 is a booking fact, not a link to `TODAY()` or a changing market valuation date.
If the user edits B2, the resulting dates are changed trade inputs and creation rebuilds
the trade. The library must not hide that edit by retaining the first value in a cache.

The helpers provide convenience, not a snapshot side effect. A formula linked to a moving
date remains dynamic; the library cannot claim that such a worksheet input is static.

### Independent economic acceptance

Reuse the synthetic month-aligned index and pricing/payment calendars from
[the Asian ticket](asian-trades.md), including its boundary contract and complete history
requirements. Prices below are remaining-observation projections under that ticket's
explicit market-input meaning; conversion from raw whole-month futures quotes stays out.

Book 15–31 December 2026, quantity **2,000**, `month`, fixed price **0.25**, financial
cleared Asian, `+2bd`. There are **17 covered calendar days** and **12 observations**:
15, 16, 17, 18, 21, 22, 23, 24, 28, 29, 30 and 31 December. Each has weight `1/12`.
The fixed leg is **-500 USD** and payment is **5 January 2027**.

Use live Z26 projection **0.28**. For this separate fixture, set the 15 December fixing
to **0.24**, the 31 December fixing to **0.26**, and all other December pricing days to
**0.28**. Provide complete history, including earlier days the market needs, but earlier
days are not this trade's observations. Supply the later reference prices/fixings needed
to keep the market valid through payment, as in the Asian ticket.

| as_of | cleared_mark | cleared_cash | Z26 delta |
|---|---:|---:|---:|
| 2026-12-15 | 60 | 0 | 2000 |
| 2026-12-16 | 160/3 | 0 | 5500/3 |
| 2027-01-01 | 50 | 0 | 0 |
| 2027-01-05 | 0 | 50 | 0 |

The first fixing changes mark to
`-500 + (2000/12)*0.24 + (2000*11/12)*0.28 = 160/3`.
The final payment is `-500 + (2000/12)*(0.24 + 10*0.28 + 0.26) = 50`.
The fraction entries are independent expectations, compared with appropriate floating
point tolerance, not rounded production output reused as expected output.

At 15 December, the same entered quantity with `calday` produces **34,000** component
units and mark **1,020**, with delta **34,000**. Its dates and observation weights are
unchanged. At payment its cash is **850**. This is quantity scaling, not 17 observations.

Additional acceptance:

- BAL helper entry and the identical explicit dates give identical resolved economics.
  Code entry and its full-month helper dates give identical economics too.
- A partial first/last month in a strip gets the correct independent quantity and
  observation denominator. Pin the November/December quantity table above.
- Change a pre-start fixing while keeping the traded period's fixings identical: this
  trade's value is unchanged after preparation against the corresponding history.
- A tick reuses preparation; an `as_of` roll preserves booked dates, component quantities
  and weights while changing only fixed/live and payment state. A fixing correction
  requires new preparation and preserves the existing identity refusals.
- Two rows on the same contract with different starts but the same end/payment must
  value like their compatible singletons, including differing denominators. Different
  payment dates still fail. Duplicates count, zero rows validate, and row order preserves
  aggregate economics and aligned risk.

## Exact periods and schedule methods

This sequence implements **explicit periods**, including BAL-derived periods. It keeps
`asian` as the method that averages their publication dates. It does not add an `exact`
enum merely as another way to select dates: that would compete with `asian` in one field
without specifying another payoff rule.

If `schedule_method = exact` is intended to describe a different observation or pricing
rule, specify that rule as the next slice using these period inputs. The date and quantity
foundation will already exist. Oil rolls, multiple fixing sources, daily settlement and
calendar-flow weighting need their own definitions; none is inferred from the word exact.

## Delivery checks and limits

Each PR updates its relevant function pages, instrument help, worked workbook cells,
unit/property tests and existing smoke/host coverage. Show mixed ordinary/BAL expressions
feeding one populated date-based ticket in the kept workbook once C is complete.

Use existing work/allocation budgets to distinguish rows, components, observations,
compressed slots and distinct live references. Parser helpers should calculate boundaries
without expanding every calendar day. Creation normalizes and expands once; price ticks
do neither. Explain changed counts and run the full gate for each PR. Follow the separate
review rule for any existing golden changes.

No new row-wise blank policy, mixed quantity bases or methods, payment-group redesign,
rate valuation, reader family or retained preparation cache belongs in these slices.
Existing `_ReportValues`, `_ReportRisk` and saved vectors retain their meaning.

## As built, slice A, #159

Built as the page says for slice A, on the path every batch takes, with these particulars.

- **The basis.** `QuantityPer` in `src/goosedove/trades/terms.py` gains `CALDAY = "calday"`, the
  public spelling; `day` was never built and is gone from the definition's options, `month, calday`,
  its description, `Whether quantity is per month or per calendar day`, and its rule, `The quantity
  per contract month, or per calendar day of it, weekends and holidays included`, the texts kept
  short since the Show spill's allocation pin follows their length. The template's and the ticket's
  choice reads `quantity_per is 'day', expected month or calday`.
- **The covered days.** The resolution, `covered_days` in `src/goosedove/trades/resolution.py`,
  counts the calendar days of each component's contract month once over the schedule's months,
  five conversions and a gather, weekends and holidays included, the whole month: a December
  contract expiring in November covers December's 31 days, and no pricing or payment calendar moves
  them. The kernel takes them as a new argument of `resolved_trades`, one per component and
  positive, and keeps them as `covered_days`.
- **The component quantity.** The kernel forms `component_quantity` once, by the basis: under
  `month` the entered quantity's own frozen column, shared; under `calday` the entered quantity
  times the covered days, the product itself looked at for finiteness and the overflow handled
  where it happens, since a bound on the entered quantity is a rounded quotient a quantity at it
  can pass, as the review of #159 found, `quantity of trade 'C-1' at row 1 is 1e+308 over 31
  days, expected a finite quantity`. `quantity` stays the entered quantity. The encoding converts
  `component_quantity` and nothing else changes: the preparation, a tick and the reports take the
  coefficients as they are, so a calday batch of 110 gallons a day values as the month batch of
  3,410 to the bit, 96.1 of mark and 3,255 of delta on the ethane example's 2 December and 96.1 of
  cash once paid.
- **The readback.** `util_ReadHandle` on a trades handle spills two more columns, `covered_days`
  as `int64` and `component_quantity` as `float64`, after the payment terms and before
  `quote_quantity`, so the entered quantity, the days and the month's quantity read side by side
  and the month's total is never read as the entered daily quantity; the payment-day columns keep
  their places and the three encoding columns move two to the right.
- **The numbers pinned.** 100 a day over November, December, February 2027 and February 2028:
  3,000, 3,100, 2,800 and 2,900; the strip `X26-Z26` at 100 a day 3,000 and 3,100 and at 100 a
  month 100 and 100; signed, duplicate and zero rows alike; a pricing calendar closed on another
  day moving the observations and a payment calendar the payment day, and neither a covered day;
  one lot a day of Z26 on the NG index 310,000 of quote quantity against 10,000, marking 62,000
  against 2,000 with 310,000 of delta against 10,000. The work: the resolution's ledger gains the
  day count, five `astype` over the schedule's months and one look that every component covers a
  day, and under `calday` one look at the bound, one multiplication and one freeze, nothing per
  row; the encoding, the preparation and a tick run the same functions and numpy as over a month
  batch; the batch of 2,500 rows keeps one more column, 8 bytes a row, 530,549 bytes against
  508,917; the Show spill's peak moves by 21 bytes with the basis texts.
- **Not in this slice.** No partial month: the covered days are the whole month's until slice C's
  explicit dates clip them. No mixing of bases in a batch, no change to the payment groups, no BAL
  parsing, slice B, and no `exact` method. The encoding's own multiplications, by the lot size and
  the unit factors, check no finiteness, as before.
