# _CreateIndex

Built in #107; the specifications' lot units checked against the conventions since #115.

The index behind one reference price: its name, its schedule, the conventions its price is quoted in, the contract specifications it trades as and, for a futures index, the holiday calendar of its market, four objects the sheet already holds and a name, bound once and reached by handle. Henry Hub NYMEX, Henry Hub IFERC and Henry Hub Gas Daily are three indices, each with a schedule of its own kind, and the kind of the schedule is the kind of the index. Each object was checked when it was made, and since #115 the index reads one fact out of two of them: every lot unit of the specifications is a unit of the conventions' quantity type, a rule neither could hold alone. Nothing else in them is checked again; the index binds them so that what is downstream can refer to one thing. Its readers today: the [calendar](../calendar/calendar.md), since #108, reads its kind, its schedule and its holiday calendar in place of taking the two itself; the three fixings, the [futures fixings](../market-data/futures-fixings.md) since #108 and the [IFERC](../market-data/iferc-fixings.md) and [Gas Daily](../market-data/gas-daily-fixings.md) fixings since #109, each refuse an index of another kind and keep it, the futures fixings reading its holiday calendar and the IFERC fixings its months; the [market history](../market/market-history.md), since #109, requires its calendar's index and its fixings' to be one object; and the [market](../market/market.md), which counts its quotes against the index's schedule and, since #112, compares its price vector's name with the index's. Past the index's own rule below and the spills of [util_ReadHandle](../utilities/read-handle.md), nothing reads the conventions or the specifications yet: the instruments to come will read units, lots and fees through the market they price against, as the market reads its calendar. The code is `src/goosedove/index_definitions/index.py`, the record and its builder, `src/goosedove/index_definitions/kind.py`, the kinds and the holiday rules the index shares with the calendar and the fixings since #107, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

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
| 2 | schedule | `30512:futures_schedule:4`, twelve NG contract months | `30512:iferc_schedule:41`, the [IFERC schedule](iferc-schedule.md) page's three months | `30512:gas_daily_schedule:44`, the [Gas Daily schedule](gas-daily-schedule.md) page's three months |
| 3 | holiday calendar | `30512:holiday_calendar:7`, the exchange's closed days | | |
| 4 | conventions | `30512:index_conventions:8` | | |
| 5 | specifications | `30512:contract_specifications:9`, the [specifications](contract-specifications.md) page's three words for a quantity of gas, all in MMBTU | `30512:contract_specifications:46`, the ICE basis lot | `30512:contract_specifications:47`, the ICE swap lot |
| 6 | `=_CreateIndex(B1, B2, B4, B5, B3)` | shows `30512:index:Henry Hub NYMEX:10` | | |
| 7 | `=_CreateIndex(C1, C2, B4, C5)` | shows `30512:index:Henry Hub IFERC:11` | | |
| 8 | `=_CreateIndex(D1, D2, B4, D5)` | shows `30512:index:Henry Hub Gas Daily:12` | | |

Text and four handles, the last of which may be left out. The name is text as typed, one cell, never trimmed or re-cased, and a label: two indices may share a name, and nothing looks an index up by it; since #113 it shows in the handle of the index and of everything made over it, `30512:index:Henry Hub NYMEX:10`, as [handles.md](../../seam/handles.md#the-handles-text) says. The schedule is any handle, the form [inputs.md](../../seam/inputs.md) decision 40 gave `util_ReadHandle` and the calendar took in #104: the seam resolves it and hands over whatever object it finds, and the library says whether it is a schedule and of which kind. The conventions and the specifications are handles of one kind each, and a cell of another kind fails in the seam's words, `index_conventions is holiday calendar handle '30512:holiday_calendar:7', expected index conventions handle`, before the function runs; the specifications are required, since every index trades as at least one contract. The holiday calendar takes decision 39's form, built in #103 and the calendar's from #104 to #108: left out with nothing in its place for an IFERC or a Gas Daily index, required for a futures one, and a blank cell in its place is a blank, refused by the seam. Empty text, a blank, a number and text naming no live object fail in the seam's words, each argument alone, left to right. The result is a handle: text in the cell that stands for the index the seam keeps, declared `Handle[Index]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. A successful call publishes an index; a `_CreateIndex` call with the same arguments as a live one, in another cell or on a recalculation, shares that index and its handle rather than making another, and the index is released when Excel disconnects the last creator call that shares it, as [handles.md](../../seam/handles.md#publication-and-release) says.

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

Three rules, in this order, the first failure being the message. The first two are the calendar's rules of #104 in the calendar's words, the calendar having taken the index since #108; the third, since #115, is the one fact that lives across two of the definitions.

