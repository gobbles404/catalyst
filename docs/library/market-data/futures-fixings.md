# _CreateFuturesFixings

Built in #75; checked against the market's holiday calendar since #79; the futures' name and two columns since #101.

The futures fixings of one index: the settlement price on each day it fixed, date beside settle, as the desk keeps them, one for every business day of its market from the first date to the last, kept as given and reached by handle. It is the futures market's own fixings, as the [IFERC fixings](iferc-fixings.md) are the IFERC market's and the [Gas Daily fixings](gas-daily-fixings.md) the Gas Daily market's, and a history that instruments will settle against, as opposed to the prices that will price them. Since #79 the creator takes the market's holiday calendar, the first creator to take a handle in, `util_ReadHandle` having taken any handle since #66, and refuses a fixing on a weekend day or a holiday and a business day without one, so a series pasted short, or with a closed day in it, fails at its creator rather than at the swap that settles on it. Since #84 [_CreateMarketHistory](../market/market-history.md) reads them, binding the settle on each past business day of the index's calendar to it, and takes them as `futures_fixings` from #101 and as `fixings` from #NN, one argument for the fixings of any market; nothing binds them to an index definition yet. Built in #75 as `_CreateDailyFixings` from a header row and a table, the creator is `_CreateFuturesFixings` from #101 and takes two columns, the date and the settle, selected without the header row, as its siblings do: the desk found the header row and the body clunky in use, one form and one naming across the fixings family, the market's name then `Fixings`, is worth more than the table's guard against a misaligned selection, and a column of numbers costs the seam no look and no temporary per cell. The record, `FuturesFixings`, keeps its two arrays, and its readers and its spill change in nothing but the name; the words `daily fixings` go, since every fixings series is daily or monthly by its market, and the market's name says which. The code is `src/goosedove/market_data/futures_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateFuturesFixings(
    date: DateColumn,
    settle: NumberColumn,
    holiday_calendar: Handle[HolidayCalendar],
) -> Handle[FuturesFixings]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | date | settle | holiday | |
| 2 | 1-May-2026 | 101.94 | 25-May-2026 | `=_CreateHolidayCalendar(C2)` shows `holiday_calendar:3f9a1c:000009` |
| 3 | 4-May-2026 | 106.42 | | |
| 4 | 5-May-2026 | 102.27 | | |
| 5 | 6-May-2026 | 95.08 | | |
| 6 | `=_CreateFuturesFixings(A2:A5, B2:B5, D2)` | shows `futures_fixings:3f9a1c:000010` | | |
| 7 | `=_CreateFuturesFixings(A2, B2, D2)` | shows `futures_fixings:3f9a1c:000011`, the fixings of one day | | |

Two columns of one kind each and a handle, all three required, none with a default, the columns selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the IFERC and Gas Daily fixings', columns paired by position, at the cost [inputs.md](../../seam/inputs.md) decision 38 states: two columns can be selected one row out of step, and equal lengths cannot catch it. The table of #75 was chosen to close that door, a body selected as one range being unable to put a date beside the wrong settle; the desk has since found the header row and the body clunky, and the door opens here as it is open for the rest of the family. The calendar comes by handle because it is an object the sheet already holds, made once by [_CreateHolidayCalendar](../index-definitions/holiday-calendar.md) and named by its cell, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say: the function receives the calendar the seam keeps, never the text, and a cell that is not a calendar's handle fails in the seam's words, `holiday_calendar is number 101.94, expected holiday calendar handle`, before the function runs. The seam checks each column alone, dates one column wide, numbers one column wide, no blank cells, converts the dates to days and resolves the handle, at the cost its ledgers state, one look for the column of dates and none for the settles; nothing here restates that. A single cell is a column of one, so the fixings of one day need no range. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[FuturesFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings. `=util_ReadHandle(A6)` shows the two columns as they went in under the two heading rows, `date` and `settle`, as it did before: the spill does not change.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the futures fixings of one index from the days it fixed and their settles, checked against its market's holiday calendar, and shows its handle, the text other formulas take as the fixings. |
| `date` | The column of days the index fixed, such as A2:A5 holding 1-May-2026 to 6-May-2026, one for every business day from the first to the last. |
| `settle` | The column of settles beside the days, such as B2:B5, one per day. |
| `holiday_calendar` | The market's holiday-calendar handle: the cell showing _CreateHolidayCalendar's result, such as D2, or a name for it. |

## The library checks

Four rules, in this order, the first failure being the message. The first comes with the columns: the settle column has one row per date, since the seam never compares two columns and a series is rows. The second is the curve's, which the owner stated as no duplicate dates and the dates ascending: each date is after the row above, and that one comparison covers both, keeping one fixing per day in the order a reader finds a day by. The third and fourth are the ticket's of #79, that creation detects a fixing on a day the market was closed and a business day without a fixing: each date is a business day, Monday to Friday and not a holiday, at either end of the series as in the middle; and no business day between the first date and the last is without a fixing. With every date a business day and the dates increasing, the series is whole exactly when each date is the business day after the one above, which is one `np.busday_offset` over the column and one comparison, as [time.md](../time.md) decided business days would be counted: numpy's functions over the calendar's list, a week of Monday to Friday, and no loop. Rows count as the sheet counts them, the first row of the column being row 1, and the message names the column by its argument name.

