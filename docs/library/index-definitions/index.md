# _CreateIndex

Built in #107.

The index behind one reference price: its name, its schedule, the conventions its price is quoted in, the contract specifications it trades as and, for a futures index, the holiday calendar of its market, four objects the sheet already holds and a name, bound once and reached by handle. Henry Hub NYMEX, Henry Hub IFERC and Henry Hub Gas Daily are three indices, each with a schedule of its own kind, and the kind of the schedule is the kind of the index. Nothing is read out of the objects and nothing in them is checked again: each was checked when it was made, and the index binds them so that what is downstream can refer to one thing. Nothing reads it yet. The [calendar](../calendar/calendar.md)'s next ticket takes the index in place of its schedule and holiday calendar, the [futures fixings](../market-data/futures-fixings.md) take the holiday calendar through it, and the instruments read units and lots through the market they price against, as the market reads its calendar. The code is `src/goosedove/index_definitions/index.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function; the kinds and the words that name an object's kind move beside it from `src/goosedove/calendar/calendar.py`, so that the index and the calendar read a schedule's kind from one place and the calendar, once it takes the index, reads the kind the index holds.

## Worksheet contract

```python
def _CreateIndex(
    name: str,
    schedule: Handle[object],
    index_conventions: Handle[IndexConventions],
    contract_specifications: Handle[ContractSpecifications],
    holiday_calendar: Handle[HolidayCalendar] | None = None,
) -> Handle[Index]: ...
```

Three Henry Hub indices, one per market, sharing one conventions cell, USD per MMBTU with quantities in MMBTU:

| | A | B | C | D |
|---|---|---|---|---|
| 1 | name | Henry Hub NYMEX | Henry Hub IFERC | Henry Hub Gas Daily |
| 2 | schedule | `futures_schedule:3f9a1c:000004`, twelve NG contract months | `iferc_schedule:3f9a1c:000041`, the [IFERC schedule](iferc-schedule.md) page's three months | `gas_daily_schedule:3f9a1c:000044`, the [Gas Daily schedule](gas-daily-schedule.md) page's three months |
| 3 | holiday calendar | `holiday_calendar:3f9a1c:000007`, the exchange's closed days | | |
| 4 | conventions | `index_conventions:3f9a1c:000008` | | |
| 5 | specifications | `contract_specifications:3f9a1c:000009`, the NYMEX and ICE lots of the [specifications](contract-specifications.md) page | `contract_specifications:3f9a1c:000046`, the ICE basis lot | `contract_specifications:3f9a1c:000047`, the ICE swap lot |
| 6 | `=_CreateIndex(B1, B2, B4, B5, B3)` | shows `index:3f9a1c:000010` | | |
| 7 | `=_CreateIndex(C1, C2, B4, C5)` | shows `index:3f9a1c:000011` | | |
| 8 | `=_CreateIndex(D1, D2, B4, D5)` | shows `index:3f9a1c:000012` | | |

Text and four handles, the last of which may be left out. The name is text as typed, one cell, never trimmed or re-cased, and a label: two indices may share a name, and nothing looks an index up by it. The schedule is any handle, the form [inputs.md](../../seam/inputs.md) decision 40 gave `util_ReadHandle` and the calendar took in #104: the seam resolves it and hands over whatever object it finds, and the library says whether it is a schedule and of which kind. The conventions and the specifications are handles of one kind each, and a cell of another kind fails in the seam's words, `index_conventions is holiday calendar handle 'holiday_calendar:3f9a1c:000007', expected index conventions handle`, before the function runs; the specifications are required, since every index trades as at least one contract. The holiday calendar is the calendar's form, decision 39's, built in #103: left out with nothing in its place for an IFERC or a Gas Daily index, required for a futures one, and a blank cell in its place is a blank, refused by the seam. Empty text, a blank, a number and text naming no live object fail in the seam's words, each argument alone, left to right. The result is a handle: text in the cell that stands for the index the seam keeps, declared `Handle[Index]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Each successful call publishes a new index and a fresh handle, and earlier indices stand.

`=util_ReadHandle(A6)` shows what the index holds, one row under the two heading rows: the name, the kind, how many contracts the schedule has, how many contracts the specifications name, and whether a holiday calendar was given. The parts themselves read back through their own handles, and reading an index publishes nothing.

| name | kind | contracts | specifications | has_holiday_calendar |
|---|---|---|---|---|
| str | str | int64 | int64 | bool |
| Henry Hub NYMEX | futures | 12 | 2 | TRUE |

