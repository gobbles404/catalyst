# _CreateDiscountCurve

Built in #53; takes anchors since #70.

A daily discount curve, built from the anchors the desk supplies with the days between them filled by a straight line on the factor, retained and reached by handle. What the first pricing function must settle, how a calculation with several curves stays inside their dates, is under Not here. The code is `src/goosedove/globals/discount_curve.py`, the record and its builder, `src/goosedove/globals/interpolation.py`, the filling of the days between, and `src/goosedove/excel/globals.py`, the worksheet function; [util_ReadHandle](../utilities/read-handle.md) spills the daily curve back onto the sheet, which is how a projection is checked.

## Worksheet contract

```python
class DiscountCurveTable(Table):
    date: DateColumn
    discount_factor: NumberColumn


def _CreateDiscountCurve(
    header_row: TextRow, table: DiscountCurveTable
) -> Handle[DiscountCurve]: ...
```

| | A | B |
|---|---|---|
| 1 | date | discount_factor |
| 2 | 22-May-2026 | 1 |
| 3 | 23-May-2026 | 0.9999 |
| 4 | 24-May-2026 | 0.9998 |
| 5 | 29-May-2026 | 0.99929 |
| 6 | `=_CreateDiscountCurve(A1:B1, A2:B5)` | shows `discount_curve:3f9a1c:000002`, a curve of eight days |

The input is a table: a header row, then a body with one row per anchor, the date and its discount factor, the first row the curve's start at exactly 1, dates increasing with any gaps between them. The curve is daily whatever the anchors are: every calendar day from the first anchor to the last, an anchor keeping its factor and a day between two anchors taking the straight line between their factors, weighted by calendar days, as The interpolation below says. A daily table is anchors with no gaps, and makes the curve it always did. The headers bind in either order and capital letters do not matter; the spelling must match, and `df` is not a header. Both arguments required, no defaults. There is no separate valuation-date argument: the first anchor is the curve's start. The seam binds the headers, checks the columns and converts the dates; nothing here restates that. The result is a handle: text in the cell that stands for the curve the seam keeps, declared `Handle[DiscountCurve]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the daily curve; `=util_ReadHandle(B6)` spills its eight days. What is still open about handles, release above all, is [handles.md](../../seam/handles.md).

## Excel help

Quoted from the declaration in `src/goosedove/excel/globals.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a discount curve from anchor dates and their discount factors, every day between filled in, and shows its handle, the text other formulas take as the curve. |
| `header_row` | The header cells of your curve table, such as A1:B1, reading date and discount_factor in either order. |
| `table` | The rows under the headers, such as A2:B12: one anchor per row, its date and discount factor, dates increasing from the valuation date at 1, the factors never rising. |

## The library checks

The checks consume typed columns and run on the anchors, before any day is filled; header interpretation, cell kinds and date conversion are the seam's and are not repeated here. Rows count as the sheet counts them, the first row of the body being row 1, and each message names the column by its header, because the headers bind in either order and the library cannot count a sheet column. The checks run in this order, and the first failure is the message.

