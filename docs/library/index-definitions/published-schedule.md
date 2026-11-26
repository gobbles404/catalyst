# _CreatePublishedSchedule

The published schedule of one index: its dated prints, one row each, with the date the publisher puts on the print and the code of the contract month the print counts toward. A print is one published price. It is the schedule of an index whose price is a listed set of prints, a weekly one such as the U.S. Energy Information Administration's retail diesel price, dated each Monday, a twice-weekly one, or one print a month; the design and its decisions are [issue #271](https://github.com/gobbles404/catalyst/issues/271). It stands beside the [futures schedule](futures-schedule.md), the [IFERC schedule](iferc-schedule.md) and the [Gas Daily schedule](gas-daily-schedule.md). The [index](index.md) holds it and reads its kind, `published`, off it; the [calendar](../calendar/calendar.md) makes one row per print from it; [util_ReadHandle](../utilities/read-handle.md) spills it. The code is `src/catalyst/index_definitions/published_schedule.py`, the record and its builder, and `src/catalyst/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreatePublishedSchedule(
    contract_code: TextColumn,
    publication_date: DateColumn,
) -> Handle[PublishedSchedule]: ...
```

The four weekly diesel prints of September 2026, each dated its Monday, between the last print of August and the first of October:

| | A | B |
|---|---|---|
| 1 | contract_code | publication_date |
| 2 | Q26 | 31-Aug-2026 |
| 3 | U26 | 7-Sep-2026 |
| 4 | U26 | 14-Sep-2026 |
| 5 | U26 | 21-Sep-2026 |
| 6 | U26 | 28-Sep-2026 |
| 7 | V26 | 5-Oct-2026 |
| 8 | `=_CreatePublishedSchedule(A2:A7, B2:B7)` | shows `30512:published_schedule:41` |
| 9 | `=_CreatePublishedSchedule(A3, B3)` | shows `30512:published_schedule:42`, a schedule of one print |

Two columns of one kind each, both required, neither with a default, selected without the header row. They are the two columns the IFERC schedule takes, with one difference: a code repeats down the rows of its month, one row per print, oldest first. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and an array of days; nothing here restates that. A single cell is a column of one. The result is a handle, declared `Handle[PublishedSchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says.

A print has one date, the date the publisher puts on the price: the Monday for the diesel price, whatever day it reaches the desk. Which month a print counts toward is the code on its row and never its date. So a price dated the last day of a month counts toward that month when its row says so, and four prints or five are a month alike.

Inside, the schedule keeps the months once each, in the order their prints were given, and for each print the month it counts toward and its date. The months are the axis every reader of a schedule counts along, so a month has one forward price however many prints it has, and an index over this schedule reads back three contracts for the six prints above.

`=util_ReadHandle(A8)` shows the schedule a row per print, the creator's own form, so the spill given back to the creator makes the same schedule:

| contract_code | publication_date |
|---|---|
| str | datetime64[D] |
| Q26 | 31-Aug-2026 |
| U26 | 7-Sep-2026 |
| U26 | 14-Sep-2026 |
| U26 | 21-Sep-2026 |
| U26 | 28-Sep-2026 |
| V26 | 5-Oct-2026 |

## Excel help

Quoted from the declaration in `src/catalyst/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a published schedule from the dated prints of one index, each print's date and the contract month it counts toward, and shows its handle, the text other formulas take as the schedule. |
| `contract_code` | The column of contract codes, one per print, such as A2:A5 holding U26 four times: the month each print counts toward, a month's prints in consecutive rows. |
| `publication_date` | The column of dates the publisher puts on each print, beside the codes, such as B2:B5, one per code, oldest first; a print is fixed from the day after its date. |

## The library checks

Three rules, in this order, the first failure being the message. Rows count as the sheet counts them, the first row of a column being row 1.

| Rule | Message |
|---|---|
| the date column has one row per code | `publication_date has 5 dates, expected 6, one per contract_code` |
| each month's prints stand in consecutive rows: a code never returns once another has begun | `contract_code row 4 is 'U26', a month whose prints ended at row 2, expected each month's prints in consecutive rows` |
| each date is after the one above | `publication_date row 3 is 2026-09-07, expected a date after row 2's 2026-09-07` |

A count of one reads `1 date`. The third rule keeps the prints oldest first and refuses a date listed twice; nothing is sorted, so a schedule pasted newest first fails at its second row.

These are the schedule's own rules, checked here once, and not a reader's. The months are read off the rows where the code changes, so a code met a second time would be two months of one name; and every reader counts along the months and searches the dates. The sibling schedules leave their order to the [calendar](../calendar/calendar.md#the-library-checks); this one does not, and the calendar over it looks at nothing of the order again.

The codes are compared as typed, `U26` and `u26` two months, and no code is read for its month. The date column is copied and frozen, so a later change to the input cells changes no schedule. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and properties are `tests/unit/test_published_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`: the work is by column, never by print.

| Case | Kind |
|---|---|
| the sample above: each month kept once, every print on its month, the dates as given | example |
| one print; one print a month, a month per row; a print's month the code on its row, a date in one calendar month counted toward the next; codes compared as typed; no rows, a schedule of no months | example |
| a publication column short or long: refused, naming the count | example |
| a month whose code returns after one other, after several, and two that return: refused at the first row from the top, naming where its prints ended | example |
| a date listed twice, a date before the one above, a schedule pasted newest first: refused, naming both rows | example |
| the rules run in order: the count, then the months, then the dates | example |
| for any months of one to six prints with distinct codes and increasing dates, every print is kept on its month | property |
| for any distinct codes with one given again at the end, the schedule is refused at that row | property |
| an input changed after construction leaves the schedule unchanged, and both arrays refuse writes | example |
| two columns read back through their handle, two single cells a schedule of one print; the library's three rules and the seam's words for a blank, a time, text among the dates, a number or empty text among the codes, a row where a column should be, either column left out or blank | example, through the seam |
| a failed construction publishes no object and no handle; an IFERC schedule's handle is not a published schedule's, nor the other way | example, with handles |
| the creator's handle over six rows and over one print, read back through `util_ReadHandle`, and the refusals, in a real workbook | Excel smoke |

## Not here

The prices of the prints, entered by publication date; a price for each print that has fixed, and the stand-in for one the publisher has not released yet; trades that average a month's prints; date windows and quoting; and the IFERC schedule moving onto this kind: the later steps of [issue #271](https://github.com/gobbles404/catalyst/issues/271), each its own pull request. Until trades are built, a batch on a published index is refused by its kind. A release date: the schedule holds one date per print, by the owner's decision on the issue. A holiday calendar: an index over this schedule takes no `holiday_key`, every print being a price. Whether a date is a day the publisher prints on, and which month a print should count toward: the schedule's author's. What a code means: text here, never read as a month. Pricing and risk.
