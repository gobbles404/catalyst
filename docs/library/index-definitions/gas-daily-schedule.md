# _CreateGasDailySchedule

Built in #98.

The Gas Daily schedule of one index: each contract month's code and the first and last day of gas the month's price covers, kept as given and reached by handle. Gas Daily is the S&P Global Platts publication whose daily price survey prints a midpoint for each day gas flows at a location, Waha and Henry Hub among them; ICE's swing futures settle to that midpoint one flow day at a time, and its index futures to the average of it over each calendar day of the month. A flow day's month is the month it flows in, so a contract month's two dates are its first and last calendar days, typed rather than read from the code, which [time.md](../time.md) parks, and the days between are every calendar day, weekends and holidays included, each with a price of its own. No last trading day is held: the swing future stops trading the business day before its one day and the index future the last business day before its month, and neither decides which month a day belongs to. It is the Gas Daily market's own object, next to the [expiry schedule](expiry-schedule.md), the exchange's, and the [IFERC schedule](iferc-schedule.md), the monthly index's, so that every market's calendar takes its months and their bounds from a schedule of its own. Nothing reads it yet but [util_ReadHandle](../utilities/read-handle.md); the calendar of the Gas Daily market is the first reader, when it is written. The code is `src/goosedove/index_definitions/gas_daily_schedule.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateGasDailySchedule(
    contract_code: TextColumn,
    first_date: DateColumn,
    last_date: DateColumn,
) -> Handle[GasDailySchedule]: ...
```

Henry Hub Gas Daily, three contract months of 2026:

| | A | B | C |
|---|---|---|---|
| 1 | contract_code | first_date | last_date |
| 2 | U26 | 1-Sep-2026 | 30-Sep-2026 |
| 3 | V26 | 1-Oct-2026 | 31-Oct-2026 |
| 4 | X26 | 1-Nov-2026 | 30-Nov-2026 |
| 5 | `=_CreateGasDailySchedule(A2:A4, B2:B4, C2:C4)` | shows `gas_daily_schedule:3f9a1c:000051` | |
| 6 | `=_CreateGasDailySchedule(A2, B2, C2)` | shows `gas_daily_schedule:3f9a1c:000052`, a schedule of one contract month | |

Three columns of one kind each, all required, none with a default, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the IFERC schedule's, columns paired by position rather than a table, and its cost stands as [inputs.md](../../seam/inputs.md) decision 38 states it: two columns can be selected one row out of step, and equal lengths cannot catch it. The code column is `contract_code`, as the IFERC schedule's is, because the code labels the month the gas flows in. The two dates are that month's first and last days, 1-Sep-2026 and 30-Sep-2026 for U26; the desk types them though the code implies them, so that this creator takes what the other schedules take and no code is read for its month before [time.md](../time.md) says how. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and two arrays of days; nothing here restates that. A single cell is a column of one, so a schedule of one contract month needs no range. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[GasDailySchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule.

`=util_ReadHandle(A5)` on the schedule above shows the three columns as they went in, the code as text and the dates as serials, under the two heading rows:

| contract_code | first_date | last_date |
|---|---|---|
| str | datetime64[D] | datetime64[D] |
| U26 | 1-Sep-2026 | 30-Sep-2026 |
| V26 | 1-Oct-2026 | 31-Oct-2026 |
| X26 | 1-Nov-2026 | 30-Nov-2026 |

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a Gas Daily schedule from the contract months of one index and the first and last day of gas each month's price covers, and shows its handle, the text other formulas take as the schedule. |
| `contract_code` | The column of contract codes, such as A2:A4 holding U26 to X26, one per contract month. |
| `first_date` | The column of each month's first day of gas, beside the codes, such as B2:B4, one per code. |
| `last_date` | The column of each month's last day of gas, beside the codes, such as C2:C4, one per code. |

## The library checks

One rule: each date column has one row per code, because the seam never compares two arguments and a schedule is rows.

| Rule | Message |
|---|---|
| each date column has one row per code | `first_date has 2 dates, expected 3, one per contract_code`, or `last_date has 2 dates, expected 3, one per contract_code` |

A count of one reads `1 date`. The first dates are checked before the last dates, so when both columns are wrong the earlier is named. Nothing else is checked. The codes are kept as typed, `U26` and `u26` alike, the seam's tuple as it arrived, and the dates as given, in the order given, each column copied and frozen so that a later change to the input cells changes no schedule. What a schedule must look like for a reader to use it, whether codes repeat, whether a month's last day is on or after its first, whether the two are a calendar month's, whether the months follow one another with no day missed and none shared, and what a code means, is that reader's rule, written when the reader is; nothing is parsed, sorted or adjusted here. A one-row schedule is a schedule. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_gas_daily_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the three-row sample above: every code and both dates preserved, aligned, as typed | example |
| a one-row schedule accepted; twelve months kept in their order | example |
| codes in either case, a code twice, a last day before its first, dates that are not a month's bounds, two months sharing a day and months out of order kept as given: nothing else is checked | example |
| a first-date column one row short or long, a last-date column one row short or long, and one date for three codes: rejected, naming the count; both columns wrong names the first dates | example |
| for any `N` codes and any two columns of `N` dates, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, both arrays refuse writes, and the codes are the tuple that arrived | example |
| three columns read back through their handle, and three single cells a schedule of one contract month | example, through the seam |
| a date column one row long or short, the library's words; a blank or a time among the dates, text where a date should be, a number or empty text among the codes, a row where a column should be, any column left out or blank, the seam's words, the codes named first when more than one column is wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short and a blank among the dates alike | example, with handles |
| a handle of another kind is not a Gas Daily schedule, the IFERC schedule's included | example, with handles |
| the spill: three headers, three types, then a row per contract month, the code as text and both dates as serials | example |
| the creator's handle over three rows and over three single cells, read back through `util_ReadHandle`, a column one row long and one row short, a blank among the last dates, a number among the codes, the last dates left out and a row where a column is expected, in a real workbook | Excel smoke |

## Not here

Reading the schedule for anything: the calendar of the Gas Daily market, when it is written, which will decide what a code means, whether codes and months must be unique and in order, whether each month is whole and the months touch, and which month each calendar day belongs to; and after it the flow-date fixings, one price per calendar day as Platts dates them, and the history that binds them. The expiry schedule and the IFERC schedule: unchanged, and not this schedule's concern. A last trading date, a trade date, the days one assessment prices, and a holiday calendar: none, since Platts' flow-date values already carry every weekend and holiday, and an instrument that needs the day it stopped trading brings that with it. What a code means: `U26` is text, never read as a month and a year; what it will mean, and whether a month's bounds could come from it, is decided in [time.md](../time.md). Whether the two dates are the days Platts prices: the schedule's author's. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule. Pricing and risk.
