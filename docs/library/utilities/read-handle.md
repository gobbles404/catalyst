# util_ReadHandle

Built in #66.

Reads the object a handle stands for onto the sheet as a table, a header row, a row of types, then one row per element: the table its creator took, or, for a curve, the daily table the creator built from the anchors it took, every day between them. It is how a person sees what is in memory, checks a block before stacking the next one on it, and hands an engineer the exact thing a formula holds. `util_ReadDiscountFactor` went with it: it existed only to prove that a handle resolves, and reading a whole curve proves that better than reading one day of it. The code is `src/goosedove/excel/utilities.py`, the function and the table each kind shows.

## Worksheet contract

```python
def util_ReadHandle(handle: Handle[object]) -> MixedArray: ...
```

`Handle[object]` is the seam's form for a handle of any kind, built in #64 ([inputs.md](../../seam/inputs.md) decision 40): the function receives the object whatever its kind, and every failure keeps the seam's words with no kind to name. `MixedArray` as a result is the mirror of the way in, built in #65 ([outputs.md](../../seam/outputs.md) decision 13): the rectangle spills one tagged value per cell, and `MixedArray.table` builds it from the headings and the object's columns.

| | A | B |
|---|---|---|
| 1 | date | discount_factor |
| 2 | 11-Sep-2026 | 1 |
| 3 | 12-Sep-2026 | 0.9999 |
| 4 | 13-Sep-2026 | 0.9998 |
| 5 | `=_CreateDiscountCurve(A1:B1, A2:B4)` | shows `discount_curve:3f9a1c:000002` |
| 7 | `=util_ReadHandle(B5)` | spills A7:B11, below |

| | A | B |
|---|---|---|
| 7 | date | discount_factor |
| 8 | datetime64[D] | float64 |
| 9 | 11-Sep-2026 | 1 |
| 10 | 12-Sep-2026 | 0.9999 |
| 11 | 13-Sep-2026 | 0.9998 |

One argument, required: any live handle, the cell showing a creator's result or a name for it. The seam resolves it to the object, and every failure is the seam's, in the seam's words: a number or a blank where the handle should be, text naming no live object, or a creator's failure relayed by the reference. The result spills as returned: dates go out as Excel dates, serials the sheet formats, as every date the seam sends does, so a fresh column shows `46276` until it is formatted once; the row of types says which columns to format. Rows 7 and 9 to 11 are the daily table `_CreateDiscountCurve` built, which as anchors with no gaps is one it takes, so `=_CreateDiscountCurve(A7:B7, A9:B11)` makes an equal curve: a spill can be fed back to a creator. A curve built from sparse anchors spills its days, not its anchors, since #70.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Reads the object behind a handle and spills it as a table: its headers, a row of types, then one row per element. |
| `handle` | The cell showing any creator's result, such as B5, or a name for it. |

## The library checks

None. Every kind the library publishes has a table, so there is no object the inspector cannot show, and a handle that resolves is shown; a handle that does not resolve fails in the seam's words before the function runs.

## The table

The first row is the headers, in the creator's own words: the headers its table took, or its parameter names. The rows are what the object holds, which for a curve is every day the creator filled between its anchors. The second row is the type of what the object holds in each column, in numpy's words where numpy holds it and Python's where Python does. Then one row per element, aligned across the columns as the object aligns them; a scalar field is a column of one row. A column the creator was given none of is not shown, and what a kind keeps only to make a lookup fast, such as the curve's day count of its start, is not a fact of the object and is not shown. Nothing is sorted, rounded or reformatted.

What each kind shows:

