# _CreateFuturesSchedule

Built in #60; the futures' name, `contract_code` and two dates per contract since #102.

The futures schedule of one index: the contract months it trades, each contract's code, the day its future expires and, for an index that has options, the day its option expires, kept as given and reached by handle. It is the futures market's own schedule, as the [Gas Daily schedule](gas-daily-schedule.md) is the Gas Daily market's and the [published schedule](published-schedule.md) a published index's, and it holds the two dates a futures contract has and nothing a publisher decides: a future's settle is traded to its expiry, so no day of publication belongs here. The expiry schedule of #60 carried a fourth column from #80, the day each contract's settle is published, for the monthly fixings of #81; those went in #99, and the column has been read by nothing since. It goes here, with the name: `_CreateExpirySchedule` becomes `_CreateFuturesSchedule`, its first column `contract_code` as the two sibling schedules' is, and the record `FuturesSchedule`. Its readers reach it through the [index](index.md), which holds it since #107 and reads nothing of it but its kind. The [calendar](../calendar/calendar.md), since #82 and through the index since #108, reads the codes and the futures' expiries to say which contract is prompt on each day, the expiry day belonging to the expiring contract and the first contract only bounding it, and holds the schedule to the futures rules on [the calendar's page](../calendar/calendar.md#the-library-checks), two contracts or more, each code once, the expiries increasing and a span a sheet can show. The [market](../market/market.md) reads its codes through the calendar to count the quotes, and [util_ReadHandle](../utilities/read-handle.md) spills it, the one reader of its option expiries. The code is `src/catalyst/index_definitions/futures_schedule.py`, the record and its builder, and `src/catalyst/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateFuturesSchedule(
    contract_code: TextColumn,
    future_expiry: DateColumn,
    option_expiry: DateColumn | None = None,
) -> Handle[FuturesSchedule]: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | contract_code | future_expiry | option_expiry |
| 2 | m26 | 19-May-2026 | 14-May-2026 |
| 3 | n26 | 22-Jun-2026 | 16-Jun-2026 |
| 4 | q26 | 21-Jul-2026 | 16-Jul-2026 |
| 5 | u26 | 20-Aug-2026 | 17-Aug-2026 |
| 6 | V26 | 22-Sep-2026 | 17-Sep-2026 |
| 7 | X26 | 20-Oct-2026 | 15-Oct-2026 |
| 8 | `=_CreateFuturesSchedule(A2:A7, B2:B7, C2:C7)` | shows `30512:futures_schedule:4` |
| 9 | `=_CreateFuturesSchedule(A2:A7, B2:B7)` | shows `30512:futures_schedule:5`, an index with no options |

Three columns of one kind each, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the family's, columns paired by position, at the cost [inputs.md](../../seam/inputs.md) decision 38 states: two columns can be selected one row out of step, and equal lengths cannot catch it. The third column is left out for an index that has no options, declared `DateColumn | None = None`, the seam's form for an argument that may be left out with nothing in its place ([inputs.md](../../seam/inputs.md) decision 39): the function receives `None` only when the argument is left out, and a blank cell in that slot fails as a blank. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and arrays of days; nothing here restates that. A single cell is a column of one, so a schedule of one contract needs no range. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[FuturesSchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule. `=util_ReadHandle(A8)` shows the three columns as they went in under the two heading rows, `contract_code`, `future_expiry` and `option_expiry`, and two columns for a schedule without options.

## Excel help

Quoted from the declaration in `src/catalyst/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the futures schedule of one index from its contract codes, the day each future expires and, where given, the day its option expires, and shows its handle, the text other formulas take as the schedule. |
| `contract_code` | The column of contract codes, such as A2:A7 holding m26 to X26, one per contract. |
| `future_expiry` | The column of future expiry dates beside the codes, such as B2:B7, one per code. |
| `option_expiry` | The column of option expiry dates beside the codes, such as C2:C7, one per code. |

Registration shows the third as `[option_expiry]`, with its line alone: there is nothing to name after the sentence, and the brackets say it may be left out. The line is written as if the argument were required, as every line is.

## The library checks

One rule: the columns have one row per code, because the seam never compares two arguments and a schedule is rows.

| Rule | Message |
|---|---|
| every column given has one row per code | `future_expiry has 5 dates, expected 6, one per contract_code`, or `option_expiry has 5 dates, expected 6, one per contract_code` |

A count of one reads `1 date`. The futures column is checked before the options column, so when both are wrong the futures column is named. A column left out is kept as none and takes no check. Nothing else is checked. The codes are kept as typed, `m26` and `V26` alike, the dates as given, in the order given. What a schedule must look like for a reader to use it is that reader's rule, checked where the reader is made and not here: two contracts or more, each code once, the futures' expiries increasing and a span a sheet can show are the [calendar](../calendar/calendar.md#the-library-checks)'s, since #82. How an option's expiry sits against its future's is no reader's rule, since no reader reads the options. A one-row schedule is a schedule, though not a calendar. A failed call publishes nothing.

## Tests

The examples and property below are `tests/unit/test_futures_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The calendar's, the market history's and the market's tests build their schedule through this creator and move with it, and hand it to the calendar through an index since #108; the calendar's argument was `expiry_schedule` until #102 and `futures_schedule` until #108.

| Case | Kind |
|---|---|
| the six-row sample above: every code and both dates preserved, aligned, as typed | example |
| the same with `option_expiry` left out: the other two preserved, the options retained as none | example |
| a one-row schedule accepted, with and without options | example |
| repeated codes, dates out of order and an option after its future are kept as given: nothing else is checked | example |
| a futures column one row short, an options column one row long, and one date for six codes: rejected, naming the count; both wrong names the futures column | example |
| for any `N` codes and any two columns of `N` dates, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, and its arrays refuse writes | example |
| the schedule read back through its handle with three columns and with two, the options left out reading none; a one-row schedule from three single cells | example, through the seam |
| a failed construction publishes no object and no handle, an options column one row short included | example, with handles |
| a blank cell in the options column fails in the seam's words, not as an argument left out; text or a row of dates where the options column should be, and a blank cell in its slot, the seam's words; a fourth argument refused as one too many | example, through the seam |
| a handle of another kind is not a futures schedule, the published schedule's included | example, with handles |
| the spill: three columns with options and two without, under the two heading rows | example |
| the creator's handle with and without options read back through `util_ReadHandle`, a column one row short and a blank among the options, in a real workbook; a fourth argument never reaches the seam, since Excel refuses it as one too many when the formula is typed | Excel smoke |

## Not here

Which contract is prompt on a given date is the calendar's since #82, the expiry day belonging to the expiring contract; a roll lag, when a market states one, is the nearby reader's, with whatever it needs a schedule to hold true. The day a price is published: a fact of a published index, held by the [published schedule](published-schedule.md) and by no futures schedule, since a future's settle is traded to its expiry. Whether an option's expiry must sit on or before its future's: not checked, a reader's rule, as [time.md](../time.md) proposes it. Business-day adjustment: every date in the library is a calendar day. What a code means: `m26` is text, never read as a month and a year; what it will mean, one spelling `M26` and the rules the builder takes on when it reads codes, is decided in [time.md](../time.md), whose messages will name `contract_code`. A calendar, history or market named for the futures market alone: none, since one [calendar](../calendar/calendar.md), one history and one market serve the three markets since #104 to #106, the index's kind choosing. The index's name, its exchange, its units, tick size, first notice, last delivery, settlement. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule, with or without options. Market data, pricing.
