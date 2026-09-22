# _CreateDeliverySchedule

Built in #92.

The delivery schedule of one reference index: each contract's code and the first and last day it delivers, both days included, kept as given and reached by handle. It is the sixth index definition and the second, after the [publication schedule](publication-schedule.md), to hold a fact of the reference period rather than of an exchange-traded future: a code names a period, a month for a monthly index, and the two dates say which calendar days the period covers, a run of any length, a single day when the two are equal, and not only a calendar month. Nothing is inferred from the code; the dates are the schedule's bounds. Its first planned reader is a delivery-schedule path of `_CreateCalendar`, a later ticket, which takes this schedule directly, without an expiry or a publication schedule, row `i` pairing `codes[i]` with `delivery_start[i]` and `delivery_end[i]`; what a code must mean, whether codes repeat, whether periods follow one another, overlap or leave gaps, are that reader's rules, written when it is, so that it assigns each delivery day to one contract without ambiguity. Nothing reads it yet but `util_ReadHandle`. The code is `src/goosedove/index_definitions/delivery_schedule.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateDeliverySchedule(
    contract_code: TextColumn,
    delivery_start: DateColumn,
    delivery_end: DateColumn,
) -> Handle[DeliverySchedule]: ...
```

| | A | B | C |
|---|---|---|---|
| 1 | contract_code | delivery_start | delivery_end |
| 2 | X26 | 1-Nov-2026 | 30-Nov-2026 |
| 3 | Z26 | 1-Dec-2026 | 31-Dec-2026 |
| 4 | `=_CreateDeliverySchedule(A2:A3, B2:B3, C2:C3)` | shows `delivery_schedule:3f9a1c:000044` | |
| 5 | `=_CreateDeliverySchedule(A2, B2, C2)` | shows `delivery_schedule:3f9a1c:000045`, a schedule of one contract | |

Three columns of one kind each, all required, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. Rows are paired by position, and the cost [inputs.md](../../seam/inputs.md) decision 38 states stands: columns selected separately can be one row out of step, and equal lengths cannot catch it. The code column is `contract_code`, as the publication schedule's is: it labels the reference period, which needs no exchange-traded future, where the expiry schedule's `future_code` labels one; the two are often the same text, and nothing here says they must be. Both dates are calendar days and both are included, so `1-Dec-2026` to `1-Dec-2026` is a period of one day, and a period need not be a calendar month. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and two arrays of days; nothing here restates that. A single cell is a column of one, so a schedule of one contract needs no range. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[DeliverySchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule.

`=util_ReadHandle(A4)` on the schedule above shows the three columns as they went in, the code as text and the days as serials, under the two heading rows:

| contract_code | delivery_start | delivery_end |
|---|---|---|
| str | datetime64[D] | datetime64[D] |
| X26 | 1-Nov-2026 | 30-Nov-2026 |
| Z26 | 1-Dec-2026 | 31-Dec-2026 |

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a delivery schedule from the contract codes of one index and their first and last delivery dates, and shows its handle, the text other formulas take as the schedule. |
| `contract_code` | The column of contract codes, such as A2:A3 holding X26 and Z26, one per contract. |
| `delivery_start` | The column of first delivery dates beside the codes, such as B2:B3, one per code. |
| `delivery_end` | The column of last delivery dates beside the codes, such as C2:C3, one per code. |

## The library checks

Three rules, in this order, the first failure being the message. Rows count as the sheet counts them, the first row of the columns being row 1.

| Rule | Message |
|---|---|
| the start column has one row per code | `delivery_start has 2 dates, expected 3, one per contract_code` |
| the end column has one row per code | `delivery_end has 2 dates, expected 3, one per contract_code` |
| each end is on or after its start, since a period that ends before it starts covers no day | `delivery_end row 2 is 2026-12-01, expected a date on or after row 2's delivery_start 2026-12-02` |

A count of one reads `1 date`. The two counts are checked before any end is compared with its start, so a column the wrong length is named as such and never compared; the comparison is one over the two columns, no row walked, and the first period that ends before it starts is the one named. Nothing else is checked. The codes are kept as typed, `x26` and `X26` alike, the seam's tuple as it arrived, and the dates as given, in the order given, each column copied and frozen so that a later change to the input cells changes no schedule. What a schedule must look like for a reader to use it, whether codes repeat, whether periods are months, whether they follow one another, overlap or leave gaps, what a code means, is that reader's rule, written when the reader is; nothing is parsed, sorted or adjusted here. A one-row schedule is a schedule. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_delivery_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, creating and reading back, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the two-row sample above: both codes and all four dates preserved, aligned, as typed | example |
| a one-row schedule accepted; a single day, a week, a fortnight from a Wednesday and a quarter kept as given; twelve rows kept in their order | example |
| codes in either case and a code twice, a period twice, periods that overlap, a gap between periods and rows out of order kept as given: nothing else is checked | example |
| a start column one row short or long, an end column one row short or long, two dates for one code: rejected, naming the count; both columns short names the starts | example |
| an end before its start on the second row, the columns swapped on the first, and the ticket's example, a day before its start: rejected, naming the row and both dates; a short column named before a reversed period | example |
| for any `N` codes, any column of `N` starts and ends none before its start, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, both arrays refuse writes, and the codes are the tuple that arrived | example |
| three columns read back through their handle; three single cells a schedule of one contract, and equal dates a period of one day | example, through the seam |
| a start column one row short, an end column one row long, an end before its start and the columns swapped, the library's words; a blank or a time among the dates, text where a date should be, a number among the codes, a row where a column should be, any column left out or blank, the seam's words, the seam's blank before the library's count | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short, an end before its start and a blank among the ends alike | example, with handles |
| a handle of another kind is not a delivery schedule | example, with handles |
| the spill: three headers, three types, then a row per contract, the code as text and both days as serials | example |
| the creator's handle over two rows, over three single cells and over ends that make a single day, read back through `util_ReadHandle`, an end column one row long, a start column one row short, an end before its start, a blank among the ends, a number among the codes and the ends left out, in a real workbook | Excel smoke |

## Not here

Reading the schedule for anything: the calendar's delivery-schedule path, a later ticket, which will decide what a code means, whether codes and periods must be unique, in order, contiguous or free of overlaps, and how each delivery day finds its contract; and after it the history and the market along those days. Expanding a period into its days, the holidays within it, mapping an assessment to the days it delivers, which fixings a period needs, balance-of-month and the order of a price vector: those later calendar, history and market tickets. The expiry schedule and the publication schedule: unchanged, and this schedule needs neither. Whether a period is a business day of any market: the schedule's author's. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule. Pricing and risk.
