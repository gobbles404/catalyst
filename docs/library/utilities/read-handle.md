# ReadHandle

Waiting on the seam: a mixed array out.

Reads the object a handle stands for onto the sheet as the table its creator took: a header row, a row of types, then one row per element. It is how a person sees what is in memory, checks a block before stacking the next one on it, and hands an engineer the exact thing a formula holds. When it is built, `util_ReadDiscountFactor` goes: its page says it exists only to prove that a handle resolves, and reading a whole curve proves that better than reading one day of it.

## Worksheet contract

```python
def ReadHandle(handle: Handle[object]) -> MixedArray: ...
```

`Handle[object]` is the seam's form for a handle of any kind, built in #64 ([inputs.md](../../seam/inputs.md) decision 40): the function receives the object whatever its kind, and every failure keeps the seam's words with no kind to name. `MixedArray` as a result, the mirror of the way in, is the one seam item this waits on, in the recommended form, engineering's to settle.

| | A | B |
|---|---|---|
| 1 | date | discount_factor |
| 2 | 11-Sep-2026 | 1 |
| 3 | 12-Sep-2026 | 0.9999 |
| 4 | 13-Sep-2026 | 0.9998 |
| 5 | `=CreateDiscountCurve(A1:B1, A2:B4)` | shows `discount_curve:3f9a1c:000002` |
| 7 | `=ReadHandle(B5)` | spills A7:B11, below |

| | A | B |
|---|---|---|
| 7 | date | discount_factor |
| 8 | datetime64[D] | float64 |
| 9 | 11-Sep-2026 | 1 |
| 10 | 12-Sep-2026 | 0.9999 |
| 11 | 13-Sep-2026 | 0.9998 |

One argument, required: any live handle, the cell showing a creator's result or a name for it. The seam resolves it to the object, and every failure is the seam's, in the seam's words: a number or a blank where the handle should be, text naming no live object, or a creator's failure relayed by the reference. The result spills as returned: dates go out as Excel dates, serials the sheet formats, as every date the seam sends does, so a fresh column shows `46276` until it is formatted once; the row of types says which columns to format. Rows 7 and 9 to 11 are the table `CreateDiscountCurve` took, so `=CreateDiscountCurve(A7:B7, A9:B11)` makes an equal curve: a spill can be fed back to a creator.

## Excel help

The lines go beside the parameter in the declaration when the function is built, as [conventions.md](../conventions.md#excel-help) says, and `tests/unit/test_help.py` pins them.

| Item | Text |
|---|---|
| Function | Reads the object behind a handle and spills it as a table: its headers, a row of types, then one row per element. |
| `handle` | The cell showing any creator's result, such as B5, or a name for it. |

## The library checks

None. Every kind the library publishes has a table, so there is no object the inspector cannot show, and a handle that resolves is shown; a handle that does not resolve fails in the seam's words before the function runs.

## The table

The first row is the headers, in the creator's own words: the headers its table took, or its parameter names. The second row is the type of what the object holds in each column, in numpy's words where numpy holds it and Python's where Python does. Then one row per element, aligned across the columns as the object aligns them; a scalar field is a column of one row. A column the creator was given none of is not shown, and what a kind keeps only to make a lookup fast, such as the curve's day count of its start, is not a fact of the object and is not shown. Nothing is sorted, rounded or reformatted.

What each kind shows:

| Kind | Headers | Types | Rows |
|---|---|---|---|
| `valuation_date` | `as_of`, `day_fraction_elapsed` | `datetime64[D]`, `float` | one |
| `discount_curve` | `date`, `discount_factor` | `datetime64[D]`, `float64` | one per calendar day |
| `expiry_schedule` | `future_code`, `future_expiry`, and `option_expiry` when the index has options | `str`, `datetime64[D]`, `datetime64[D]` | one per contract |

`=ReadHandle(B2)` on `=CreateValuationDate(A2, 0.5)`:

| as_of | day_fraction_elapsed |
|---|---|
| datetime64[D] | float |
| 11-Sep-2026 | 0.5 |

`=ReadHandle(A8)` on the six-contract schedule of [expiry-schedule.md](../market-definitions/expiry-schedule.md), and the same schedule built without options shows the first two columns alone:

| future_code | future_expiry | option_expiry |
|---|---|---|
| str | datetime64[D] | datetime64[D] |
| m26 | 19-May-2026 | 14-May-2026 |
| n26 | 22-Jun-2026 | 16-Jun-2026 |
| q26 | 21-Jul-2026 | 16-Jul-2026 |
| u26 | 20-Aug-2026 | 17-Aug-2026 |
| V26 | 22-Sep-2026 | 17-Sep-2026 |
| X26 | 20-Oct-2026 | 15-Oct-2026 |

A new kind adds its row to this table on the pull request that builds its creator.

## Tests

| Case | Kind |
|---|---|
| a valuation date: the two headers, the two types, one row, the date and the fraction exactly | example |
| the three-day curve: the two headers, the two types, three rows, dates as serials, factors exactly | example |
| the six-contract schedule with options: three columns; without options: two | example |
| a curve's spill, headers and body, fed back to `CreateDiscountCurve` gives a curve with equal dates and factors | example, through the seam |
| for any valid curve of N days, the spill is N + 2 rows by 2 columns, headers first, types second, and row i + 2 holds day i and its factor | property |
| a number, a blank, text naming no live object, a creator's failure relayed: the seam's words, and nothing spilled | example, through the seam |
| each of the three kinds inspected on a real sheet, and a schedule without options | Excel smoke |

## Not here

The kind's name and the handle's text: the creator's cell shows both, and the count is the spill's height. Formatting the spilled cells: the sheet's. A filter, a range of rows, or a second argument: the whole object spills, every time. Editing an object through its spill; the internals a kind keeps to make a lookup fast; the text of a handle typed by hand.
