# util_FutToDate

Built in #129.

Gives the first day of a contract's month as a date: 1 January 2026 for `F26`, 1 July 2026 for `n26`. Text in and one date out, no object and no handle: the desk turns a code it holds into a date to count from, to place on an axis or to compare with a day. The first day is the one day a code names on its own; a contract's expiry is its [schedule](../index-definitions/futures-schedule.md)'s to say, and this function knows no schedule. It reads the code through the same reading as [util_NextFut](next-fut.md) and takes the same one form, a month letter and a two-digit year. The code is `src/catalyst/index_definitions/contract_codes.py`, `first_day_of`, and `src/catalyst/excel/utilities.py`, the worksheet function, the first to send one date back to the sheet.

## Worksheet contract

```python
def util_FutToDate(contract: str) -> Date: ...
```

| | A | B |
|---|---|---|
| 1 | F26 | `=util_FutToDate(A1)` shows `46023`, 1-Jan-2026 once the cell is formatted as a date |
| 2 | n26 | `=util_FutToDate(A2)` shows `46204`, 1-Jul-2026 |
| 3 | Cal27 | `=util_FutToDate(A3)` shows `#ERROR util_FutToDate: ValueError: contract is 'Cal27', expected a month letter and a two-digit year, such as F26` |

One argument, required: a contract code as text, typed in the formula or in a cell, which the seam checks as it checks any text scalar, as [inputs.md](../../seam/inputs.md) says, refusing a number, a blank, empty text and a range in its own words; nothing here restates that. The result is a date, which goes out as its serial, as every date the seam sends does, so a fresh cell shows `46023` until it is formatted once, as [outputs.md](../../seam/outputs.md) says; a cell formatted as a date shows 1-Jan-2026. The letter is read in either case, `n26` and `N26` naming one month.

## Excel help

Quoted from the declaration in `src/catalyst/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Gives the first day of a contract's month as a date, 1-Jan-2026 for F26. |
| `contract` | One contract code, a month letter and a two-digit year such as F26, typed or in a cell such as A2. |

## The library checks

One rule, the reading's: a code is one month letter and two digits, nothing before, between or after, as [util_NextFut](next-fut.md) says in full; a strip, a season, a four-digit year and a letter that is no month are refused naming what arrived. Every code the reading takes has a first day, `Z99` included, 1 December 2099.

| Rule | Message |
|---|---|
| one month letter and two digits | `contract is 'Cal27', expected a month letter and a two-digit year, such as F26` |

## Tests

The library's examples and property are `tests/unit/test_contract_codes.py`; the seam's texts are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| January, a leap February, a lowercase June and July, December, the first and the last month two digits name: the first day each, a date of days | example |
| a strip, a season, a four-digit year and a leading space: refused naming what arrived | example |
| for any day of the century, the first day of its code's month is the first of its own month, in capitals or in lowercase | property |
| a code in and a serial out through the seam, as a number; a strip and a four-digit year in the library's words; left out, blank and empty text in the seam's | example, through the seam |
| ten calls across ten functions, the way out for a date among them, which puts the day in a one-day array and checks it as it checks a column; a peak within twice the slack, measured 1,217 bytes, none of it the library's, and nothing published | budget |
| `46023` for `F26` and `46204` for the schedule's `n26` in a real workbook, and a strip refused | Excel smoke |

## Not here

The contract's expiry, its first trading day or its delivery period: the schedule's, read through [util_ReadHandle](read-handle.md). The last day of the month, or any day but the first. A strip's months. Formatting the cell as a date: the sheet's, as for every date the seam sends.
