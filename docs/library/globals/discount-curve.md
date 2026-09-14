# CreateDiscountCurve

Built in #53.

A daily discount curve, retained and reached by handle. Why these choices, and what they cost, is [decisions.md](../decisions.md#the-discount-curve), D6 to D12, and D21 for its table. The code is `src/goosedove/globals/discount_curve.py`, the record, its builder and the reader's lookup, and `src/goosedove/excel/globals.py`, the worksheet functions.

## Worksheet contract

```python
class DiscountCurveTable(Table):
    date: DateColumn
    discount_factor: NumberColumn


def CreateDiscountCurve(
    header_row: TextRow, table: DiscountCurveTable
) -> Handle[DiscountCurve]: ...
```

| | A | B |
|---|---|---|
| 1 | date | discount_factor |
| 2 | 11-Sep-2026 | 1 |
| 3 | 12-Sep-2026 | 0.9999 |
| 4 | 13-Sep-2026 | 0.9998 |
| 5 | `=CreateDiscountCurve(A1:B1, A2:B4)` | shows `discount_curve:3f9a1c:000002` |

The input is a table (D21): a header row, then a body with one row per calendar day, the date and its discount factor, the first row the curve's start (D6), every day through the last supplied (D7). The headers bind in either order and capital letters do not matter; the spelling must match, and `df` is not a header. Both arguments required, no defaults. There is no separate valuation-date argument: the first date in the body is the curve's start. The seam binds the headers, checks the columns and converts the dates; nothing here restates that. The result is a handle: text in the cell that stands for the curve the seam keeps, declared `Handle[DiscountCurve]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the curve. What is still open about handles, release above all, is [handles.md](../../seam/handles.md) and D26.

## Excel help

Quoted from the declaration in `src/goosedove/excel/globals.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a daily discount-curve handle. Its last date is the latest the library prices. |
| `header_row` | One row holding the two headers, date and discount_factor, in either order; capitals do not matter. |
| `table` | The body under the headers: one row per calendar day, the date and its discount factor, no day missing. The first factor is 1, and factors never rise and stay above 0. |

## The library checks

The checks consume typed columns; header interpretation, cell kinds and date conversion are the seam's and are not repeated here. Rows count as the sheet counts them, the first row of the body being row 1, and each message names the column by its header, because the headers bind in either order and the library cannot count a sheet column. Every rejection raises `ValueError` (D29). The checks run in this order, and the first failure is the message.

| Rule | Message |
|---|---|
| every factor is finite, checked before any arithmetic; a cell cannot send one that is not, so this is for Python callers | `discount_factor row 7 is nan, expected a finite number` |
| `discount_factor[0] == 1` exactly (D8) | `discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date` |
| non-increasing (D9); the row named is the one that rose | `discount_factor rises at row 412, from 0.91318 to 0.92254` |
| the last factor is above zero (D9) | `discount_factor row 3631 is 0.0, expected greater than 0` |
| each date exactly one calendar day after the row above (D7); the first date is the start by definition | `date row 118 is 2026-09-18, expected 2026-09-17, one day after the row above` |

Those cover the stated rules: the first factor at 1 with non-increasing already implies every factor is at most 1, and the minimum of a non-increasing array is its last element. No sorting, no gap filling, no generated factors; nothing is clipped, smoothed or rounded.

## In memory

Received: the schema's record, one typed column per header, per [bridge.md](../../seam/bridge.md#the-declared-input-types): `date` as an array of numpy days, `discount_factor` as a view of the table's storage. Retained, after the checks pass:

| Field | Representation |
|---|---|
| `dates` | `NDArray[np.datetime64]`, dtype `datetime64[D]`, shape `(N,)`, a copy, read-only |
| `factors` | `NDArray[np.float64]`, shape `(N,)`, a copy, read-only |
| `start_ordinal` | the start date as numpy counts days, an `int`, so a day becomes an index in one subtraction |
| `start_date`, `max_date` | properties over `dates[0]` and `dates[-1]`, the latter inclusive (D11); the start's name is D6 |

The two arrays align by position: `dates[i]` and `factors[i]` describe the same calendar day. Both are copied, because the seam's factors column is a view of the whole two-column table and a Python caller keeps whatever it passed, and both are frozen, so a later change to an input never changes a curve. Numeric validation is vectorized; no per-row Python loops. The curve is held in the seam's store until Excel closes; release is D26.

## Counted work

The builder takes no `WorkCounter` (D27, deferred by the owner); its work is pinned at the seam. `tests/performance/test_seam_budgets.py` pins a ten-year curve, 3,631 rows, at the table path plus the builder and one publication, and on the numpy ledger at five looks, one per column and one per rule, the date column's two conversions, the two copies the curve keeps, and the start's one scalar conversion. `tests/performance/test_seam_allocation.py` pins its peak at 36 bytes per day plus the slack, measured 129,027 bytes on 2026-09-14: the two arrays at 16 bytes per day, and the table path's conversion of the date column and the builder's masks on the way. On the Python clock a ten-year curve takes about 90 microseconds to build. The transport of 7,262 cells is inside the seam's measured range ([baseline.md](../../seam/baseline.md)).

## A temporary reader

`util_ReadDiscountFactor(curve, date)` returns the factor for one calendar day the curve covers, `=util_ReadDiscountFactor(B5, A3)` showing `0.9999` in the sheet above. It exists to prove that a handle resolves to its curve on a real sheet, and it goes when a real consumer of a curve exists; `util_` leads the name at the owner's word. A day outside the curve's dates, before the start or after the end alike, fails, `#ERROR util_ReadDiscountFactor: ValueError: date is 2026-09-20, expected a date from 2026-09-11 to 2026-09-13, the curve's first and last`, which is the hard upper bound (D11) and, for a day before the start, the reader's own rule, noted under D12. The seam's own failures come first, in the order [inputs.md](../../seam/inputs.md) decision 35 gives: a number or a blank where the handle should be, text naming no live object, a handle of another kind, or a creator's failure relayed by the reference. The reader is a text call plus one lookup, pinned in the same two files, measured 1,208 bytes; on the Python clock it takes about 5 microseconds. Its Excel help, quoted from the declaration: `curve`, "The cell holding a discount-curve handle, or a name for that cell."; `date`, "One date between the curve's first and last dates, inclusive."

## Tests

The examples and properties below are `tests/unit/test_discount_curve.py`; the seam's texts, the handle and the reader are `tests/unit/test_globals.py` and `tests/unit/test_handles.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`.

| Case | Kind |
|---|---|
| a valid table: every date/factor pair preserved, aligned | example |
| first date is the start; each following date exactly one day later | example |
| consecutive dates spanning a year end and a leap day | example |
| missing day, duplicate date, reversed rows: rejected, not sorted or filled | example |
| factor at the first date is exactly `1` | example |
| first factor other than `1`: rejected, not rescaled | example |
| zero, negative, above one, NaN, infinity rejected | example |
| `1, 0.9999, 0.9999` accepted; `1, 0.9998, 0.9999` rejected | example |
| all factors equal `1` accepted; a one-row curve accepted | example |
| for any valid table, retained arrays are equal length and preserve pairing | property |
| an input changed after construction leaves the curve unchanged, and the curve's arrays refuse writes | example |
| the headers bind in either order and either case | example, through the seam |
| validation failure publishes no object and no handle | example, with handles |
| a read on `max_date` passes; one day after, and one day before the start, is rejected naming both dates | example |
| the creator's handle, its failures, and the reader in a real workbook | Excel smoke |

The daily-coverage and anchor rules are tested independently of generic date acceptance, which is the seam's.

## Open

| | |
|---|---|
| How the bound reaches a calculation, which curve governs when there are several, and dates before the start | D12 |
| Whether `start_date` keeps a name that collides with the valuation date's `as_of` | D6 |
| Release of the curve when its creator is deleted or its workbook closes, and reuse on an unchanged recalculation | D26 |
| How a work counter reaches this code | D27 |

## Not here

Intraday interpolation, any use of `day_fraction_elapsed`, a second or projection curve, instruments, pricing.