| Rule | Message |
|---|---|
| the settle column has one row per date | `settle has 3 settles, expected 4, one per date` |
| each date after the row above | `date row 2 is 2026-05-01, expected a date after row 1's 2026-05-04` |
| each date a business day, Monday to Friday and not a holiday | `date row 1 is 2026-05-02, a Saturday, expected a business day`, or `date row 2 is 2026-05-25, a holiday, expected a business day` |
| every business day from the first date to the last has a fixing | `date row 3 is 2026-05-06, expected 2026-05-05, the business day after row 2's 2026-05-04` |

A count of one reads `1 settle`. The first and last dates bound the check: nothing is asked for before the first or after the last, so a series from a Tuesday to the Thursday of the same week is whole, and a holiday outside the period changes nothing, so a calendar of one day in January checks a series in May against Monday to Friday alone. A single business day is a series; a single Saturday or holiday is refused. The calendar is read as numpy reads it, a day listed twice counting once and a day listed on a weekend adding nothing, and a Saturday in the series is a Saturday whether or not the calendar lists it. Nothing is sorted: a series pasted newest first fails at its second row, and the desk sorts it, because nothing in the library sorts anything; nothing is filled in either, since a fixing the desk did not paste is a row to paste, never a price to invent. Nothing else is checked. A settle is any number a cell holds, zero and below included, WTI's May 2020 contract having settled below zero, and a cell holds no NaN or infinity to refuse. What a settle may be for a given index is a reader's rule, written when the reader is. One fixing is a series. The settles are copied and frozen, so the fixings own their data, and the days are copied as days. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_futures_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market history's tests build their fixings through this creator and move with it, and its argument, `daily_fixings` until #101, is `futures_fixings`, its three messages and the seam's handle words with it, and from #NN `fixings`, one argument for the fixings of any market, its messages naming it so; its own cases are unchanged.

| Case | Kind |
|---|---|
| the four-row sample above under the calendar page's ten holidays: every date and settle preserved, aligned | example |
| one fixing accepted as a series | example |
| a Friday and the Tuesday after it, with the Monday a listed holiday: whole, the weekend and the holiday being the days without a fixing | example |
| a Tuesday to a Thursday: whole, nothing asked for before the first date or after the last | example |
| a settle below zero and a zero are kept as given | example |
| a holiday listed twice, and a Saturday and a Sunday listed, change nothing | example |
| a settle column one row short, one row long, one settle for four dates and four settles for one date: rejected, naming the count; the count checked before the order | example |
| two dates swapped, a date twice, and a series newest first: rejected, naming the row | example |
| a Saturday first, a Sunday last, a holiday between and a holiday alone: rejected, naming the row, the day and its reason | example |
| a weekday missing, the Monday after a weekend missing, and the day after a holiday missing: rejected, naming the row after the gap and the business day without a fixing | example |
| a calendar whose one day is elsewhere: a weekday missing and a Saturday are still refused, and the 25th of May is a business day | example |
| a Saturday listed as a holiday is refused as a Saturday; the order is checked before the calendar, and the calendar before the gaps | example |
| for any run of `N` business days under any calendar, and any `N` settles, everything is preserved and aligned | property |
| for any such run with one interior day left out, the row after the gap is refused, naming the day | property |
| an input changed after construction leaves the fixings unchanged, and their arrays refuse writes | example |
| the fixings read back through the handle, and two single cells the fixings of one day; a listed holiday between two fixings is a day without one | example, through the seam |
| a settle column one row short, dates backwards, a Saturday, a listed holiday and a business day without a fixing: the library's words; a blank or a time among the days, text where a day should be, a blank or text among the settles, a row where a column should be, either column left out or blank, and a number, a blank, a missing argument, text naming no live object or a creator's failure where the calendar should be: the seam's, the days named first when both columns are wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short and a Saturday alike | example, with handles |
| a handle of another kind is not futures fixings, and is not a holiday calendar | example, with handles |
| the fixings' spill: two headers, two types, then one row per day, the date as a serial and the settle exactly | example |
| the creator's handle over four days and over two single cells read back, a settle column one row short, the days newest first, a business day without a fixing, a Saturday, a listed holiday, text among the days, and the calendar left out or a number in its place, in a real workbook | Excel smoke |

## Not here

The header row: the function never sees it, so the columns bind by position and not by name, and a header spelled otherwise is not an error. Two columns selected one row out of step: the count sees equal lengths, and nothing here can tell a settle from its neighbour's, decision 38's cost, carried by the desk's selection as it is for the IFERC and Gas Daily fixings. The schedule's name: the futures schedule stays `_CreateFuturesSchedule` until its own pull request, the futures market's schedule beside the IFERC and Gas Daily schedules being that request's to name. Reading a settle by date, the days a period covers and their average, which is how a swap settles: the pricing's job, along the [market history](../market/market-history.md), which since #84 binds the settle on each past business day to the index's calendar and refuses a fixing on a day that calendar closes. Binding the fixings to an index definition, and checking that the calendar is that index's. A market trading on weekends, whose week is not Monday to Friday: its own mask, when one arrives, as [time.md](../time.md) parks it. A series as of a date, revisions to a published settle, bid and ask, volume. Sorting a pasted series, and filling a missing settle. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
