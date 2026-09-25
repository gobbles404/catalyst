# _CreateFuturesSchedule

Ready to ship: the futures' name, `contract_code` and no publication column, instead of the expiry schedule of #60 with the publication dates of #80.

The futures schedule of one index: the contract months it trades, each contract's code, the day its future expires and, for an index that has options, the day its option expires, kept as given and reached by handle. It is the futures market's own schedule, as the [IFERC schedule](iferc-schedule.md) is the IFERC market's and the [Gas Daily schedule](gas-daily-schedule.md) the Gas Daily market's, and it holds the two dates a futures contract has and nothing a publisher decides: a future's settle is traded to its expiry, so no day of publication belongs here. The expiry schedule of #60 carried a fourth column from #80, the day each contract's settle is published, for the monthly fixings of #81; those went in #99, the [IFERC schedule](iferc-schedule.md) of #97 holds the publication day beside each month since, and the column has been read by nothing since. It goes here, with the name: `_CreateExpirySchedule` becomes `_CreateFuturesSchedule`, its first column `contract_code` as the two sibling schedules' is, and the record `FuturesSchedule`. Since #82 the [calendar](../calendar/calendar.md) reads the codes and the futures' expiries to say which contract is prompt on each day, the expiry day belonging to the expiring contract and the first contract only bounding it; it takes the schedule as `futures_schedule` from #NN, and the calendar's tests, the market history's and the market's build their schedule through this creator and move with it, their own cases unchanged. The code is `src/goosedove/index_definitions/futures_schedule.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

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
| 8 | `=_CreateFuturesSchedule(A2:A7, B2:B7, C2:C7)` | shows `futures_schedule:3f9a1c:000004` |
| 9 | `=_CreateFuturesSchedule(A2:A7, B2:B7)` | shows `futures_schedule:3f9a1c:000005`, an index with no options |

Three columns of one kind each, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the family's, columns paired by position, at the cost [inputs.md](../../seam/inputs.md) decision 38 states: two columns can be selected one row out of step, and equal lengths cannot catch it. The third column is left out for an index that has no options, declared `DateColumn | None = None`, the seam's form for an argument that may be left out with nothing in its place ([inputs.md](../../seam/inputs.md) decision 39): the function receives `None` only when the argument is left out, and a blank cell in that slot fails as a blank. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and arrays of days; nothing here restates that. A single cell is a column of one, so a schedule of one contract needs no range. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[FuturesSchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule. `=util_ReadHandle(A8)` shows the three columns as they went in under the two heading rows, `contract_code`, `future_expiry` and `option_expiry`, and two columns for a schedule without options.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

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

A count of one reads `1 date`. The futures column is checked before the options column, so when both are wrong the futures column is named. A column left out is kept as none and takes no check. Nothing else is checked. The codes are kept as typed, `m26` and `V26` alike, the dates as given, in the order given. What a schedule must look like for a reader to use it, whether codes repeat, whether dates increase and how an option's expiry sits against its future's, is that reader's rule, written when the reader is; the calendar's, since #82, is that the futures' expiries increase. A one-row schedule is a schedule. A failed call publishes nothing.

## Tests

The examples and property below are `tests/unit/test_futures_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The calendar's, the market history's and the market's tests build their schedule through this creator and move with it, and the calendar's argument, `expiry_schedule` until #NN, is `futures_schedule`, the seam's handle words with it; their own cases are unchanged.

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
| a handle of another kind is not a futures schedule, the IFERC schedule's included | example, with handles |
| the spill: three columns with options and two without, under the two heading rows | example |
| the creator's handle with and without options read back through `util_ReadHandle`, a column one row short, a blank among the options and a fourth argument, in a real workbook | Excel smoke |

## Not here

Which contract is prompt on a given date is the calendar's since #82, the expiry day belonging to the expiring contract; a roll lag, when a market states one, is the nearby reader's, with whatever it needs a schedule to hold true. The day a settle is published: a fact of an index settled on a published index, held by the [IFERC schedule](iferc-schedule.md) since #97 and by no futures schedule, since a future's settle is traded to its expiry. Whether an option's expiry must sit on or before its future's: not checked, a reader's rule, as [time.md](../time.md) proposes it. Business-day adjustment: every date in the library is a calendar day. What a code means: `m26` is text, never read as a month and a year; what it will mean, one spelling `M26` and the rules the builder takes on when it reads codes, is decided in [time.md](../time.md), whose messages will name `contract_code`. The calendar's own name, `_CreateCalendar` until the futures calendar is named beside the Gas Daily's: its own pull request, with the market history's and the market's. The index's name, its exchange, its units, tick size, first notice, last delivery, settlement. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule, with or without options. Market data, pricing.
