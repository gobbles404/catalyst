# _CreateGasDailyFixings

Built in #100.

The Gas Daily fixings of one index: the midpoint Platts printed for each day gas flowed, price beside flow day, one row for every calendar day from the first to the last, kept as given and reached by handle. Gas Daily prints its daily price survey on the business day before the gas flows, one midpoint per flow day, and its flow-date symbols date each value by the day the gas flows rather than the day the deal was done, so a Friday's print arrives as three rows, Saturday, Sunday and Monday, and the Friday before Labor Day 2026 as four, each carrying the same number. The desk pastes those rows as Platts dates them, weekends and holidays included, and the library moves no date and carries nothing forward: a Saturday's price is the number Platts dated Saturday, not something reached back for from Friday. It is the [daily fixings](daily-fixings.md)' sibling for an index that prices every calendar day, and it takes no holiday calendar, since no day is closed, and no schedule, since a flow day's month is the month it flows in and needs no lookup. Nothing reads it yet but [util_ReadHandle](../utilities/read-handle.md); the history of the Gas Daily market is the first reader, when it is written, binding each day's price to the days of the Gas Daily calendar built from the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md). The code is `src/goosedove/market_data/gas_daily_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateGasDailyFixings(
    flow_date: DateColumn,
    price: NumberColumn,
) -> Handle[GasDailyFixings]: ...
```

Henry Hub Gas Daily over Labor Day week 2026, with the prices illustrative and not published values; Friday 4 September's print covers Saturday 5 to Tuesday 8, Monday 7 being the holiday:

| | A | B |
|---|---|---|
| 1 | flow_date | price |
| 2 | 4-Sep-2026 | 2.930 |
| 3 | 5-Sep-2026 | 2.875 |
| 4 | 6-Sep-2026 | 2.875 |
| 5 | 7-Sep-2026 | 2.875 |
| 6 | 8-Sep-2026 | 2.875 |
| 7 | 9-Sep-2026 | 2.900 |
| 8 | `=_CreateGasDailyFixings(A2:A7, B2:B7)` | shows `gas_daily_fixings:3f9a1c:000055` |
| 9 | `=_CreateGasDailyFixings(A2, B2)` | shows `gas_daily_fixings:3f9a1c:000056`, the fixings of one day |

Two columns of one kind each, both required, neither with a default, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the IFERC fixings', columns paired by position, so that the fixings of a family are typed the same way, at the cost [inputs.md](../../seam/inputs.md) decision 38 states: two columns can be selected one row out of step, and equal lengths cannot catch it. A price is any number a cell holds, zero and below included, and Waha has printed below zero. The seam checks each column alone, dates one column wide, numbers one column wide, no blank cells, and hands over an array of days and an array of numbers; nothing here restates that. A single cell is a column of one, so the fixings of one day need no range. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[GasDailyFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings.

`=util_ReadHandle(A8)` on the fixings above shows the two columns as they went in, the flow days as serials and the prices as numbers, under the two heading rows:

| flow_date | price |
|---|---|
| datetime64[D] | float64 |
| 4-Sep-2026 | 2.93 |
| 5-Sep-2026 | 2.875 |
| 6-Sep-2026 | 2.875 |
| 7-Sep-2026 | 2.875 |
| 8-Sep-2026 | 2.875 |
| 9-Sep-2026 | 2.9 |

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_data.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the Gas Daily fixings of one index from the days gas flowed and the midpoint printed for each, one for every calendar day from the first to the last, and shows its handle, the text other formulas take as the fixings. |
| `flow_date` | The column of flow days, such as A2:A7 holding 4-Sep-2026 to 9-Sep-2026, one for every calendar day from the first to the last. |
| `price` | The column of midpoints beside the flow days, such as B2:B7, one per day. |

## The library checks

Two rules, in this order, the first failure being the message. Rows count as the sheet counts them, the first row of the column being row 1.

| Rule | Message |
|---|---|
| the price column has one row per flow day, since the seam never compares two columns and a series is rows | `price has 5 prices, expected 6, one per flow_date` |
| each flow day is the day after the row above, since a series that prices every calendar day has no other shape: the days increase, no day is given twice, and no day between the first and the last is missing | `flow_date row 4 is 2026-09-07, expected 2026-09-06, the day after row 3's 2026-09-05` |

A count of one reads `1 price`. The second rule is one comparison over the column, and the first row that breaks it is the one named: a day given twice, a day skipped and a series pasted newest first all fail at that row, with the day that was expected. Nothing is sorted, filled or extended: a series pasted newest first fails at its second row, and the desk sorts it; a day without a row is a row the desk did not paste, never a price to carry forward, and a day Platts printed no midpoint for is a gap the desk cannot fill, so the series is refused at it and what such a day means to an average is a rule for the instrument that averages, not for the fixings. Nothing else is checked: no weekday is looked at, no holiday list is taken, and no month is read off a day. The prices are copied and frozen, so the fixings own their data, and the days are copied as days. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_gas_daily_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the six-day sample above: every flow day and every price preserved, aligned, the weekend and the holiday rows among them | example |
| the fixings of one day accepted, from a one-row range and from two single cells; a whole month, thirty rows, kept in its order | example |
| a price below zero and a zero kept as given; the same price on four consecutive days kept as four rows | example |
| a run across a month end, 30 September to 2 October, and across a year end, kept as given: no month or year is looked at | example |
| a price column one row short, one row long, one price for six days and six prices for one day: rejected, naming the count | example |
| a day given twice, a day skipped, two days skipped, a series pasted newest first and two days swapped in the middle: rejected, naming the row and the day expected; the count checked before the days | example |
| for any first day and any `N` consecutive days with `N` prices, everything is preserved and aligned; with one day left out, the row after the gap is refused, naming the day | property |
| an input changed after construction leaves the fixings unchanged, and both arrays refuse writes | example |
| two columns read back through their handle, and two single cells the fixings of one day | example, through the seam |
| a price column one row short and a day skipped, the library's words; a blank or a time among the days, text where a day should be, a blank or text among the prices, a row where a column should be, either column left out or blank, the seam's words, the days named first when both columns are wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short, a day skipped and a blank among the prices alike | example, with handles |
| a handle of another kind is not Gas Daily fixings, the daily fixings' and the Gas Daily schedule's included | example, with handles |
| the spill: two headers, two types, then a row per day, the day as a serial and the price as a number, a weekend row among them | example |
| the creator's handle over six days and over two single cells, read back through `util_ReadHandle`, a column one row short, a day skipped, a series newest first, a blank among the prices, text among the days and the prices left out, in a real workbook | Excel smoke |

## Not here

Reading the fixings for anything: the history of the Gas Daily market, when it is written, which will take the Gas Daily calendar and these fixings and decide that every day of the calendar through the valuation day has a price, since a flow day is printed before it begins, and which days after it the paste has priced. Which month a flow day belongs to: the calendar's, from the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md). The day an assessment was made, the days one print covers and Platts' holidays: Platts' own, already applied when it dated the values by flow day, and the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md) page says why none of them is held. A day Platts printed no midpoint for: refused here as a gap; dropped from the average under the ICE contracts and bridged under the ISDA gas annex, which the instrument's page decides. The month's average, plain Gas Daily: an instrument's arithmetic over a month's rows, and Platts publishes its own, a number a later reader may take as a month's settlement. A revised midpoint: a new fixings object, never an edit. The daily fixings, which keep their holiday calendar and their table until their own refactor. Sorting a series, filling a missing day. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
