# _CreateGasDailyFixings

Built in #100; the index since #109.

The Gas Daily fixings of one index: the midpoint Platts printed for each day gas flowed, price beside flow day, one row for every calendar day from the first to the last, kept as given and reached by handle. Gas Daily prints its daily price survey on the business day before the gas flows, one midpoint per flow day, and its flow-date symbols date each value by the day the gas flows rather than the day the deal was done, so a Friday's print arrives as three rows, Saturday, Sunday and Monday, and the Friday before Labor Day 2026 as four, each carrying the same number. The desk pastes those rows as Platts dates them, weekends and holidays included, and the library moves no date and carries nothing forward: a Saturday's price is the number Platts dated Saturday, not something reached back for from Friday. It is the [futures fixings](futures-fixings.md)' sibling for an index that prices every calendar day: it reads no holiday calendar, since no day is closed, and nothing of the schedule, since a flow day's month is the month it flows in and needs no lookup. Since #105 the [market history](../market/market-history.md) reads it, binding each day's price to the days of the Gas Daily calendar built from the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md); before that only [util_ReadHandle](../utilities/read-handle.md) did. From #109 the creator takes the [index](../index-definitions/index.md), as its siblings do: it keeps the index by reference, so that the fixings say whose they are and the history can check that they and its calendar are one index's, and it refuses an index of another kind; it reads nothing else from it. The code is `src/goosedove/market_data/gas_daily_fixings.py`, the record and its builder, and `src/goosedove/excel/market_data.py`, the worksheet function.

## Worksheet contract

```python
def _CreateGasDailyFixings(
    flow_date: DateColumn,
    price: NumberColumn,
    index: Handle[Index],
) -> Handle[GasDailyFixings]: ...
```

Henry Hub Gas Daily over Labor Day week 2026, with the prices illustrative and not published values; Friday 4 September's print covers Saturday 5 to Tuesday 8, Monday 7 being the holiday:

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | flow_date | price | contract_code | first_date | last_date |
| 2 | 4-Sep-2026 | 2.930 | U26 | 1-Sep-2026 | 30-Sep-2026 |
| 3 | 5-Sep-2026 | 2.875 | `=_CreateGasDailySchedule(C2, D2, E2)` shows `30512:gas_daily_schedule:44` | | |
| 4 | 6-Sep-2026 | 2.875 | `=_CreateIndex("Henry Hub Gas Daily", C3, B12, B13)` shows `30512:index:Henry Hub Gas Daily:45`, B12 and B13 holding the conventions and the specifications | | |
| 5 | 7-Sep-2026 | 2.875 | | | |
| 6 | 8-Sep-2026 | 2.875 | | | |
| 7 | 9-Sep-2026 | 2.900 | | | |
| 8 | `=_CreateGasDailyFixings(A2:A7, B2:B7, C4)` | shows `30512:gas_daily_fixings:Henry Hub Gas Daily:55` | | | |
| 9 | `=_CreateGasDailyFixings(A2, B2, C4)` | shows `30512:gas_daily_fixings:Henry Hub Gas Daily:56`, the fixings of one day | | | |

Two columns of one kind each and a handle, all three required, none with a default, the columns selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the IFERC fixings', columns paired by position, so that the fixings of a family are typed the same way, at the cost [inputs.md](../../seam/inputs.md) decision 38 states: two columns can be selected one row out of step, and equal lengths cannot catch it. A price is any number a cell holds, zero and below included, and Waha has printed below zero. The index comes by handle because it is an object the sheet already holds, made once by [_CreateIndex](../index-definitions/index.md) and named by its cell, as decisions 34 to 37 say: the function receives the index the seam keeps, never the text; a cell that is not an index's handle fails in the seam's words, `index is number 2.93, expected index handle`, before the function runs, and an index of another kind in the library's words, below. The seam checks each column alone, dates one column wide, numbers one column wide, no blank cells, resolves the handle, and hands over an array of days, an array of numbers and the index; nothing here restates that. A single cell is a column of one, so the fixings of one day need no range. The result is a handle: text in the cell that stands for the fixings the seam keeps, declared `Handle[GasDailyFixings]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the fixings, their index by reference and their two columns. The index is one object: the fixings and the calendar of their market refer to the same `_CreateIndex` cell, or a name for it, and are remade together when the index is.

`=util_ReadHandle(A8)` on the fixings above shows the two columns as they went in, the flow days as serials and the prices as numbers, under the two heading rows, as it did before: the spill does not change.

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
| `index` | The index handle: the cell showing _CreateIndex's result, such as C4, or a name for it; a Gas Daily index, the one these fixings belong to. |

## The library checks

Three rules, in this order, the first failure being the message. The first is the index's kind: Gas Daily fixings belong to a Gas Daily index, so a futures or an IFERC index is refused naming its kind, as the calendar names kinds, and nothing else is read from the index. The other two are the columns' own, as they were. Rows count as the sheet counts them, the first row of the column being row 1.

| Rule | Message |
|---|---|
| the index is a Gas Daily index | `index is a futures index, expected a Gas Daily index` |
| the price column has one row per flow day, since the seam never compares two columns and a series is rows | `price has 5 prices, expected 6, one per flow_date` |
| each flow day is the day after the row above, since a series that prices every calendar day has no other shape: the days increase, no day is given twice, and no day between the first and the last is missing | `flow_date row 4 is 2026-09-07, expected 2026-09-06, the day after row 3's 2026-09-05` |

