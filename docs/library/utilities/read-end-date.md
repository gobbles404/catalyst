# util_ReadEndDate

Built in #129.

Reads the last calendar day of a contract or strip from its label, inclusive: 31 January 2026 for `F26`, 31 March 2027 for `1Q27`, 31 March 2030 for `W29`, and the last day of the right label of `F26-Z28`. Text in and one date out, no object and no handle. It is the twin of [util_ReadStartDate](read-start-date.md), through the same reading of the same grammar, which that page holds in full: the forms, the case rule, the two-digit year, what a range covers and the order its ends must keep. The code is `src/goosedove/index_definitions/periods.py`, `end_date`, and `src/goosedove/excel/utilities.py`, the worksheet function.

## Worksheet contract

```python
def util_ReadEndDate(period: str) -> Date: ...
```

| | A | B |
|---|---|---|
| 1 | f26 | `=util_ReadEndDate(A1)` shows `46053`, 31-Jan-2026 once formatted |
| 2 | G28 | `46812`, 29-Feb-2028, a leap year |
| 3 | W99 | `73140`, 31-Mar-2100, the next century and no wrap |
| 4 | 1Q27-CAL27 | `46752`, 31-Dec-2027 |
| 5 | CAL28-F28 | `#ERROR util_ReadEndDate: ValueError: period is 'CAL28-F28', expected range endpoints in chronological order` |

One argument, required: the label as text, typed or in a cell, which the seam checks as any text scalar, as [inputs.md](../../seam/inputs.md) says; the result is a date, out as its serial, as [outputs.md](../../seam/outputs.md) says, which the cell formats.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Reads the last calendar day of a contract or strip, 31-Jan-2026 for F26, 31-Mar-2030 for W29 and the last day of the right label of F26-Z28. |
| `period` | One contract or strip label, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28, typed or in a cell such as A2. |

## The library checks

The two rules of [util_ReadStartDate](read-start-date.md), run over the whole expression here too, so asking for an end cannot hide a start that is no label, and a reversed range is refused whichever end is asked for.

| Rule | Message |
|---|---|
| each label is one of the forms, with a two-digit year | `period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28` |
| a range's right end starts and ends no earlier than its left | `period is 'CAL28-F28', expected range endpoints in chronological order` |

The last day is the day before the month after the period begins, one conversion of a month to a day and one day subtracted, so a February's own length, a winter's March in the year after and `W99`'s in the next century come from numpy's month unit with nothing counted by hand.

## Tests

The tests are the start reader's, each case asking for both days: `tests/unit/test_periods.py` for the library, `tests/unit/test_utilities.py` for the seam, `tests/unit/test_help.py` for the help, `tools/excel_smoke.ps1` and `host/Goosedove.Host.Tests/CallTests.cs` for a real workbook and its replay, and the two performance files for the ledger, eleven calls across eleven functions for one label and twelve for a range, and the peak, 1,264 bytes for a month and for the whole century alike.

| Case | Kind |
|---|---|
| the last day of every form in the grammar's table, in either case; February in leap years and not; `W99` in the next century | example |
| every malformed label and every reversed range the start reader refuses, refused here with the same words | example |
| for any month, the last day is the day before the next month's first; for any range, the right label's last day | property |
| the last days through the seam as serials, and both refusals in the library's words; the seam's own for a number, a blank and empty text | example, through the seam |
| the last day of the schedule's own `m26`, of a quarter, a year, a winter and two ranges in a real workbook, a reversed range refused | Excel smoke |

## Not here

As [util_ReadStartDate](read-start-date.md) says: expiries, publication and payment days are the schedules'; strips are not built, priced or weighted here; aliases and spaces are refused; the ends of a range are never sorted. The last business day of a period, and a period's days as a column: the [calendar](../calendar/calendar.md) holds every day of its schedule with whether the market is open, and a strip's days as a column wait for the function that averages over them.
