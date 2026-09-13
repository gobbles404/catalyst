# CreateDiscountCurve

Open: D6, D12, D21, D26, D27, D29, D30.

A daily discount curve, retained and reached by handle. Why these choices, and what they cost, is [decisions.md](../decisions.md#the-discount-curve), D6 to D12 and D30.

## Worksheet contract

The input is a table of two columns, `date` and `df`: one row per calendar day, the first row the curve's start (D6), every day through the last supplied (D7). How that table crosses the seam, and so the signature and the formula a user types, is open: the candidates and what would decide between them are D21. Whatever the layout, the library receives dates as numpy days and factors as numbers, aligned by row, with the seam's checks already made. The result is a handle, text in the cell that stands for the curve held in memory: its spec is [handles.md](../../seam/handles.md), and the declaration `-> DiscountCurve` is what D26 makes registrable.

```excel
Inputs!B2     =CreateDiscountCurve(...)       displays a handle
```

Both arguments required, no defaults. There is no separate valuation-date argument: the first date in the body is the curve's start.

## Excel help

| Item | Text |
|---|---|
| Function | Creates a daily discount-curve handle. Its final date is the library's maximum allowed date. |
| the arguments | one line each, written when D21 names them |

## The library checks

The checks consume typed columns; header interpretation, cell kinds and date conversion are the seam's and are not repeated here. Messages follow the seam's grammar; rows and cells count as `INDEX` counts within the table that was passed, and `values` stands for the body argument until D21 names it.

**Dates** (D7)

| Rule | Message |
|---|---|
| the first date is the curve's start | it is, by definition |
| each following date exactly one calendar day later | `values row 118 is 2026-09-18, expected 2026-09-17, one day after the row above` |

No sorting, no gap filling, no generated factors.

**Factors** (D8, D9)

| Rule | Message |
|---|---|
| `df[0] == 1` exactly | `values cell (1, 2) is 0.98, expected exactly 1 at the curve's first date` |
| non-increasing | `factor rises at values row 412, from 0.91318 to 0.92254` |
| `df[-1] > 0` | `values cell (3631, 2) is 0, expected greater than 0` |

Those three cover the stated rules: `df[0] == 1` with non-increasing already implies `df ≤ 1`, and the minimum of a non-increasing array is its last element. Nothing is clipped, smoothed or rounded. NaN and infinity cannot arrive from a cell; keep the checks for Python callers (D9).

## In memory

Received: what the layout hands over, per [bridge.md](../../seam/bridge.md#the-declared-input-types); with a table it is the schema's record, one typed column per header. Retained:

| Field | Representation |
|---|---|
| dates | `NDArray[np.datetime64]`, dtype `datetime64[D]`, shape `(N,)` |
| factors | `NDArray[np.float64]`, shape `(N,)` |
| `start_date` | `np.datetime64[D]` scalar, `dates[0]`; its name is D6 |
| `max_date` | `np.datetime64[D]` scalar, `dates[-1]`, inclusive (D11) |

The two arrays align by position: `dates[i]` and `factors[i]` describe the same calendar day. Frozen after construction: a later change to an input buffer must not change an existing curve. Numeric validation is vectorized; no per-row Python loops.

## Counted work

This function converts and validates, so it counts. Names and expected values are not yet fixed, and D27 is open on how a counter reaches library code at all. A ten-year curve is 3,631 rows, 7,262 cells, inside the seam's measured range ([baseline.md](../../seam/baseline.md)); the transport is not a concern.

## Tests

| Case | Kind |
|---|---|
| a valid table: every date/factor pair preserved, aligned | example |
| first date is the start; each following date exactly one day later | example |
| consecutive dates spanning weekends, holidays, leap days, year ends | example |
| missing day, duplicate date, reversed rows: rejected, not sorted or filled | example |
| factor at the first date is exactly `1` | example |
| first factor other than `1`: rejected, not rescaled | example |
| zero, negative, above one, NaN, infinity rejected | example |
| `1, 0.9999, 0.9999` accepted; `1, 0.9998, 0.9999` rejected | example |
| all factors equal `1` accepted | example |
| for any valid table, retained arrays are equal length and preserve pairing | property |
| an input buffer changed after construction leaves the curve unchanged | example |
| validation failure publishes no object and no handle | example, with handles |
| a request on `max_date` passes; one after it is rejected, naming both dates | example, with D12 |
| a derived date after `max_date` is rejected against the same curve | example, with D12 |
| constructor handle output, and representative failures, in a real workbook | Excel smoke, with handles |

The daily-coverage and anchor rules are tested independently of generic date acceptance, which is the seam's.

## Open

| | |
|---|---|
| The input layout, and so the signature and the formula | D21 |
| How the bound reaches a calculation, which curve governs when there are several, and dates before the start | D12 |
| Whether `start_date` keeps a name that collides with the valuation date's `as_of` | D6 |
| The smallest table: whether a one-row curve is meaningful | D30 |
| The handle return type, which blocks the whole function | D26 |
| How a work counter reaches this code | D27 |
| The exception type the builder raises | D29 |

## Not here

Intraday interpolation, any use of `day_fraction_elapsed`, a second or projection curve, instruments, pricing.