`=util_ReadHandle(A7)` on the IFERC index shows `Henry Hub IFERC`, `IFERC`, `3`, `1`, `FALSE`, and the Gas Daily one `Gas Daily` in the second column. The kind is spelled as every message spells it, `futures`, `IFERC` and `Gas Daily`.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the index behind one reference price, its name with its schedule, conventions, contract specifications and, for a futures index, holiday calendar, and shows its handle, the text other formulas take as the index. |
| `name` | The index's name as the desk calls it, such as Henry Hub NYMEX, kept as typed. |
| `schedule` | The index's schedule handle, futures, IFERC or Gas Daily: the cell showing its creator's result, such as B2, or a name for it. |
| `index_conventions` | The index-conventions handle: the cell showing _CreateIndexConventions's result, such as B4, or a name for it. |
| `contract_specifications` | The contract-specifications handle: the cell showing _CreateContractSpecifications's result, such as B5, or a name for it. |
| `[holiday_calendar]` | The market's holiday-calendar handle with a futures schedule: the cell showing _CreateHolidayCalendar's result, such as B3, or a name for it; left out for an IFERC or Gas Daily schedule. |

## The library checks

Two rules, in this order, the first failure being the message. Both are the calendar's rules of #104 in the calendar's words, moved here for the day the calendar takes the index; until that day they stand in both places.

| Rule | Message |
|---|---|
| the schedule is a futures, an IFERC or a Gas Daily schedule, its kind read off the object as the calendar reads it, and an object of another kind is refused naming what it is | `schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule` |
| a futures index brings its holiday calendar, since its market closes on days its schedule does not say, and an IFERC or a Gas Daily index leaves it out, since nothing of theirs closes a day | `holiday_calendar is missing, expected holiday calendar handle with a futures schedule`; `holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule` |

Nothing else is checked. The name is a label, kept as typed, neither unique nor looked up. Whether the schedule, the conventions and the specifications are one index's is the desk's to keep right, since nothing in any of them says which index it belongs to; the specifications' names are the contracts the index trades as, NYMEX NG and ICE NG, and neither their names nor their count answer to the schedule's codes or its count. The conventions' codes and the lot sizes' rules stay the tasks their own pages noted, and the calendar's rules on a schedule, its order and its count of contracts, stay the calendar's, so an index that builds says its parts are of the right kinds and nothing more. The four objects are kept by reference and unchanged, the record holds the kind, and nothing is copied, scanned or built: the index is the small record and no more. A failed call publishes nothing.

## Tests

The examples and the property below are `tests/unit/test_index.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, which reads the index back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. That a call costs its five arguments' checks, the kind's dispatch, the holiday rule and one publication, with no numpy call, no copy and no scan, that the record is the only thing allocated, and what reading one back costs, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The calendar's tests are unchanged; its kinds and naming helper move module and keep their tests.

| Case | Kind |
|---|---|
| the three samples: each index holding its schedule, conventions and specifications themselves, the kind read off the schedule, the futures index its holiday calendar and the other two none | example |
| a holiday calendar, a calendar, fixings, a history and a market where the schedule should be: refused naming what arrived | example |
| a futures schedule without a holiday calendar, and an IFERC or a Gas Daily schedule with one: refused in the calendar's words; the schedule checked before the holiday calendar | example |
| the name kept as typed, in any case, with spaces inside and around; two indices of one name, each its own object | example |
| specifications whose names and count differ from the schedule's codes and count, accepted, the counts read back as they are | example |
| the index keeps its four objects themselves, the record refuses writes, neither input changed, and a second index leaves the first as it was | example |
| for any of the three kinds of schedule, any name and any specifications: the kind is the schedule's, the objects are the ones given, the holiday calendar as the kind requires | property |
| five arguments in and each of the three indices read back as one row; each argument left out, blank, a number, empty text, text naming no live object, a creator's failure relayed or a handle of another kind, the seam's words, the index's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; reading an index publishes nothing; a dead index handle cannot be read | example, with handles |
| the spill: five headers, five types, one row, the two counts numbers, the name and the kind text and the holiday flag a boolean, for each of the three kinds | example |
| the creator's handle in a real workbook over the three schedules, each read back, a futures schedule without its holiday calendar and a Gas Daily schedule with one refused | Excel smoke |

## Not here

The calendar and the futures fixings take the index since #108, `_CreateCalendar(valuation_date, index)` and `_CreateFuturesFixings(date, settle, index)`, the calendar reading the kind the index holds and both reading the holiday calendar through it; the two rules above live here alone. The IFERC and Gas Daily fixings take theirs since #NN, and the [market history](../market/market-history.md) requires the calendar's index and the fixings' to be one object since #NN, so that every reader of a calendar and its fixings reads one index. The check of the conventions' codes against the unit tables and the price scale they imply: the [conventions](index-conventions.md) page's own task, now with a consumer in sight. Lot-size rules and the units of the fees: the [specifications](contract-specifications.md) page's. Whether the parts are one index's: the desk's, since a name is a label; there is no registry of indices, no lookup by name and no uniqueness. The discount curve: the valuation's, never the index's. Pricing and risk. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills the summary above, and each part spills as its own page shows.
