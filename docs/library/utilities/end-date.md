# util_EndDate

Built in #129; the balance of a period, a `BAL` label, in #160, from a reference date, and since #173 from a valuation-date handle, the period held to end on or after its day; the ticket is [date-helper-inputs.md](../../engineering-tickets/trade-valuation-pipeline/date-helper-inputs.md).

Gives the last calendar day of a contract or strip from its label, inclusive: 31 January 2026 for `F26`, 31 March 2027 for `1Q27`, 31 March 2030 for `W29`, and the last day of the right label of `F26-Z28`; since #160, the last day of the balance of any of these too, `BALZ26` with its valuation-date handle since #173, the same last day, the period checked here as well to end on or after the valuation day, though the end it would give is the label's own. Text and a handle in and one date out, no object made, a derivation and no `util_Read*` function, as [conventions.md](../conventions.md) divides them. It is the twin of [util_StartDate](start-date.md), through the same reading of the same grammar, which that page holds in full: the forms, the case rule, the two-digit year, what a range covers and the order its ends must keep, and the valuation-day rule of a balance. The code is `src/goosedove/index_definitions/periods.py`, `end_date`, and `src/goosedove/excel/utilities.py`, the worksheet function.

## Worksheet contract

```python
def util_EndDate(period: str, valuation_date: Handle[ValuationDate] | None = None) -> Date: ...
```

| | A | B |
|---|---|---|
| 1 | | `=_CreateValuationDate(DATE(2026,10,12),0)` shows `30512:valuation_date:3`, 12 October 2026 |
| 2 | f26 | `=util_EndDate(A2)` shows `46053`, 31-Jan-2026 once formatted |
| 3 | G28 | `46812`, 29-Feb-2028, a leap year |
| 4 | W99 | `73140`, 31-Mar-2100, the next century and no wrap |
| 5 | 1Q27-CAL27 | `46752`, 31-Dec-2027 |
| 6 | CAL28-F28 | `#ERROR util_EndDate: ValueError: period is 'CAL28-F28', expected range endpoints in chronological order` |
| 7 | balv26 | `=util_EndDate(A7,$B$1)` shows `46326`, 31-Oct-2026, the label's last day from the 12th on |
| 8 | BALX26 | `=util_EndDate(A8,$B$1)` shows `46356`, 30-Nov-2026, a month still to come |
| 9 | balf26 | `=util_EndDate(A9,$B$1)` shows `#ERROR util_EndDate: ValueError: valuation_date is 2026-10-12, after 'balf26' ended on 2026-01-31, expected a valuation day on or before the period's last day` |

Two arguments, the label required and, since #160, the second, which may be left out with nothing in its place and is required by the library for a `BAL` label, since #173 the valuation-date handle, a raw date refused by the seam, both as [util_StartDate](start-date.md) says and the seam checks, as [inputs.md](../../seam/inputs.md) says; the result is a date, out as its serial, as [outputs.md](../../seam/outputs.md) says, which the cell formats. Nothing is published and no object is made.

## Excel help

Quoted from the declaration in `src/goosedove/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Gives the last calendar day of a contract or strip, 31-Jan-2026 for F26, 31-Mar-2030 for W29 and the last day of the right label of F26-Z28; of its balance, the same last day, a period ended before the valuation day refused. |
| `period` | One contract or strip label, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28, or its balance, BALZ26, typed or in a cell such as A2. |
| `[valuation_date]` | For a BAL label, the valuation-date handle whose day the balance starts on, such as B1 showing _CreateValuationDate's result; left out for any other label. |

## The library checks

The four rules of [util_StartDate](start-date.md), run over the whole expression here too, so asking for an end cannot hide a start that is no label, a reversed range is refused whichever end is asked for, and a balance whose handle is left out or whose period ended before the valuation day is refused here as well, though the end it would give is the label's own: a period that has gone must not read as a one-day deal at its end from either function.

| Rule | Message |
|---|---|
| each label is one of the forms, with a two-digit year, under a `BAL` prefix or not | `period is 'W8-W9', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28` |
| a range's right end starts and ends no earlier than its left | `period is 'CAL28-F28', expected range endpoints in chronological order` |
| a `BAL` label has its valuation-date handle | `valuation_date is missing, expected a valuation-date handle with 'BALZ26', whose day starts the balance of a period` |
| the label's period ends on or after the valuation day, since #173 | `valuation_date is 2026-11-01, after 'balv26' ended on 2026-10-31, expected a valuation day on or before the period's last day` |

The last day is the day before the month after the period begins, one conversion of a month to a day and one day subtracted, so a February's own length, a winter's March in the year after and `W99`'s in the next century come from numpy's month unit with nothing counted by hand.

## Tests

The tests are the start function's, each case asking for both days: `tests/unit/test_periods.py` for the library, `tests/unit/test_utilities.py` for the seam, `tests/unit/test_help.py` for the help, `tools/excel_smoke.ps1` and `host/Goosedove.Host.Tests/CallTests.cs` for a real workbook and its replay, `workbooks/handles.xlsx` for the kept examples, and the two performance files for the ledger, fourteen calls across thirteen functions for one label and fifteen for a range, the balance of a month sixteen across fourteen and of a strip seventeen, and the peak, 1,264 bytes for a month and for the whole century alike and the balance within the same bound.

| Case | Kind |
|---|---|
| the last day of every form in the grammar's table, in either case; February in leap years and not; `W99` in the next century | example |
| every malformed label and every reversed range the start function refuses, refused here with the same words | example |
| for any month, the last day is the day before the next month's first; for any range, the right label's last day | property |
| the last days through the seam as serials, and both refusals in the library's words; the seam's own for a number, a blank and empty text | example, through the seam |
| since #173 the balance of a period ending on the label's last day from any valuation day on or before it, the ticket's table, slice B's labels, the leap day, a Saturday and a year-end range among them, a future period's end the label's own; the handle left out or the period ended refused naming the label, the day and the end, the prefix twice or over a malformed or reversed label refused naming the whole expression; the same through the seam, with a blank, a raw date, a text, a fraction of a day and a handle of another kind in the seam's words | example |
| the last day of the schedule's own `m26`, of a quarter, a year, a winter and two ranges in a real workbook, a reversed range refused; the balances over valuation-date handles, a period that has ended refused | Excel smoke |
| since #NN the last day of a half-year, 30-Jun-2027 for `1H27` and `1h27`, 31-Dec-2027 for `2H27`, the leap `1H28`, the ranges `1H27-2H27` and `2h27-1h28`, `H27` still March; `0H27`, `3H27`, `1H7` and `1H2027` refused naming the forms, `2H27-1H27` by its order; the balance of a half from a day inside it, [half-year-strips.md](../../engineering-tickets/trade-valuation-pipeline/half-year-strips.md); the same on the host, the smoke sheet and the kept workbook from row 2612 | example |

## Not here

As [util_StartDate](start-date.md) says: expiries, publication and payment days are the schedules'; strips are not built, priced or weighted here; aliases and spaces are refused; the ends of a range are never sorted; a period that has ended is never read as a one-day deal and the valuation day is never a business day by rule; no implicit valuation date is consulted. The last business day of a period, and a period's days as a column: the [calendar](../calendar/calendar.md) holds every day of its schedule with whether the market is open, and a strip's days as a column wait for the function that averages over them.