| Rule | Message |
|---|---|
| the schedule is a futures, an IFERC or a Gas Daily schedule, its kind read off the object as the calendar reads it, and an object of another kind is refused naming what it is | `schedule is a holiday calendar, expected a futures, IFERC or Gas Daily schedule` |
| a futures index brings its holiday calendar, since its market closes on days its schedule does not say, and an IFERC or a Gas Daily index leaves it out, since nothing of theirs closes a day | `holiday_calendar is missing, expected holiday calendar handle with a futures schedule`; `holiday_calendar is a holiday calendar, expected none with a Gas Daily schedule` |
| every lot unit of the specifications is a unit of the conventions' quantity type, because a trade's count of a word converts to the index's quantity through that unit, so barrels and gallons both stand under a volume index and an energy unit does not; the row, the unit and the units that would have done are named, in the tables' order | `specifications row 2 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3` |

Nothing else is checked. The name is a label, kept as typed, neither unique nor looked up. Whether the schedule, the conventions and the specifications are one index's is otherwise the desk's to keep right, since nothing in any of them says which index it belongs to; the specifications' names are the desk's words for a quantity of the index, `lots`, `ice_lots` and `mmbtu`, and neither their names nor their count answer to the schedule's codes or its count. What each part must hold alone was checked by its own creator and is not checked again: the conventions' codes since #110, the specifications' names, lot sizes, lot units and fees since #78, #110 and #115, each on its own page. The calendar's rules on a schedule, its order and its count of contracts, stay the [calendar](../calendar/calendar.md#the-library-checks)'s, so an index that builds says its parts are of the right kinds and its lots of its measure, and nothing more. The four objects are kept by reference and unchanged, and the record holds the kind; nothing is copied and nothing built but the small record, and the one pass is the third rule's, one lookup per row of the specifications in the conventions' measure, never a look at the schedule. A failed call publishes nothing.

## Tests

The examples and the property below are `tests/unit/test_index.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, which reads the index back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. That a call costs its five arguments' checks, the kind's dispatch, the holiday rule and one publication, with no numpy call, no copy and no look at the schedule whatever its length, the unit rule's lookup per row calling nothing the ledger counts, that the record is the only thing allocated, and what reading one back costs, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The kinds and the words that name them, in `kind.py` since #107, are exercised through the index's tests and the calendar's.

| Case | Kind |
|---|---|
| the three samples: each index holding its schedule, conventions and specifications themselves, the kind read off the schedule, the futures index its holiday calendar and the other two none | example |
| a holiday calendar, a calendar, fixings, a history and a market where the schedule should be: refused naming what arrived | example |
| a futures schedule without a holiday calendar, and an IFERC or a Gas Daily schedule with one: refused in the calendar's words; the schedule checked before the holiday calendar | example |
| the name kept as typed, in any case, with spaces inside and around; two indices of one name, each its own object | example |
| specifications whose names and count differ from the schedule's codes and count, accepted, the counts read back as they are | example |
| a barrel row and a gallon row under volume conventions, accepted; an MMBTU row under them, and a barrel row under energy conventions, refused naming the row, the unit and the units of the measure; the holiday rule before the unit rule | example, and through the seam |
| the index keeps its four objects themselves, the record refuses writes, neither input changed, and a second index leaves the first as it was | example |
| for any of the three kinds of schedule, any name and any specifications: the kind is the schedule's, the objects are the ones given, the holiday calendar as the kind requires | property |
| five arguments in and each of the three indices read back as one row; each argument left out, blank, a number, empty text, text naming no live object, a creator's failure relayed or a handle of another kind, the seam's words, the index's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; reading an index publishes nothing; a dead index handle cannot be read | example, with handles |
| the spill: five headers, five types, one row, the two counts numbers, the name and the kind text and the holiday flag a boolean, for each of the three kinds | example |
| the creator's handle in a real workbook over the three schedules, each read back; a futures schedule without its holiday calendar, a Gas Daily schedule with one, a holiday calendar where the schedule should be and specifications with an MMBTU lot under volume conventions refused in the library's words; the specifications left out and a blank name refused in the seam's | Excel smoke |

## Not here

The calendar and the futures fixings take the index since #108, `_CreateCalendar(valuation_date, index)` and `_CreateFuturesFixings(date, settle, index)`, the calendar reading the kind the index holds and both reading the holiday calendar through it; the two rules above live here alone. The IFERC and Gas Daily fixings take theirs since #109, and the [market history](../market/market-history.md) requires the calendar's index and the fixings' to be one object since #109, so that every reader of a calendar and its fixings reads one index. The conventions' codes are checked against the unit tables since #110, and the specifications' lot sizes and fees hold their rules since #110, each on its own page, [conventions](index-conventions.md) and [specifications](contract-specifications.md); the price scale the codes imply is the instrument's to look up, and the fees are costs per lot in the conventions' settlement currency, read off the index by the consumer that charges them. Whether the parts are one index's: the desk's, since a name is a label; there is no registry of indices, no lookup by name and no uniqueness. The discount curve: the valuation's, never the index's. Pricing and risk. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills the summary above, and each part spills as its own page shows.
