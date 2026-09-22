# _CreatePublicationSchedule

Built in #90.

The publication schedule of one reference index: each contract's code and the day the index's reference price for that contract is published, kept as given and reached by handle. It is the fifth index definition, and the first to hold a fact of the publisher rather than the exchange: an expiry is the exchange's, the day a monthly index prints is the publisher's, and a gas market can have both, IFERC's monthly indices beside the NYMEX futures they settle against. Since #80 the [expiry schedule](expiry-schedule.md) carries a publication date beside each future, and the monthly [calendar](../calendar/calendar.md) and [market history](../market/market-history.md) read it there; this object is where that fact will live on its own. Its first planned reader is a publication-schedule path of `_CreateCalendar`, a later ticket, which takes this schedule directly, without an expiry schedule, row `i` pairing `codes[i]` with `publication_date[i]`, and after it the market history matching fixings to the scheduled dates; what a code must mean, whether codes repeat, whether dates increase and which fixings must be present are those readers' rules, written when they are. There is no join by code or by position with the expiry schedule. Nothing reads it yet but `util_ReadHandle`. The code is `src/goosedove/index_definitions/publication_schedule.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreatePublicationSchedule(
    contract_code: TextColumn,
    publication_date: DateColumn,
) -> Handle[PublicationSchedule]: ...
```

| | A | B |
|---|---|---|
| 1 | contract_code | publication_date |
| 2 | X26 | 2-Nov-2026 |
| 3 | Z26 | 1-Dec-2026 |
| 4 | `=_CreatePublicationSchedule(A2:A3, B2:B3)` | shows `publication_schedule:3f9a1c:000041` |
| 5 | `=_CreatePublicationSchedule(A2, B2)` | shows `publication_schedule:3f9a1c:000042`, a schedule of one contract |

Two columns of one kind each, both required, selected without the header row: row 1 is for the person reading the sheet, and the function never sees it. Rows are paired by position, and the cost [inputs.md](../../seam/inputs.md) decision 38 states stands: two columns can be selected one row out of step, and equal lengths cannot catch it. The code column is `contract_code`, not the expiry schedule's `future_code`, on purpose: it labels the reference period a price is published for, a month for a monthly index, where `future_code` labels a futures contract; the two are often the same text, and nothing here says they must be. The seam checks each column alone, text one column wide, dates one column wide, no blank cells, and hands over a tuple of texts and an array of days; nothing here restates that. A single cell is a column of one, so a schedule of one contract needs no range. The result is a handle: text in the cell that stands for the schedule the seam keeps, declared `Handle[PublicationSchedule]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the schedule.

`=util_ReadHandle(A4)` on the schedule above shows the two columns as they went in, the code as text and the date as a serial, under the two heading rows:

| contract_code | publication_date |
|---|---|
| str | datetime64[D] |
| X26 | 2-Nov-2026 |
| Z26 | 1-Dec-2026 |

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a publication schedule from the contract codes of one index and the dates their reference prices are published, and shows its handle, the text other formulas take as the schedule. |
| `contract_code` | The column of contract codes, such as A2:A3 holding X26 and Z26, one per contract. |
| `publication_date` | The column of publication dates beside the codes, such as B2:B3, one per code. |

## The library checks

One rule: the date column has one row per code, because the seam never compares two arguments and a schedule is rows.

| Rule | Message |
|---|---|
| the date column has one row per code | `publication_date has 2 dates, expected 3, one per contract_code` |

A count of one reads `1 date`. Nothing else is checked. The codes are kept as typed, `x26` and `X26` alike, the seam's tuple as it arrived, and the dates as given, in the order given, copied and frozen so that a later change to the input cells changes no schedule. What a schedule must look like for a reader to use it, whether codes repeat, whether dates increase, what a code means, is that reader's rule, written when the reader is; nothing is parsed, sorted or adjusted here. A one-row schedule is a schedule. A failed call publishes nothing, and a column the seam rejects never reaches the function.

## Tests

The examples and property below are `tests/unit/test_publication_schedule.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the schedule; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the two-row sample above: both codes and both dates preserved, aligned, as typed | example |
| a one-row schedule accepted; twelve rows kept in their order | example |
| codes in either case, a code twice, a date twice and dates out of order kept as given: nothing else is checked | example |
| a date column one row short, one row long, two dates for one code and one date for three: rejected, naming the count | example |
| for any `N` codes and any column of `N` dates, everything is preserved and aligned | property |
| an input changed after construction leaves the schedule unchanged, its array refuses writes, and the codes are the tuple that arrived | example |
| two columns read back through their handle, and two single cells a schedule of one contract | example, through the seam |
| a date column one row long or short, the library's words; a blank or a time among the dates, text where a date should be, a number or empty text among the codes, a row where either column should be, either column left out or blank, the seam's words, the codes named first when both columns are wrong | example, through the seam |
| a failed construction publishes no object and no handle, a column one row short and a blank among the dates alike | example, with handles |
| a handle of another kind is not a publication schedule | example, with handles |
| the spill: two headers, two types, then a row per contract, the code as text and the date as a serial | example |
| the creator's handle over two rows and over two single cells, read back through `util_ReadHandle`, a column one row long and one row short, a blank among the dates, a number among the codes, the dates left out and a row where a column is expected, in a real workbook | Excel smoke |

## Not here

Reading the schedule for anything: the calendar's publication-schedule path, a later ticket, and the market history after it, which will decide what a code means, whether codes and dates must be unique and in order, and which fixings must be present. The expiry schedule's own publication column and its readers: unchanged until they migrate to this object, after which the column goes; the intended end state is that this schedule is the one home of the fact. Delivery months and contract-month parsing, holidays, the calendar, the fixings, balance-of-month and the order of a price vector: their own pages and tickets. Whether a publication date is a business day of the publisher: the schedule's author's. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any schedule. Pricing and risk.
