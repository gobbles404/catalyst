# _CreateDailyFixings

Built in #75; checked against the market's holiday calendar since #79.

The daily fixings of one index: the settlement price on each day it fixed, date beside settle, as the desk keeps them, one for every business day of its market from the first date to the last, kept as given and reached by handle. It is the second market data, beside the futures curve: a history that instruments will settle against, as opposed to the curve that prices them. Since #79 the creator takes the market's holiday calendar, the first function the library lists to take a handle in, and refuses a fixing on a weekend day or a holiday and a business day without one, so a series pasted short, or with a closed day in it, fails at its creator rather than at the swap that settles on it. Nothing reads the fixings yet, and nothing binds them to an index yet. The code is `src/goosedove/market_data/daily_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
class DailyFixingsTable(Table):
    date: DateColumn
    settle: NumberColumn


def _CreateDailyFixings(
    header_row: TextRow, table: DailyFixingsTable, holiday_calendar: Handle[HolidayCalendar]
) -> Handle[DailyFixings]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | date | settle | holiday | |
| 2 | 1-May-2026 | 101.94 | 25-May-2026 | `=_CreateHolidayCalendar(C2)` shows `holiday_calendar:3f9a1c:000009` |
| 3 | 4-May-2026 | 106.42 | | |
| 4 | 5-May-2026 | 102.27 | | |
| 5 | 6-May-2026 | 95.08 | | |
| 6 | `=_CreateDailyFixings(A1:B1, A2:B5, D2)` | shows `daily_fixings:3f9a1c:000010` | | |