| Kind | Headers | Types | Rows |
|---|---|---|---|
| `valuation_date` | `as_of`, `day_fraction_elapsed` | `datetime64[D]`, `float` | one |
| `discount_curve` | `date`, `discount_factor` | `datetime64[D]`, `float64` | one per calendar day, the anchors and every day filled between them |
| `expiry_schedule` | `future_code`, `future_expiry`, and `option_expiry` when the index has options | `str`, `datetime64[D]`, `datetime64[D]` | one per contract |
| `holiday_calendar` | `holiday` | `datetime64[D]` | one per holiday |
| `index_conventions` | `quote_currency_unit`, `quote_quantity_unit`, `currency_unit`, `quantity_type`, `quantity_unit` | `str` five times | one |
| `contract_spec` | `name`, `lot_size`, `brokerage_rate_per_lot`, `clearing_rate_per_lot` | `str`, `int`, `float`, `float` | one |
| `futures_curve` | `future_code`, `price` | `str`, `float64` | one per contract |
| `daily_fixings` | `date`, `settle` | `datetime64[D]`, `float64` | one per fixing |

`=util_ReadHandle(B2)` on `=_CreateValuationDate(A2, 0.5)`:

| as_of | day_fraction_elapsed |
|---|---|
| datetime64[D] | float |
| 11-Sep-2026 | 0.5 |

`=util_ReadHandle(A8)` on the six-contract schedule of [expiry-schedule.md](../index-definitions/expiry-schedule.md), and the same schedule built without options shows the first two columns alone:

| future_code | future_expiry | option_expiry |
|---|---|---|
| str | datetime64[D] | datetime64[D] |
| m26 | 19-May-2026 | 14-May-2026 |
| n26 | 22-Jun-2026 | 16-Jun-2026 |
| q26 | 21-Jul-2026 | 16-Jul-2026 |
| u26 | 20-Aug-2026 | 17-Aug-2026 |
| V26 | 22-Sep-2026 | 17-Sep-2026 |
| X26 | 20-Oct-2026 | 15-Oct-2026 |

`=util_ReadHandle(A12)` on the ten-day calendar of [holiday-calendar.md](../index-definitions/holiday-calendar.md) shows one column, `holiday` over `datetime64[D]`, then the ten days as given.

A new kind adds its row to this table on the pull request that builds its creator, and the same row in code: each kind registers how it shows in `src/goosedove/excel/utilities.py`, and a kind nobody registered fails in the cell, `#ERROR util_ReadHandle: TypeError: no table for a Widget`, rather than guessing its columns.

## Tests

The tests are `tests/unit/test_utilities.py`, through the seam; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1`, reading each spill with `INDEX`, and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| a valuation date: the two headers, the two types, one row, the date and the fraction exactly | example |
| the three-day curve: the two headers, the two types, three rows, dates as serials, factors exactly | example |
| the six-contract schedule with options: three columns; without options: two | example |
| a three-day calendar: one column of dates under its two heading rows | example |
| index conventions: one row of five texts under its two heading rows | example |
| a contract spec: one row, the name as text and the lot size and fees as numbers, under its two heading rows | example |
| a futures curve: two columns, the code as text and the price exactly, one row per contract under its two heading rows | example |
| daily fixings: two columns, dates as serials and settles exactly, one row per day under its two heading rows | example |
| a curve's spill, headers and body, fed back to `_CreateDiscountCurve` gives a curve with equal dates and factors | example, through the seam |
| for any valid curve of N days, the spill is N + 2 rows by 2 columns, headers first, types second, and row i + 2 holds day i and its factor | property |
| a number, a blank, text naming no live object, a creator's failure relayed: the seam's words, and nothing spilled | example, through the seam |
| a kind with no table fails in the cell rather than guessing; every kind a creator publishes has one | example |
| each kind inspected on a real sheet, with a schedule without options and a calendar of one day | Excel smoke |

## Not here

The kind's name and the handle's text: the creator's cell shows both, and the count is the spill's height. Formatting the spilled cells: the sheet's. A filter, a range of rows, or a second argument: the whole object spills, every time. Editing an object through its spill; the internals a kind keeps to make a lookup fast; the text of a handle typed by hand.
