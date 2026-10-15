# Dates and period labels through the date helpers

[Pipeline overview](README.md) · [UAT item 3](surface-uat-notes.md#3-dates-and-period-labels-through-the-same-helpers)

**Status:** Draft requiring further alignment, 9 October 2026. Not ready for implementation.
The owner subsequently requested one-argument BAL, starting at the later of `as_of` and
the period's first day. How the helper selects a valuation date is unresolved; the
library has no implicit current valuation context. The explicit-reference proposal below
is retained for discussion. Inspected baseline: prototype PR #168 at `d1633d7`.

## Outcome

Let the same worksheet formulas accept a period label, a BAL label or an explicit date.
The helpers produce concrete `start_date` and `end_date` cells for trade entry without
requiring the user to switch formulas or wrap them in an `IF`.

Keep the function names, argument names, order and optional reference:

```text
util_StartDate(period, [reference_date]) -> date
util_EndDate(period, [reference_date])   -> date
```

Widen the first argument to accept a date as well as existing period text. Both helpers
return an explicit date unchanged. Ordinary labels and case-insensitive BAL parsing
retain their existing behavior; BAL support was already implemented in PR #160.

## Input behavior

Dates in this table mean numeric Excel dates, not text containing a date.

| First input | Reference date | Start result | End result |
|---|---|---|---|
| `DATE(2026,10,8)` | omitted | 8-Oct-2026 | 8-Oct-2026 |
| `v26` | omitted | 1-Oct-2026 | 31-Oct-2026 |
| `CAL27` | omitted | 1-Jan-2027 | 31-Dec-2027 |
| `balv26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |
| `BALV26` or `BalV26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |
| `balx26-z26` | 12-Nov-2026 | 12-Nov-2026 | 31-Dec-2026 |
| `v26` | 8-Oct-2026 | 1-Oct-2026 | 31-Oct-2026 |
| `DATE(2026,10,8)` | 12-Nov-2026 | 8-Oct-2026 | 8-Oct-2026 |

A valid reference affects BAL only. Validate a supplied reference even when it does not
affect the result, allowing one formula shape down mixed input rows without bypassing
argument checks. A BAL reference must be inside the base period, including either end;
both helpers refuse a missing or out-of-period reference. Preserve all existing period
grammar, range-order and BAL-prefix rules.

Reuse the existing scalar date contract: a finite whole Excel serial from 61 through
2958465, inclusive. Excel dates arrive as numbers; cell formatting is not available at
this boundary. A valid serial therefore works even if its cell is formatted General.
Do not infer whether a number is a date from how it is displayed.

Refuse fractional days, out-of-range or nonfinite serials, booleans, blank cells, empty
text and multi-cell ranges. The first argument remains required. An omitted optional
reference remains distinct from a supplied blank. Text such as `"2026-10-08"`,
`"10/08/26"` or `"46303"` does not become a date: it follows the existing period-text
grammar and fails. No locale-dependent date parsing or numeric-text coercion.

## Worksheet use

Use separate input columns when entering an explicit start and end. A period label can
be repeated in both columns so the same formulas also handle whole months and BAL:

| Start input A | End input B | Fixed reference C | `util_StartDate(A, C)` | `util_EndDate(B, C)` |
|---|---|---|---|---|
| `v26` | `v26` | 8-Oct-2026 | 1-Oct-2026 | 31-Oct-2026 |
| `balv26` | `balv26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |
| 8-Oct-2026 | 20-Oct-2026 | 8-Oct-2026 | 8-Oct-2026 | 20-Oct-2026 |

Populate C with a valid fixed reference when using that two-argument formula throughout;
a blank C is not an omitted argument. A single explicit date passed to both helpers
intentionally returns the same date twice, not the bounds of its month.

The booking reference stays fixed as market `as_of` advances. These helpers remain
deterministic and nonvolatile; they neither read the clock or market nor snapshot a
changing input cell. Changing a referenced cell still recalculates its dependents.

## Engineering boundaries

The current first argument is declared `str`; adding date support requires an explicit
seam extension. Implement the smallest declared scalar input that distinguishes valid
dates from period text, with type/shape validation at the seam and period meaning in the
library. Do not route raw Excel values to library code for another round of type checks
or introduce general coercion. Record the new input contract in `docs/seam/inputs.md`.
Internal type names and representation are engineering choices.

Reuse the existing date validator and period resolver. The date path returns the
validated day without period parsing or business-day adjustment. Keep dates as dates
through the library and existing numeric date output. Publish no handles and add no
persistent cache or market dependency.

Relevant implementation locations are `src/goosedove/excel/utilities.py`, the declared
types and binding in `src/goosedove/excel/bridge.py`, and
`src/goosedove/index_definitions/periods.py`. Update both helpers' Excel help and their
pages under `docs/library/utilities`, plus UAT item 3 when delivered.

## Acceptance

- Pin every row of the input table through the registered worksheet functions, with
  numeric date output. Include a date formula, a date cell and an unformatted serial.
- Test both date bounds, invalid neighboring serials, fractional days, nonfinite
  numbers, booleans, blanks, empty text, missing first input and multi-cell ranges.
- Pin explicit-date identity for representative dates including leap day, month/year
  ends and weekends. Preserve existing ordinary-label and BAL cases and refusals.
- Check supplied reference validation on every path: ordinary label, BAL and explicit
  date. A valid irrelevant reference changes neither ordinary-label nor date results;
  an invalid supplied reference fails.
- Add a kept worksheet example like the mixed-input table, with numeric helper outputs
  feeding a date-based Asian ticket. Its resolved periods and value/risk must match the
  same trade dates supplied directly. Keep `contract_code` absent under current rules.
- Preserve nonvolatile registration and existing work-budget coverage. Account for the
  new date branch without redundant parsing or conversion; no timing merge gate.
- Update seam/library tests, help, host replay, Excel smoke and the kept example as
  applicable, then run the full gate. Existing golden changes remain separately reviewed.

This does not implement UAT item 4's coexistence of `contract_code` and date columns,
unused period-cell handling, direct BAL codes in `_CreateTrades`, or a new `exact`
schedule method. The separate date-offset utility (`+1bd`, `cd`, `em`) is also outside
this ticket. Existing trade-period and schedule-method validation remains in force.