| Rule | Message |
|---|---|
| every factor is finite, checked before any arithmetic; a cell cannot send one that is not, so this is for Python callers | `discount_factor row 7 is nan, expected a finite number` |
| `discount_factor[0] == 1` exactly | `discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date` |
| non-increasing; the row named is the one that rose | `discount_factor rises at row 412, from 0.91318 to 0.92254` |
| the last factor is above zero | `discount_factor row 34 is 0.0, expected greater than 0` |
| each date after the row above; a gap of any length is expected | `date row 12 is 2027-01-17, expected a date after row 11's 2027-02-16` |
| the curve holds at most 1,048,574 days, a sheet's rows less the two heading rows `util_ReadHandle` spills first, so whatever is created can be read back | `date row 2 is 4897-08-04, expected within 1048573 days of row 1's 2026-09-11` |

Those cover the stated rules: the first factor at 1 with non-increasing already implies every factor is at most 1, which rules out a curve for negative rates and the owner accepts that, and the minimum of a non-increasing array is its last element; a day filled between two anchors lies between their factors, so the daily curve holds every rule the anchors hold. No sorting, no discarding; nothing is clipped, smoothed or rounded, and a failure builds no curve.

## The interpolation

`interpolate_discount_factors`, in `src/goosedove/globals/interpolation.py`, is the library's and has no worksheet surface: the desk supplies anchors and reads days, and never calls it by name. For adjacent anchors `(date_left, df_left)` and `(date_right, df_right)`, and each whole date `d` between them:

```text
weight = calendar_days(d - date_left) / calendar_days(date_right - date_left)
df(d)  = df_left + weight * (df_right - df_left)
```

Weights count calendar days, weekends and leap days included, the library's one rule for interpolation ([conventions.md](../conventions.md#what-holds-everywhere)). Every anchor keeps its own factor exactly. One day per calendar day from the first anchor through the last, inclusive:

```text
days = calendar_days(last_anchor - first_anchor) + 1
```

No day before the first anchor or after the last: no endpoint extension, no extrapolation. Interpolating on `df` rather than on `log df` is a model choice, not data preparation: the implied forward rate ramps inside each gap and steps at each anchor, about one basis point over a one-year gap in the owner's sample.

[`np.interp`](https://numpy.org/doc/stable/reference/generated/numpy.interp.html) is the implementation. It does not enforce increasing source coordinates, and outside the source range it repeats endpoint values: the builder checks the order first, and asks only for the inclusive range above. Its endpoint behaviour is not permission to accept out-of-range dates. Vectorized throughout; nothing runs per day.

The line is then held above the anchor it runs to. In arithmetic it never falls below that anchor; in `float64`, near underflow, the slope's rounding can take it a step below, and a curve that rose on its last day was a finding of the review of #70. The line never rises above the anchor it runs from, since it adds a non-positive step to it, so the hold is the one bound left to keep; for any ordinary curve it changes nothing, and every anchor is still exact.

The first four anchors of the owner's sample, the table above, give eight days. The gap from May 24 to May 29 spans five calendar-day intervals; the factor change is `0.99929 − 0.9998 = −0.00051`, or `−0.000102` per day.

| date | discount_factor |
|---|---:|
| 2026-05-22 | 1 |
| 2026-05-23 | 0.9999 |
| 2026-05-24 | 0.9998 |
| 2026-05-25 | 0.999698 |
| 2026-05-26 | 0.999596 |
| 2026-05-27 | 0.999494 |
| 2026-05-28 | 0.999392 |
| 2026-05-29 | 0.99929 |

These are mathematical targets; compare with a stated `float64` tolerance. Anchors are preserved exactly. This is a reviewed reference output: it lands as a golden file in its own change, never beside the implementation, and this table goes when it does. The owner's full sample, eleven anchors from 2026-05-22 to 2026-12-18, is a block in `workbooks/handles.xlsx`, whose spill shows all 211 days.

## Tests

The examples and properties below are `tests/unit/test_discount_curve.py` and `tests/unit/test_interpolation.py`; the seam's texts and the handle are `tests/unit/test_globals.py` and `tests/unit/test_handles.py`; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| a daily table: every date/factor pair preserved, aligned | example |
| a gap between anchors is filled a day at a time, on the straight line, the anchors exact | example |
| the owner's eleven anchors: 211 days, every anchor kept exactly, never rising | example |
| consecutive dates spanning a year end and a leap day | example |
| a duplicate date, reversed rows, a step back after a gap: rejected, never sorted | example |
| the longest curve a sheet shows, 1,048,574 days, accepted; one day longer rejected, naming both dates | example |
| the review's anchors near underflow: the curve never rises, its last anchor exact | example |
| factor at the first date is exactly `1` | example |
| first factor other than `1`: rejected, not rescaled | example |
| zero, negative, above one, NaN, infinity rejected | example |
| `1, 0.9999, 0.9999` accepted; `1, 0.9998, 0.9999` rejected | example |
| all factors equal `1` accepted; a one-row curve accepted | example |
| for any daily table, retained arrays are equal length and preserve pairing | property |
| for any anchors, the curve has `days(last − first) + 1` days, one day apart, every anchor kept exactly | property |
| an input changed after construction leaves the curve unchanged, and the curve's arrays refuse writes | example |
| a one-row curve starts and ends on its one day | example |
| the straight line over four days hits every quarter exactly; daily anchors come back as they were; a gap over a leap day; equal anchors give a flat line exactly; one anchor is one day; the anchors are left as they were | example, the interpolation |
| every day from the first anchor to the last once; every anchor keeps its factor exactly; the days never rise, so every day lies between its anchors | property, the interpolation |
| the review's anchors near underflow held at the last anchor; for anchors falling anywhere above zero, subnormals included, the days never rise and every anchor is kept | example and property, the interpolation |
| the worked example above, to tolerance | golden, in its own change |
| the headers bind in either order and either case; a gap filled and shown day by day; dates backwards and a span no sheet could show refused | example, through the seam |
| validation failure publishes no object and no handle | example, with handles |
| the creator's handle over anchors read back day by day, an anchor exact and a day between on the line, dates backwards and a span no sheet could show, in a real workbook | Excel smoke |

The daily-coverage and anchor rules are tested independently of generic date acceptance, which is the seam's.

## Not here

How a calculation with several curves knows which dates it must stay inside, and how it is told: a cash flow outside a curve's dates fails, and with several curves the tightest governs, but which object carries them to the calculation is the first pricing function's page. The start date's name: its field is `as_of`, the same word the valuation date uses for a different thing, and the first consumer of both names it. Extrapolation, any other interpolation basis, intraday interpolation, any use of `day_fraction_elapsed`, a second or projection curve, instruments, pricing. A worksheet function for the interpolation alone: the owner declined one, and `util_ReadHandle` shows the days a curve was given.
