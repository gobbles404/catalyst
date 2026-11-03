# Shift a date by a text offset

[Pipeline overview](README.md) · [UAT item 9](surface-uat-notes.md#9-date-offsets-from-text)

**Status:** Built in #171, one focused PR stacked on the reviewed prototype PR #170 at
`716a236`, the page as it was agreed on 10 October 2026 with the section at the end saying
what landed. It is independent of the unresolved BAL valuation-context and mixed
period-entry decisions.

## Outcome and worksheet contract

Provide one deterministic, nonvolatile utility that takes an explicit date and a
short offset instruction, then returns one Excel date directly in the formula cell.
It creates no handle and reads no valuation parameters, market or system clock.

```text
util_ShiftDate(date, offset, [holiday_calendar]) -> date
```

| Argument | Meaning |
|---|---|
| `date` | Required Excel date, such as `A2` or `DATE(2026,10,9)`. Use the existing `Date` validation; no date-text parsing or contract codes. |
| `offset` | Required text: one explicit `+` or `-`, a whole nonnegative count written in ASCII digits, and `bd`, `cd` or `em`. Suffixes are case-insensitive; leading zeros are accepted. No spaces, decimals, unsigned counts or compound instructions. |
| `holiday_calendar` | Optional existing holiday-calendar handle. Omission means Monday to Friday with no additional holidays. A supplied blank, wrong-kind handle or dead handle fails normal seam validation. |

Examples: `=util_ShiftDate(A2,"+1bd")` and
`=util_ShiftDate(A2,"+1bd",B2)`, where B2 contains a holiday-calendar handle.
The return uses the existing date output type and serial conversion; format the cell
as a date just as with `util_StartDate`. Do not add an output range parameter.

## Offset meanings

| Suffix | Rule |
|---|---|
| `bd` | Count eligible business days strictly after the anchor for a positive count, or strictly before it for a negative count. Eligible means Monday to Friday excluding the supplied holidays. |
| `cd` | Add or subtract that many calendar days, including weekends and holidays. |
| `em` | Move the anchor's calendar month by the signed number of months and return that target month's final calendar day. This is month-end selection, not business-day adjustment. |

Both `+0bd` and `-0bd`, and both zero `cd` forms, return the original date even if
it is closed. Both zero `em` forms return the current month's final calendar day.
A supplied calendar affects `bd` only. For `cd` and `em`, validate the handle normally
but do not use its holidays to move the result.

Count from the anchor without including it. In particular, Saturday `+1bd` gives
Monday and Sunday `-1bd` gives Friday on a weekday-only calendar. With NumPy this
means positive offsets use `roll="backward"`, negative offsets use `roll="forward"`,
and zero is handled without rolling. Rolling forward and then adding `+1bd` would
incorrectly skip Monday.

## Worked acceptance examples

The holiday calendar below is synthetic and contains only **12 October 2026**.
It does not claim exchange holiday coverage.

| Input date | Offset | Holiday calendar | Expected date |
|---|---|---|---|
| 9-Oct-2026, Friday | `+1bd` | omitted | 12-Oct-2026, Monday |
| 9-Oct-2026, Friday | `+1BD` | synthetic | 13-Oct-2026, Tuesday |
| 10-Oct-2026, Saturday | `+1bd` | omitted | 12-Oct-2026, Monday |
| 11-Oct-2026, Sunday | `-1bd` | omitted | 9-Oct-2026, Friday |
| 12-Oct-2026, closed Monday | `+1bd` | synthetic | 13-Oct-2026, Tuesday |
| 12-Oct-2026, closed Monday | `-1bd` | synthetic | 9-Oct-2026, Friday |
| 10-Oct-2026, Saturday | `+0bd` | synthetic | 10-Oct-2026, Saturday |
| 9-Oct-2026 | `+7cd` | synthetic | 16-Oct-2026 |
| 9-Oct-2026 | `-7cd` | omitted | 2-Oct-2026 |
| 10-Oct-2026 | `-0cd` | omitted | 10-Oct-2026 |
| 9-Oct-2026 | `+0em` | synthetic | 31-Oct-2026, Saturday |
| 9-Oct-2026 | `+1em` | omitted | 30-Nov-2026 |
| 9-Oct-2026 | `-1em` | omitted | 30-Sep-2026 |
| 31-Jan-2028 | `+1em` | omitted | 29-Feb-2028 |
| 15-Dec-2026 | `+1em` | omitted | 31-Jan-2027 |
| 9-Oct-2026 | `+001cD` | omitted | 10-Oct-2026 |

Also pin a nonleap February, multi-day offsets across holidays, mixed-case suffixes,
and all signed-zero forms. Round-trip business-day properties apply to eligible
anchors; do not assume a closed anchor can be recovered by reversing an offset.

## Validation and boundaries

The seam owns input types, scalar shapes and handle resolution using existing
capabilities. The library owns the offset grammar and resulting date. Do not repeat
internal type checks or introduce coercion, fallback dates or silent clipping.

Reject malformed instructions with `offset` named and examples of the accepted form:
`1bd`, `+1.5bd`, `+1wd`, `+1bd+2cd`, ` +1bd` and non-ASCII digits all fail.
Blank and empty text keep their existing seam refusals. Supplied arguments are
validated even when the offset is zero or does not consume holidays.

The result must fall within the library's Excel date range, **1900-03-01 through
9999-12-31**. Guard excessive digit counts/magnitudes before Python integer conversion
or NumPy date arithmetic can overflow; account for accepted leading zeros. Then check
the actual result on the supplied calendar. Name the input date and offset when their
combination leaves the supported range. A long cell value must produce a useful library
refusal rather than Python's integer-string limit, an overflow, a wrapped date or `NaT`.

Pin `1900-03-01` with `-1cd` and `9999-12-31` with `+1cd` as refusals, out-of-range
business-day/month-end results, and huge counts for all three suffixes. Conversely,
`9999-12-31` with `+0em` must succeed. Month-end arithmetic may temporarily reach
`10000-01-01` before subtracting a day; the supported-range rule applies to the final result.

## Implementation fit

The inspected prototype already has the seam's scalar `Date`, required text, optional
`Handle[HolidayCalendar]` and date output support. No new seam type is required.
Keep the worksheet wrapper in `excel/utilities.py`, delegating to a small pure library
helper beside the existing date/period helpers. Follow the current registration,
error, help and measurement conventions; internal names and record layout are engineering's.

Reuse NumPy's `busday_offset` and day/month units. Compute `em` through the first day
of the month after the target month, minus one day. Do not write weekday counters,
day-by-day loops, leap-year tables or expanded calendar ranges. A small full-match
parser is sufficient; do not create a general expression language or date framework.

Existing trade reuse points are `trades/template.py::business_days_of` and
`trades/resolution.py::_payment_terms`. They demonstrate bounded parsing and strict
positive business-day counting. **Keep their current positive-only `+Nbd` grammar,
required calendar, anchors and refusal behavior unchanged.** The utility's signed,
case-insensitive grammar and optional calendar are a separate public contract.
Do not make a general date utility import trade-template machinery. A tiny neutral
helper may be shared where useful; moving all payment and calendar consumers is not
required for this PR. Reuse by those consumers can follow with unchanged-behavior tests.

## Delivery and checks

- Pin the worked answers independently, then test the public seam, invalid instructions,
  calendar omission versus blank, incorrect handles, unsupported dates and long input.
- Prove no handle is published and no valuation/market dependency or volatility is added.
  Date, instruction and calendar-cell changes remain normal Excel dependencies.
- Follow existing utility performance probes. Work must not grow one Python iteration
  or allocated date per shifted day; compare small and large valid offsets. Preserve
  payment-creation budgets if existing helpers are touched.
- Add public help and `docs/library/utilities/shift-date.md`; update the utilities listing,
  applicable time documentation, UAT item 9, host replay, smoke and the kept workbook.
  Keep examples explicit about omitted holidays versus a supplied calendar.
- Run the full gate. Preserve existing trade/payment/BAL behavior and existing goldens.

No BAL parsing changes, implicit `as_of`, date-or-text union, mixed ticket-period fields,
custom weekends, intraday offsets, compound instructions, monthly date clamping or
month-end business-day adjustment are included. The helper can be composed in Excel
with explicit start/end dates; it does not change how a trade obtains its booked dates.

## As built

Built in #171. The page is [shift-date.md](../../library/utilities/shift-date.md). The library
helper is `shift_date(date, offset, holidays)` in `src/catalyst/index_definitions/date_offsets.py`,
beside the period grammar: one full match of a sign, ASCII digits and two letters, the suffix
looked up among `bd`, `cd` and `em` in either case, the digits counted before the count is read,
more than seven significant digits refused by their digits, since the sheet's calendar is seven
digits of days, business days or month ends end to end; then one `np.busday_offset` with
`roll="backward"` for a positive count and `"forward"` for a negative one and no roll for zero,
one `np.timedelta64` of days, or the month moved by the count and one and taken as a day less one;
the day made held to the sheet's two days, which moved from `trades/template.py` to
`index_definitions/sheet_days.py`, the template and the resolution reading them there with no
ledger moved. A calendar left out is an empty holiday array to numpy, which takes no absence of
one. The wrapper `util_ShiftDate` in `excel/utilities.py` declares the seam's `Date`, a required
text and `Handle[HolidayCalendar] | None`, the first utility with a handle it may leave out;
nothing new at the seam, nothing published, the help within its limit.

Pinned: the sixteen worked answers, in the library, through the seam, on the smoke's sheet with
the synthetic calendar in PA2, in the host's rows and its fact on a calendar of its own, and in
the kept workbook's rows 1884 to 1905; a nonleap February, offsets across the holiday and back,
mixed-case suffixes, the signed zeros of each suffix on a closed day, leading zeros; the sheet's
first and last days reached from each other and a day past either, by a day, a business day or
a month, refused naming the date and the offset; eight and five thousand digits refused by their
digits, seven read and five thousand leading zeros dropped before the count is read; nineteen
texts that are no offset, an Arabic-Indic digit among them; the round trip of business days from
an open day as a property, the month end's month and the
calendar days' arithmetic likewise; the calendar refused blank, dead or of another kind whatever
the offset; the same calls and the same numpy for one day and for two million, within twice the
slack, nothing published. The payment lag's grammar, the trade creators' ledgers and the kept
goldens are unchanged.