A count of one reads `1 price`. The third rule is one comparison over the column, and the first row that breaks it is the one named: a day given twice, a day skipped and a series pasted newest first all fail at that row, with the day that was expected. Nothing is sorted, filled or extended: a series pasted newest first fails at its second row, and the desk sorts it; a day without a row is a row the desk did not paste, never a price to carry forward, and a day Platts printed no midpoint for is a gap the desk cannot fill, so the series is refused at it and what such a day means to an average is a rule for the instrument that averages, not for the fixings. Nothing else is checked: no weekday is looked at, no holiday list is taken, no month is read off a day, and the flow days are not held to the index's schedule, since a series may run past the calendar on either side, allowed and unused there, as the history decided in #105. The prices are copied and frozen, so the fixings own their data, the days are copied as days, and the index is kept by reference, the one the desk paired the series with. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_gas_daily_fixings.py`; the seam's texts and the handle are `tests/unit/test_market_data.py`, whose hidden reader proves the handle resolves to the fixings; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market history's tests build their Gas Daily fixings through this creator and move with it.

| Case | Kind |
|---|---|
| the six-day sample above, over the index of its month: every flow day and every price preserved, aligned, the weekend and the holiday rows among them, and the index kept | example |
| the fixings of one day accepted, from a one-row range and from two single cells; a whole month, thirty rows, kept in its order | example |
| a price below zero and a zero kept as given; the same price on four consecutive days kept as four rows | example |
| a run across a month end, 30 September to 2 October, and across a year end, kept as given: no month or year is looked at, and days outside the index's schedule are kept | example |
| a futures index and an IFERC index: rejected, naming the kind, before the columns are looked at | example |
| a price column one row short, one row long, one price for six days and six prices for one day: rejected, naming the count | example |
| a day given twice, a day skipped, two days skipped, a series pasted newest first and two days swapped in the middle: rejected, naming the row and the day expected; the count checked before the days | example |
| for any first day and any `N` consecutive days with `N` prices, everything is preserved and aligned; with one day left out, the row after the gap is refused, naming the day | property |
| an input changed after construction leaves the fixings unchanged, and both arrays refuse writes | example |
| two columns and an index read back through their handle, and two single cells the fixings of one day | example, through the seam |
| a futures index where the Gas Daily index should be, a price column one row short and a day skipped, the library's words; a blank or a time among the days, text where a day should be, a blank or text among the prices, a row where a column should be, either column left out or blank, and a number, a blank, a missing argument, text naming no live object, a creator's failure or a schedule's handle where the index should be, the seam's words, the days named first when both columns are wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short, a day skipped and a blank among the prices alike | example, with handles |
| a handle of another kind is not Gas Daily fixings, the futures fixings' and the Gas Daily schedule's included, and is not an index | example, with handles |
| the spill: two headers, two types, then a row per day, the day as a serial and the price as a number, a weekend row among them | example |
| the creator's handle over six days and over two single cells, read back through `util_ReadHandle`, a column one row short, a day skipped, a series newest first, a blank among the prices, text among the days, and the index left out or a schedule in its place, in a real workbook | Excel smoke |

## Not here

Reading the fixings against a calendar: the [market history](../market/market-history.md)'s since #105, which takes the Gas Daily calendar and these fixings, from #109 requires the two to be one index's, the same index object and not merely the same name, and requires a print on every day of the calendar through the valuation day, since a flow day is printed before it begins, and refuses a print for any day after it. Which month a flow day belongs to: the calendar's, from the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md). The flow days against the index's schedule: unchecked here, since a series may run past the calendar on either side, allowed and unused there. The day an assessment was made, the days one print covers and Platts' holidays: Platts' own, already applied when it dated the values by flow day, and the [Gas Daily schedule](../index-definitions/gas-daily-schedule.md) page says why none of them is held. A day Platts printed no midpoint for: refused here as a gap; dropped from the average under the ICE contracts and bridged under the ISDA gas annex, which the instrument's page decides. The month's average, plain Gas Daily: an instrument's arithmetic over a month's rows, and Platts publishes its own, a number a later reader may take as a month's settlement. A revised midpoint: a new fixings object, never an edit. The futures fixings, which read their holiday calendar through their index. Sorting a series, filling a missing day. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any fixings as two columns. Pricing and risk.
