# _CreateIfercSchedule

Built in #97; two columns since #204.

The IFERC schedule of one index: each contract month's code and the day the month's index is published, kept as given and reached by handle. Inside FERC, IFERC for short, is the S&P Global Platts publication whose monthly bidweek index prints once per delivery month, on the first publication day of that month; ICE's basis and fixed-price futures settle on it, the Waha and Henry basis futures among them. The publication day is the one day a trade on the month observes and, since [iferc-publication-payment-anchor.md](../../engineering-tickets/trade-valuation-pipeline/iferc-publication-payment-anchor.md), the day its payment counts from, so it is the one date this schedule holds beside the month's code; the day the exchange's future stops trading is no reader's fact and the schedule held it until #204. It is the IFERC market's own object, next to the [futures schedule](futures-schedule.md), which is the exchange's schedule of futures and options. Its readers reach it through the [index](index.md), which holds it since #107 and reads nothing of it but its kind. The [calendar](../calendar/calendar.md), since #104 and through the index since #108, makes one row per month dated by its publication day and holds it to the IFERC rules on [the calendar's page](../calendar/calendar.md#the-library-checks), each code once and the publication days increasing. The [IFERC fixings](../market-data/iferc-fixings.md), since #109, refuse a code that is none of its months and, since #147, read the publication day beside each month they are given to hold their series newest first, refusing a code the schedule holds at two rows; the [market history](../market/market-history.md) and the [market](../market/market.md) read its codes through the calendar, to put each index on its month's row and to count the quotes. [Trade creation](../trades/create-trades.md), since #167, observes each component's month on its publication day and, since #204, counts its payment from that day. [util_ReadHandle](../utilities/read-handle.md) spills it. The code is `src/catalyst/index_definitions/iferc_schedule.py`, the record and its builder, and `src/catalyst/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateIfercSchedule(
    contract_code: TextColumn,
    publication_date: DateColumn,
) -> Handle[IfercSchedule]: ...
```

Waha basis, on Platts' first publication days:

| | A | B |
|---|---|---|
| 1 | contract_code | publication_date |
| 2 | V26 | 1-Oct-2026 |
| 3 | X26 | 2-Nov-2026 |
| 4 | Z26 | 1-Dec-2026 |
| 5 | `=_CreateIfercSchedule(A2:A4, B2:B4)` | shows `30512:iferc_schedule:41` |
| 6 | `=_CreateIfercSchedule(A2, B2)` | shows `30512:iferc_schedule:42`, a schedule of one contract month |

Two columns of one kind each, both required, neither with a default, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. The form is the futures schedule's, columns paired by position rather than a table, and its cost stands as [inputs.md](../../seam/inputs.md) decision 38 states it: two columns can be selected one row out of step, and equal lengths cannot catch it. The code column is `contract_code`, as the futures schedule's is since #102, because the code labels the delivery month the index is for, and the same text also names the future on that month; nothing here reads it. The publication date is Platts', the day the index for that month prints, which the desk takes from Platts' calendar, since a holiday moves it, January 2026's index having printed on the 5th. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and an array of days; nothing here restates that. A single cell is a column of one, so a schedule of one contract month needs no range. A cell still holding the three-argument form of before #204 fails in Excel's own words before the add-in runs, `#VALUE!`, never the seam's. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[IfercSchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule.

`=util_ReadHandle(A5)` on the schedule above shows the two columns as they went in, the code as text and the dates as serials, under the two heading rows:

| contract_code | publication_date |
|---|---|
| str | datetime64[D] |
| V26 | 1-Oct-2026 |
| X26 | 2-Nov-2026 |
| Z26 | 1-Dec-2026 |

## Excel help

Quoted from the declaration in `src/catalyst/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates an IFERC schedule from the contract months of one index and the day each month's index is published, and shows its handle, the text other formulas take as the schedule. |
| `contract_code` | The column of contract codes, such as A2:A4 holding V26 to Z26, one per contract month. |
| `publication_date` | The column of dates the index is published, beside the codes, such as B2:B4, one per code, the day each month is observed and the day its payment counts from. |

## The library checks

One rule: the date column has one row per code, because the seam never compares two arguments and a schedule is rows.

| Rule | Message |
|---|---|
| the date column has one row per code | `publication_date has 2 dates, expected 3, one per contract_code` |

A count of one reads `1 date`. Nothing else is checked. The codes are kept as typed, `V26` and `v26` alike, the seam's tuple as it arrived, and the dates as given, in the order given, the column copied and frozen so that a later change to the input cells changes no schedule. What a schedule must look like for a reader to use it is that reader's rule, checked where the reader is made and not here: each code once and the publication days increasing are the [calendar](../calendar/calendar.md#the-library-checks)'s, since #104, and each fixing's code one of these months, held at one row, and the fixings' months newest first by these publication days are the [IFERC fixings](../market-data/iferc-fixings.md#the-library-checks)', since #109 and #147. What a code means is no reader's rule, since no reader needs it; nothing is parsed, sorted or adjusted here. A one-row schedule is a schedule, and a calendar of one month. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_iferc_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`, one copy and one freeze fewer since #204.

| Case | Kind |
|---|---|
| the three-row sample above: every code and every date preserved, aligned, as typed | example |
| a one-row schedule accepted; twelve months kept in their order | example |
| codes in either case, a code twice, dates out of order and two months sharing a date kept as given: nothing else is checked | example |
| a publication column one row short or long, one date for three codes and three dates for one code: rejected, naming the count | example |
| for any `N` codes and any column of `N` dates, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, the array refuses writes, and the codes are the tuple that arrived | example |
| two columns read back through their handle, and two single cells a schedule of one contract month | example, through the seam |
| the date column one row long or short, the library's words; a blank or a time among the dates, text where a date should be, a number or empty text among the codes, a row where a column should be, either column left out or blank, the seam's words, the codes named first when both are wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short and a blank among the dates alike | example, with handles |
| a handle of another kind is not an IFERC schedule, the futures schedule's included | example, with handles |
| the spill: two headers, two types, then a row per contract month, the code as text and the date as a serial | example |
| the creator's handle over three rows and over two single cells, read back through `util_ReadHandle`, the column one row long and one row short, a blank among the publication dates, a number among the codes, the publication dates left out and a row where a column is expected, in a real workbook | Excel smoke |

## Not here

Reading the schedule: its readers, named at the top, each checking what it needs where it is made, none reading a code for its month. Which month is quoted first on a given day: the [market](../market/market.md)'s since #106, the first month whose index has not published, the one publishing on the valuation day included. The day the exchange's future stops trading: no reader's fact since #204, the ICE basis futures' payment rule, the third clearing business day after it, reproduced by `+2bd` from publication whenever the index prints on the first clearing business day after, as the ticket's comparison shows, and a month printing later than that a convention decision before it is booked. The futures schedule: its publication column gone in #102, and not this schedule's concern; the monthly fixings that read the column went in #99, replaced by the [IFERC fixings](../market-data/iferc-fixings.md), keyed by month. The final settlement of a contract month and where it is kept, options on the IFERC fixed-price futures, and the delivery month's first and last days: each with the instrument that first needs it. Whether a publication date is a day Platts publishes: the schedule's author's. What a code means: `V26` is text, never read as a month and a year; what it will mean, one spelling and the rules the builder takes on when it reads codes, is decided in [time.md](../time.md). A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule. Pricing and risk.
