# CreateDiscountCurve

**Normative.** A daily discount curve, retained and reached by handle. Why these choices,
and what they cost, is in [decisions.md](../decisions.md#the-discount-curve) — D6 to D12.

Not implemented. Not buildable until the seam can return a handle (D26) and the table
shape is decided (D21).

## Worksheet contract

The shape below is the one currently written down. **D21 is open and may change it**; the
alternatives under consideration need no new seam machinery, and whichever is chosen
applies to the [interpolation utility](../utilities/interpolate-discount-factors.md) too.

```python
def CreateDiscountCurve(header_row: TextRow, values: NumberArray) -> DiscountCurve: ...
```

```excel
Data!A1:B1    date / df headers
Data!A2:B15   the daily table
Inputs!B2     =CreateDiscountCurve(Data!A1:B1, Data!A2:B15)
```

Both arguments required, no defaults. The first date in the body is the curve's start;
there is no separate valuation-date argument.

| Argument | Shape |
|---|---|
| `header_row` | one row of two text column names |
| `values` | a non-empty two-dimensional numeric body, two columns, one date/factor pair per row, headers excluded |

## The seam checks

Write no code and no test for anything in this section. The rules are
[inputs.md](../../seam/inputs.md).

| Argument | Declared | Accepts | Rejects |
|---|---|---|---|
| `header_row` | `TextRow` | a one-row range of non-empty text, handed over as `tuple[str, ...]` | a column, a taller range, a number, a boolean, a blank, an empty text cell, missing |
| `values` | `NumberArray` | a range of numbers, any shape, handed over as `NDArray[np.float64]` in sheet order | any blank, text or boolean cell, named as `INDEX` counts; missing |

The messages, produced by running the seam:

```text
header_row is 2x1 array, expected row of text
header_row is 2x2 array, expected row of text
header_row cell (1, 2) is number 5.0, expected text
header_row cell (1, 2) is empty text, expected text
header_row cell (1, 2) is blank, expected text
header_row is missing, expected row of text
values cell (1, 1) is text 'date', expected number
values cell (2, 2) is blank, expected number
values cell (1, 2) is boolean TRUE, expected number
values is missing, expected array of numbers
```

**What the seam lets through, by design** — all of it is meaning, and all of it is the
library's to catch:

| Passes the seam | Why |
|---|---|
| three headers against a two-column body | the seam checks each argument alone |
| headers named `Maturity` and `Mid` | names are meaning |
| a one-column body, or a single cell as a 1×1 | any shape is a valid `NumberArray` |
| scalar text as `header_row` — `=CreateDiscountCurve("date", …)` | one text is a one-element row |
| a fractional date serial such as `46164.5` | in a `NumberArray` a date is just a number |
| a serial outside the calendar, such as `60` | the same |
| a factor of `1.5` | the seam never compares a value to a bound |

## The library checks

Write all of this, and one test for each row. Messages are proposed and follow the seam's
grammar; row and column references count the way `INDEX` does, from 1 within the passed
range, because no sheet address crosses the seam.

**Headers** (D19)

| Rule | Message |
|---|---|
| exactly two headers, matching the body's column count | `header_row has 3 names for 2 columns of values` |
| both `date` and `df` present, matched without regard to case | `header_row cell (1, 2) is 'Mid', expected date or df` |
| no duplicates after case-insensitive matching | `header_row names df twice, as 'df' and 'DF'` |

**Dates** (D7) — *these depend on D21.* Under the current shape the library receives raw
serials and has nowhere to convert them from; that is the open question, not a rule to
write yet.

| Rule | Message |
|---|---|
| every date a whole serial inside Excel's calendar | `values cell (4, 1) is 46164.5, expected a whole date serial` |
| the first date is the curve's start | — it is, by definition |
| each following date exactly one calendar day later | `values row 118 is 2026-09-18, expected 2026-09-17, one day after the row above` |

No sorting, no gap filling, no generated factors.

**Factors** (D8, D9)

| Rule | Message |
|---|---|
| `df[0] == 1` exactly | `values cell (1, 2) is 0.98, expected exactly 1 at the curve's first date` |
| non-increasing | `factor rises at values row 412, from 0.91318 to 0.92254` |
| `df[-1] > 0` | `values cell (3631, 2) is 0, expected greater than 0` |

Those three cover the stated rules: `df[0] == 1` with non-increasing already implies
`df ≤ 1`, and the minimum of a non-increasing array is its last element. Nothing is
clipped, smoothed or rounded. NaN and infinity cannot arrive from a cell; keep the checks
for Python callers (D9).

## In memory

| Stage or field | Representation |
|---|---|
| `header_row` at the seam | `tuple[str, ...]`, two entries |
| `values` at the seam | `NDArray[np.float64]`, shape `(N, 2)`; dates still serials |
| retained dates | `NDArray[np.datetime64]`, dtype `datetime64[D]`, shape `(N,)` |
| retained factors | `NDArray[np.float64]`, shape `(N,)` |
| `start_date` | `np.datetime64[D]` scalar — `dates[0]` |
| `max_date` | `np.datetime64[D]` scalar — `dates[-1]`, inclusive (D11) |

The two arrays align by position: `dates[i]` and `df[i]` describe the same calendar day.
Frozen after construction — a later change to an input buffer must not change an existing
curve. Numeric validation is vectorized; no per-row Python loops.

## Counted work

This function converts and validates, so it counts. Names and expected values are not yet
fixed, and D27 is open on how a counter reaches library code at all.

For reference, a 3,631-row table costs the seam roughly 7,264 cells scanned, 65,358 buffer
bytes, and 3 trips (two ranges, per the measured `Dot` row in
[host-work.csv](../../seam/baseline/host-work.csv)). That is the same order as the
existing 10,000-cell control, so the transport is not a concern.

## Excel help

Wording is provisional until D19 and D21 close. Each string must fit Excel's
argument-help limit of about 255 characters; **the `values` draft below is 292 and has to
be cut.**

| Item | Text |
|---|---|
| Function | Creates a daily discount-curve handle. Its final date is the library's maximum allowed date. |
| `header_row` | One row containing date and df. Header matching ignores case; duplicate or unknown names fail. Required. |
| `values` | Two numeric columns matching the headers. Start at the curve's first date with factor 1; include every calendar day without gaps. Factors must be greater than 0, at most 1, and non-increasing; equal values are allowed. Exclude headers. Required. |

## Tests

| Case | Kind | Where |
|---|---|---|
| a blank, text or boolean cell in a numeric range is named as `INDEX` counts | example | passes today — `test_failure_names_argument_arrival_and_expectation` |
| a `NumberArray` keeps its sheet shape and order | example | passes today — `test_array_keeps_the_shape_on_the_sheet`, `test_nothing_is_reordered` |
| a text row is handed over as a tuple; empty text and wrong shape rejected | example | passes today — `test_text_is_handed_over_as_a_tuple`, `test_rejected` |
| valid header row and matching body preserve every date/factor pair | example | new |
| header casing changed only — same interpreted columns | example | new |
| unknown, missing, duplicate or extra header rejected | example | new |
| duplicates differing only in case rejected | example | new |
| header count and body width disagree — rejected, no column dropped | example | new |
| first date is the start; each following date exactly one day later | example | new |
| consecutive dates spanning weekends, holidays, leap days, year ends | example | new |
| missing day, duplicate date, reversed rows — rejected, not sorted or filled | example | new |
| factor at the first date is exactly `1` | example | new |
| first factor other than `1` — rejected, not rescaled | example | new |
| zero, negative, above one, NaN, infinity rejected | example | new |
| `1, 0.9999, 0.9999` accepted; `1, 0.9998, 0.9999` rejected | example | new |
| all factors equal `1` accepted | example | new |
| for any valid table, retained arrays are equal length and preserve pairing | property | new |
| an input buffer changed after construction leaves the curve unchanged | example | new |
| validation failure publishes no object and no handle | example | new, needs handles |
| a request on `max_date` passes; one after it is rejected, naming both dates | example | new, needs D12 |
| a derived date after `max_date` is rejected against the same curve | example | new, needs D12 |
| constructor handle output, and representative failures, in a real workbook | Excel smoke | new, needs handles |

Three already pass. Do not restate the seam's type and shape matrix. The daily-coverage
and anchor rules are tested independently of generic date acceptance.

## Open

| | |
|---|---|
| How the table crosses the seam, which decides the signature and the date rules | D21 |
| Header whitespace, and whether columns may be reordered | D19 |
| How the bound reaches a calculation, and which curve governs when there are several | D12 |
| Behaviour for dates before the curve's start | D12 |
| Whether `start_date` should be renamed out of its collision with the valuation date's `as_of` | D6 |
| Minimum row count — whether a one-row curve is meaningful | — |
| The handle return type, which blocks the whole function | D26 |

Not covered by this specification: intraday interpolation, any use of
`day_fraction_elapsed`, a second or projection curve, instruments, pricing.