The input is a table and a handle: a header row, then a body with one row per fixing, the date and its settle, one row for every business day from the first date to the last, and the cell showing the market's holiday calendar, whose days and the weekends are the days without a fixing. The owner chose a table over columns, the shape the futures curve takes, for two reasons its page states the other side of: a fixings series is closer to static data than to a ticking curve, so the table path's cost is paid rarely, and a body selected as one range cannot put a date beside the wrong settle, where two columns selected one row out of step could. The calendar comes by handle because it is an object the sheet already holds, made once by [_CreateHolidayCalendar](../index-definitions/holiday-calendar.md) and named by its cell, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say: the function receives the calendar the seam keeps, never the text, and a cell that is not a calendar's handle fails in the seam's words, `holiday_calendar is number 101.94, expected holiday calendar handle`, before the function runs. The headers bind in either order and capital letters do not matter; the spelling must match, and `price` is not a header. All three arguments required, no defaults. The seam binds the headers, checks the columns, converts the dates and resolves the handle, at the cost its ledgers state, one look per column, the gathers that pull each column out of the body, and one lookup for the handle; nothing here restates that. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[DailyFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the daily fixings of one index from the days it fixed and their settles, checked against its market's holiday calendar, and shows its handle, the text other formulas take as the fixings. |
| `header_row` | The header cells of your fixings table, such as A1:B1, reading date and settle in either order. |
| `table` | The rows under the headers, such as A2:B5: one fixing per row, its date and settle, one for every business day from the first to the last. |
| `holiday_calendar` | The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's result, such as D2, or a name for it. |

## The library checks

Three rules, in this order, the first failure being the message. The first is the curve's, which the owner stated as no duplicate dates and the dates ascending: each date is after the row above, and that one comparison covers both, keeping one fixing per day in the order a reader finds a day by. The second and third are the ticket's of #79, that creation detects a fixing on a day the market was closed and a business day without a fixing: each date is a business day, Monday to Friday and not a holiday, at either end of the series as in the middle; and no business day between the first date and the last is without a fixing. With every date a business day and the dates increasing, the series is whole exactly when each date is the business day after the one above, which is one `np.busday_offset` over the column and one comparison, as [time.md](../time.md) decided business days would be counted: numpy's functions over the calendar's list, a week of Monday to Friday, and no loop. Rows count as the sheet counts them, the first row of the body being row 1, and the message names the column by its header, because the headers bind in either order.

| Rule | Message |
|---|---|
| each date after the row above | `date row 2 is 2026-05-01, expected a date after row 1's 2026-05-04` |
| each date a business day, Monday to Friday and not a holiday | `date row 1 is 2026-05-02, a Saturday, expected a business day`, or `date row 2 is 2026-05-25, a holiday, expected a business day` |
| every business day from the first date to the last has a fixing | `date row 3 is 2026-05-06, expected 2026-05-05, the business day after row 2's 2026-05-04` |

The first and last dates bound the check: nothing is asked for before the first or after the last, so a series from a Tuesday to the Thursday of the same week is whole, and a holiday outside the period changes nothing, so a calendar of one day in January checks a series in May against Monday to Friday alone. A single business day is a series; a single Saturday or holiday is refused. The calendar is read as numpy reads it, a day listed twice counting once and a day listed on a weekend adding nothing, and a Saturday in the series is a Saturday whether or not the calendar lists it. Nothing is sorted: a series pasted newest first fails at its second row, and the desk sorts it, because nothing in the library sorts anything; nothing is filled in either, since a fixing the desk did not paste is a row to paste, never a price to invent. Nothing else is checked. A settle is any number a cell holds, zero and below included, as the futures curve's page says, and a cell holds no NaN or infinity to refuse. What a settle may be for a given index is a reader's rule, written when the reader is. One fixing is a series. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_daily_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the four-row sample above under the calendar page's ten holidays: every date and settle preserved, aligned | example |
| one fixing accepted as a series | example |
| a Friday and the Tuesday after it, with the Monday a listed holiday: whole, the weekend and the holiday being the days without a fixing | example |
| a Tuesday to a Thursday: whole, nothing asked for before the first date or after the last | example |
| a settle below zero and a zero are kept as given | example |
| a holiday listed twice, and a Saturday and a Sunday listed, change nothing | example |
| two dates swapped, a date twice, and a series newest first: rejected, naming the row | example |
| a Saturday first, a Sunday last, a holiday between and a holiday alone: rejected, naming the row, the day and its reason | example |
| a weekday missing, the Monday after a weekend missing, and the day after a holiday missing: rejected, naming the row after the gap and the business day without a fixing | example |
| a calendar whose one day is elsewhere: a weekday missing and a Saturday are still refused, and the 25th of May is a business day | example |
| a Saturday listed as a holiday is refused as a Saturday; the order is checked before the calendar, and the calendar before the gaps | example |
| for any run of `N` business days under any calendar, and any `N` settles, everything is preserved and aligned | property |
| for any such run with one interior day left out, the row after the gap is refused, naming the day | property |
| an input changed after construction leaves the fixings unchanged, and their arrays refuse writes | example |
| the fixings read back through the handle; the headers bind in either order and any case; a listed holiday between two fixings is a day without one | example, through the seam |
| an unknown header, text in the settle column, a body wider than its headers, a blank or a missing body, headers down a column, and a number, a blank, a missing argument, text naming no live object or a creator's failure where the calendar should be: the seam's words; dates backwards, a Saturday, a listed holiday and a business day without a fixing: the library's | example, through the seam |
| a failed construction publishes no object and no handle | example, with handles |
| a handle of another kind is not daily fixings, and is not a holiday calendar | example, with handles |
| the fixings' spill: two headers, two types, then one row per day, the date as a serial and the settle exactly | example |
| the creator's handle read back, the days newest first, a business day without a fixing, a Saturday, a listed holiday, the headers where the body should be, a header the table does not have, and the calendar left out or a number in its place, in a real workbook | Excel smoke |

## Not here

Reading a settle by date, the days a period covers and their average, which is how a swap settles: the first consumer's job, with the holiday calendar beside it. Binding the fixings to an index, and checking that the calendar is that index's. A market trading on weekends, whose week is not Monday to Friday: its own mask, when one arrives, as [time.md](../time.md) parks it. A series as of a date, revisions to a published settle, bid and ask, volume. Sorting a pasted series, and filling a missing settle. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
