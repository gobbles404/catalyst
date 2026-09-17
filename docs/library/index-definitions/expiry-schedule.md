# _CreateExpirySchedule

Built in #60.

The contract months of one index: each contract's code, the day its future expires and, for an index that has options, the day its option expires, kept as given and reached by handle. Nothing reads the schedule yet; the first consumer, the function that says which contract is prompt on a given date, is not specified. The code is `src/goosedove/index_definitions/expiry_schedule.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateExpirySchedule(
    future_code: TextColumn,
    future_expiry: DateColumn,
    option_expiry: DateColumn | None = None,
) -> Handle[ExpirySchedule]: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | future_code | future_expiry | option_expiry |
| 2 | m26 | 19-May-2026 | 14-May-2026 |
| 3 | n26 | 22-Jun-2026 | 16-Jun-2026 |
| 4 | q26 | 21-Jul-2026 | 16-Jul-2026 |
| 5 | u26 | 20-Aug-2026 | 17-Aug-2026 |
| 6 | V26 | 22-Sep-2026 | 17-Sep-2026 |
| 7 | X26 | 20-Oct-2026 | 15-Oct-2026 |
| 8 | `=_CreateExpirySchedule(A2:A7, B2:B7, C2:C7)` | shows `expiry_schedule:3f9a1c:000004` |
| 9 | `=_CreateExpirySchedule(A2:A7, B2:B7)` | shows `expiry_schedule:3f9a1c:000005`, an index with no options |

Three columns of one kind each, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The owner chose columns over a table to put the typed columns through a real function, and the third column can be left out, which a table cannot do; the cost is that two columns can be selected one row out of step and equal lengths cannot catch it. This is the first function to take columns of one kind without headers, the case [inputs.md](../../seam/inputs.md) decision 38 left to the next few functions. The third argument is left out for an index that has no options, declared `DateColumn | None = None`, the seam's form for an argument that may be left out with nothing in its place ([inputs.md](../../seam/inputs.md) decision 39): the function receives `None` only when the argument is left out, and a blank cell in that slot fails as a blank. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and arrays of days; nothing here restates that. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[ExpirySchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates an expiry schedule from the contract codes of one index and their expiry dates, and shows its handle, the text other formulas take as the schedule. |
| `future_code` | The column of contract codes, such as A2:A7 holding m26 to X26, one per contract. |
| `future_expiry` | The column of future expiry dates beside the codes, such as B2:B7, one per code. |
| `option_expiry` | The column of option expiry dates beside the codes, such as C2:C7, one per code. |

Registration shows the third as `[option_expiry]` with its line alone: there is nothing to name after the sentence, and the brackets say it may be left out. The line is written as if the argument were required, as every line is.

## The library checks

One rule: the columns have one row per code, because the seam never compares two arguments and a schedule is rows.

| Rule | Message |
|---|---|
| every column given has one row per code | `future_expiry has 5 dates, expected 6, one per future_code` |

A count of one reads `1 date`. The futures column is checked before the options column, so when both are wrong the futures column is named. Nothing else is checked. The codes are kept as typed, `m26` and `V26` alike, the dates as given, in the order given. What a schedule must look like for a reader to use it, whether codes repeat, whether dates increase, how an option's expiry sits against its future's, is that reader's rule, written when the reader is. A one-row schedule is a schedule. A failed call publishes nothing.

## Tests

The examples and properties below are `tests/unit/test_expiry_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the six-row sample above: every code and both dates preserved, aligned, as typed | example |
| the same with `option_expiry` left out: the other two preserved, options retained as none | example |
| a one-row schedule accepted | example |
| repeated codes, dates out of order and an option after its future are kept as given: nothing else is checked | example |
| a futures column one row short, and an options column one row long: rejected, naming the count | example |
| for any `N` codes and any two columns of `N` dates, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, and its arrays refuse writes | example |
| a failed construction publishes no object and no handle | example, with handles |
| a blank cell in the options column fails in the seam's words, not as an argument left out | example, through the seam |
| the creator's handle with and without options, and a column one row short, in a real workbook | Excel smoke |

## Not here

Which contract is prompt on a given date, and the roll rule that says whether a contract is still prompt on its own expiry day: the first consumer's job, with whatever it needs a schedule to hold true. Business-day adjustment: every date in the library is a calendar day. What a code means: `m26` is text, never read as a month and a year; what it will mean, one spelling `M26` and the rules the builder takes on when it reads codes, is decided in [time.md](../time.md). The index's name, its exchange, its units, tick size, first notice, last delivery, settlement. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule, with or without options. Market data, pricing.
