# _CreateIfercSchedule

Built in #97.

The IFERC schedule of one index: each contract month's code, the day the month's future stops trading and the day the month's index is published, kept as given and reached by handle. Inside FERC, IFERC for short, is the S&P Global Platts publication whose monthly bidweek index prints once per delivery month, on the first publication day of that month; ICE's basis and fixed-price futures settle on it, the Waha and Henry basis futures among them, each stopping trading on the last business day before its delivery month and settling to the index printed after. So an IFERC contract month has two dates, one the exchange's and one the publisher's, and this schedule holds both beside the month's code. It is the IFERC market's own object, next to the [futures schedule](futures-schedule.md), which is the exchange's schedule of futures and options. Its readers reach it through the [index](index.md), which holds it since #107 and reads nothing of it but its kind. The [calendar](../calendar/calendar.md), since #104 and through the index since #108, makes one row per month dated by its publication day and holds it to the IFERC rules on [the calendar's page](../calendar/calendar.md#the-library-checks), each code once and the publication days increasing. The [IFERC fixings](../market-data/iferc-fixings.md), since #109, refuse a code that is none of its months and, since #147, read the publication day beside each month they are given to hold their series newest first, refusing a code the schedule holds at two rows; the [market history](../market/market-history.md) and the [market](../market/market.md) read its codes through the calendar, to put each index on its month's row and to count the quotes. [util_ReadHandle](../utilities/read-handle.md) spills it, and is the one reader of its last trading dates. No instrument reads it yet; the instruments to come will reach it the same way, through the index and its calendar. The code is `src/goosedove/index_definitions/iferc_schedule.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateIfercSchedule(
    contract_code: TextColumn,
    last_trading_date: DateColumn,
    publication_date: DateColumn,
) -> Handle[IfercSchedule]: ...
```

Waha basis, on ICE's listed last trading days and Platts' first publication days:

| | A | B | C |
|---|---|---|---|
| 1 | contract_code | last_trading_date | publication_date |
| 2 | V26 | 30-Sep-2026 | 1-Oct-2026 |
| 3 | X26 | 30-Oct-2026 | 2-Nov-2026 |
| 4 | Z26 | 30-Nov-2026 | 1-Dec-2026 |
| 5 | `=_CreateIfercSchedule(A2:A4, B2:B4, C2:C4)` | shows `30512:iferc_schedule:41` | |
| 6 | `=_CreateIfercSchedule(A2, B2, C2)` | shows `30512:iferc_schedule:42`, a schedule of one contract month | |

Three columns of one kind each, all required, none with a default, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the futures schedule's, columns paired by position rather than a table, and its cost stands as [inputs.md](../../seam/inputs.md) decision 38 states it: two columns can be selected one row out of step, and equal lengths cannot catch it. The code column is `contract_code`, as the futures schedule's is since #102, because the code labels the delivery month the index is for, and the same text also names the future on that month; nothing here reads it. The last trading date is the exchange's fact, the day the future on that month stops trading, which for the ICE basis futures is the last business day before the month; the publication date is Platts', the day the index for that month prints, which the desk takes from Platts' calendar, since a holiday moves it, January 2026's index having printed on the 5th. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and two arrays of days; nothing here restates that. A single cell is a column of one, so a schedule of one contract month needs no range. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[IfercSchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule.

`=util_ReadHandle(A5)` on the schedule above shows the three columns as they went in, the code as text and the dates as serials, under the two heading rows:

| contract_code | last_trading_date | publication_date |
|---|---|---|
| str | datetime64[D] | datetime64[D] |
| V26 | 30-Sep-2026 | 1-Oct-2026 |
| X26 | 30-Oct-2026 | 2-Nov-2026 |
| Z26 | 30-Nov-2026 | 1-Dec-2026 |

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates an IFERC schedule from the contract months of one index, the day each month's future stops trading and the day its index is published, and shows its handle, the text other formulas take as the schedule. |
| `contract_code` | The column of contract codes, such as A2:A4 holding V26 to Z26, one per contract month. |
| `last_trading_date` | The column of last trading dates beside the codes, such as B2:B4, one per code. |
| `publication_date` | The column of dates the index is published, beside the codes, such as C2:C4, one per code. |

## The library checks

One rule: each date column has one row per code, because the seam never compares two arguments and a schedule is rows.

| Rule | Message |
|---|---|
| each date column has one row per code | `last_trading_date has 2 dates, expected 3, one per contract_code`, or `publication_date has 2 dates, expected 3, one per contract_code` |

A count of one reads `1 date`. The last trading dates are checked before the publication dates, so when both columns are wrong the earlier is named. Nothing else is checked. The codes are kept as typed, `V26` and `v26` alike, the seam's tuple as it arrived, and the dates as given, in the order given, each column copied and frozen so that a later change to the input cells changes no schedule. What a schedule must look like for a reader to use it is that reader's rule, checked where the reader is made and not here: each code once and the publication days increasing are the [calendar](../calendar/calendar.md#the-library-checks)'s, since #104, and each fixing's code one of these months, held at one row, and the fixings' months newest first by these publication days are the [IFERC fixings](../market-data/iferc-fixings.md#the-library-checks)', since #109 and #147. Whether the last trading dates increase, whether a month's index prints after its future stops trading and what a code means are no reader's rule, since no reader needs them; nothing is parsed, sorted or adjusted here. A one-row schedule is a schedule, and a calendar of one month. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_iferc_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the three-row sample above: every code and both dates preserved, aligned, as typed | example |
| a one-row schedule accepted; twelve months kept in their order | example |
| codes in either case, a code twice, dates out of order, two months sharing a date and a publication before its last trading date kept as given: nothing else is checked | example |
| a last trading column one row short or long, a publication column one row short or long, and one date for three codes: rejected, naming the count; both columns wrong names the last trading dates | example |
| for any `N` codes and any two columns of `N` dates, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, both arrays refuse writes, and the codes are the tuple that arrived | example |
| three columns read back through their handle, and three single cells a schedule of one contract month | example, through the seam |
| a date column one row long or short, the library's words; a blank or a time among the dates, text where a date should be, a number or empty text among the codes, a row where a column should be, any column left out or blank, the seam's words, the codes named first when more than one column is wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short and a blank among the dates alike | example, with handles |
| a handle of another kind is not an IFERC schedule, the futures schedule's included | example, with handles |
| the spill: three headers, three types, then a row per contract month, the code as text and both dates as serials | example |
| the creator's handle over three rows and over three single cells, read back through `util_ReadHandle`, a column one row long and one row short, a blank among the publication dates, a number among the codes, the publication dates left out and a row where a column is expected, in a real workbook | Excel smoke |

## Not here

Reading the schedule: its readers, named at the top, each checking what it needs where it is made, none reading a code for its month. Which month is quoted first on a given day: the [market](../market/market.md)'s since #106, the first month whose index has not published, the one publishing on the valuation day included. Whether a month's index must print after its future stops trading: no reader's, until one needs it. The futures schedule: its publication column gone in #102, and not this schedule's concern; the monthly fixings that read the column went in #99, replaced by the [IFERC fixings](../market-data/iferc-fixings.md), keyed by month. The final settlement of a contract month and where it is kept, options on the IFERC fixed-price futures, the day a settlement is paid, and the delivery month's first and last days: each with the instrument that first needs it. Whether a publication date is a day Platts publishes: the schedule's author's. What a code means: `V26` is text, never read as a month and a year; what it will mean, one spelling and the rules the builder takes on when it reads codes, is decided in [time.md](../time.md). A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule. Pricing and risk.
