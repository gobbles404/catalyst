# _CreateHolidayCalendar

Built in #67.

The days one market is closed, listed one by one as the desk keeps them, kept as given and reached by handle. It is a static calendar: the list is the calendar, and no day is generated from a rule. Its first reader is [_CreateFuturesFixings](../market-data/futures-fixings.md), since #79: the fixings take the calendar's handle and are refused on a listed day, or without a fixing on a business day, through numpy's business-day functions over this list, as [time.md](../time.md) decided; the [calendar](../calendar/calendar.md) of #82 reads it the same way, flagging whether the market is open on each of its days, and since #108 both read it through the [index](index.md), which holds it beside the schedule; a reader that counts the business days between two dates is not specified. The code is `src/goosedove/index_definitions/holiday_calendar.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateHolidayCalendar(holiday: DateColumn) -> Handle[HolidayCalendar]: ...
```

| | A | B |
|---|---|---|
| 1 | holiday | |
| 2 | 1-Jan-2026 | |
| 3 | 19-Jan-2026 | |
| 4 | 16-Feb-2026 | |
| 5 | 3-Apr-2026 | |
| 6 | 25-May-2026 | |
| 7 | 19-Jun-2026 | |
| 8 | 3-Jul-2026 | |
| 9 | 7-Sep-2026 | |
| 10 | 26-Nov-2026 | |
| 11 | 25-Dec-2026 | |
| 12 | `=_CreateHolidayCalendar(A2:A11)` | shows `30512:holiday_calendar:6` |
| 13 | `=_CreateHolidayCalendar(A2)` | shows `30512:holiday_calendar:7`, a market closed on one day |

One column of dates, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. It is the second function to take a column of one kind without headers, after `_CreateFuturesSchedule` ([inputs.md](../../seam/inputs.md) decision 38), and the cost that page states, two columns selected one row out of step, does not arise with one. A single cell is a column of one, so a market closed on one day needs no range. The seam checks the column alone, dates one column wide, no blank cells, and hands over an array of days; nothing here restates that. The result is a handle: text in the cell that stands for the calendar the seam keeps, declared `Handle[HolidayCalendar]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the calendar.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a holiday calendar from the days one market is closed and shows its handle, the text other formulas take as the calendar. |
| `holiday` | The column of dates the market is closed, such as A2:A11, one holiday per row. |

## The library checks

None. The seam never compares two arguments and the calendar has one, so there is no rule of alignment as the schedule has, and a calendar is the days the desk listed. The dates are kept as given, in the order given: a day listed twice is listed twice, a day out of order stays where it was, and a Saturday listed is kept. What a calendar must look like for a reader to use it, whether days repeat, whether they increase, whether a weekend day belongs, is that reader's rule, written when the reader is; the futures fixings, the first, read the list as numpy does, a day listed twice counting once and a weekend day listed adding nothing. A one-row calendar is a calendar. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_holiday_calendar.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the calendar; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the ten-row sample above: every day preserved, as given, in order | example |
| a one-row calendar accepted | example |
| a day listed twice, days out of order and a Saturday are kept as given: nothing else is checked | example |
| for any column of `N` dates, every day is preserved in order | property |
| an input changed after construction leaves the calendar unchanged, and its array refuses writes | example |
| a column read back through its handle holds the days that went in, and a single cell is a calendar of one day | example, through the seam |
| a blank, text or a time in the column, a row of dates, a blank cell or the column left out: the seam's words | example, through the seam |
| a rejected column publishes no object and no handle | example, with handles |
| a handle of another kind is not a calendar | example, with handles |
| the creator's handle over three days and over one cell, read back through `util_ReadHandle`, a blank in the column and a row where a column is expected, in a real workbook | Excel smoke |

## Not here

Whether a day is a business day: the futures fixings' rule since #79, numpy's business-day functions over this list as [time.md](../time.md) decided. The business days between two dates, and where a date that falls on a holiday rolls to: a later consumer's job, with whatever it needs a calendar to hold true. Weekends: the calendar holds the days the desk listed and knows nothing of Saturdays and Sundays; the futures fixings treat them as closed, Monday to Friday being the week, and another reader may rule otherwise. Holidays from a rule, the third Monday of January say: the list is the calendar. Which market the calendar belongs to, its name, its exchange, its time zone. A market with no holidays: a range has at least one cell and a blank fails, so the smallest calendar holds one day, and an empty calendar waits for a need. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any calendar. Market data, pricing.
