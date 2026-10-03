# util_DateToFut

Built in #129.

Gives the contract code of the month a day falls in: `F26` for any day of January 2026, `K26` for 19 May 2026. One date in and text out, no object and no handle: the desk turns a date it holds, a valuation day, an expiry, a flow day, into the code of that month, to label a column or to feed [util_FutToCme](fut-to-cme.md) and [util_NextFut](next-fut.md). It is the day's own month and nothing more: 19 May 2026 is the day WTI's June contract expires, and this function says `K26`, May's code, since it reads a day and knows no schedule; which contract expires or is prompt on a day is the [calendar](../calendar/calendar.md)'s to say. The code is `src/goosedove/index_definitions/contract_codes.py`, `code_of_month`, and `src/goosedove/excel/utilities.py`, the worksheet function.

## Worksheet contract

```python
def util_DateToFut(date: Date) -> str: ...
```

| | A | B |
|---|---|---|
| 1 | 15-Jan-2026 | `=util_DateToFut(A1)` shows `F26` |
| 2 | 19-May-2026 | `=util_DateToFut(A2)` shows `K26` |
| 3 | 31-Dec-2026 | `=util_DateToFut(A3)` shows `Z26` |
| 4 | 1-Jan-2100 | `=util_DateToFut(A4)` shows `#ERROR util_DateToFut: ValueError: date is 2100-01-01, expected a day from 2000 to 2099, the years a two-digit code can name` |

One argument, required: one day, a cell holding a date or `DATE(2026,1,15)`, which the seam takes as it takes any single date, a whole serial inside the sheet's calendar, refusing a time, text, a blank and a range in its own words, `date is number 46276.5, expected date`, as [inputs.md](../../seam/inputs.md) says; nothing here restates that. The result is text, the letter in capitals, since a day carries no case to keep, as [outputs.md](../../seam/outputs.md) sends text.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Gives the contract code of the month a day falls in, F26 for any day of January 2026. |
| `date` | One day, such as A2 or DATE(2026,1,15): any day of the contract's month. |

## The library checks

One rule: the day is of a year two digits can name, 2000 to 2099, since a code's year is two digits after 2000 and `F00` means January 2000 and nothing else. The day is read as the count of months since January 1970, one conversion as numpy counts them, and the year and the month fall out of that count; no calendar is built and no table looked up.

| Rule | Message |
|---|---|
| a day from 2000 to 2099 | `date is 1999-12-31, expected a day from 2000 to 2099, the years a two-digit code can name` |

Every other day of the century has a code, a leap day and a year's last day included, and every day of a month has the same one.

## Tests

The library's examples and property are `tests/unit/test_contract_codes.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the first, a middle and the last day of January; the last of February and a leap day; 19 May, a WTI June expiry, as May's code; a year's last day; the first and the last day two digits name; April as `J` | example |
| days of 1999, 1970, 1900, 2100 and 2150: refused naming the day | example |
| for any day of the century, the first day of its code's month is the first of its own month, the code of that first day is the code again, and the CME month agrees | property |
| a day in and a code out through the seam, and the days of 1999 and 2100 refused in the library's words; left out, blank, a time, text, a boolean and a range in the seam's | example, through the seam |
| nine calls across nine functions and two numpy conversions; a peak within the slack, measured 870 bytes, and nothing published | budget |
| `K26` for m26's expiry day, `U26` for 11 September and `Z26` for the year's last day in a real workbook, a day of 2100 refused, and a time, text and a blank where the day should be | Excel smoke |

## Not here

The contract expiring or prompt on a day, which may be the next month's: the [calendar](../calendar/calendar.md)'s, through the schedule. A lowercase code: the day carries no case, and the code is in capitals. A date before 2000 or after 2099. The day's product root and the whole symbol a feed takes: the desk's formula joins them.
