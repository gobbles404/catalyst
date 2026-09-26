# _CreateMarketHistory

Built in #84 over a futures calendar, in #105 over any calendar, and in #NN over one index, the calendar's and the fixings'.

The market history of one index: its calendar, kept as it is, bound to the price fixed on each period of it that has fixed, taken from the fixings of the calendar's market, one price for every such period and none for any other, built once from two objects the sheet already holds and reached by handle. The calendar determines the periods and the fixings supply the prices for them: creating the history never extends, shortens, reorders or regenerates the calendar, and a fixing never adds a row. It holds the side of the market that has already happened; the periods to come are priced by the [market](market.md), since #86, which keeps the history as it is. Since #84 it has read a futures calendar and futures fixings alone. From #105 it reads any calendar the [calendar](../calendar/calendar.md) makes and the fixings of that calendar's market: [futures fixings](../market-data/futures-fixings.md) with a futures calendar, one settle per business day; [Gas Daily fixings](../market-data/gas-daily-fixings.md) with a Gas Daily calendar, one midpoint per flow day; and [IFERC fixings](../market-data/iferc-fixings.md) with an IFERC calendar, one index per month. The fixings handle's kind says which arrived, as the calendar's index does for it. From #NN the two are checked to be one index's: every fixings creator keeps its index, the futures fixings since #108 and the IFERC and Gas Daily fixings from #NN, as the calendar does since #108, and the history requires the fixings' index to be the calendar's, the same object one `_CreateIndex` cell made, refusing any other, an index of another kind and another index of the same name alike. The pairing rule of #105, which read the two kinds, goes with it: a fixings kind is its index's kind, so one index means one kind. So does the closed-day rule of #84: the futures fixings are checked against the index's holiday calendar when they are made, the same calendar this calendar closes on, so no fixing over the calendar's index can fall on a day it closes. The record and the spill are one shape for the three, so that the market and the instruments read one history however the market fixes. The code is `src/goosedove/market/market_history.py`, the record and its builder, and `src/goosedove/excel/market.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMarketHistory(
    calendar: Handle[Calendar],
    fixings: Handle[object],
) -> Handle[MarketHistory]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | as_of | 26-May-2026 | contract_code | future_expiry |
| 2 | holiday | 25-May-2026 | m26 | 19-May-2026 |
| 3 | date | settle | n26 | 22-Jun-2026 |
| 4 | 20-May-2026 | 70.85 | q26 | 21-Jul-2026 |
| 5 | 21-May-2026 | 71.10 | | |
| 6 | 22-May-2026 | 71.25 | | |
| 7 | `=_CreateValuationDate(B1, 0.5)` | shows `valuation_date:3f9a1c:000001` | `=_CreateFuturesSchedule(C2:C4, D2:D4)` | shows `futures_schedule:3f9a1c:000004` |
| 8 | `=_CreateHolidayCalendar(B2)` | shows `holiday_calendar:3f9a1c:000007` | `=_CreateIndex("WTI NYMEX", C7, B15, B16, A8)` | shows `index:3f9a1c:000010`, B15 and B16 holding the conventions and the specifications |
| 9 | `=_CreateCalendar(A7, C8)` | shows `calendar:3f9a1c:000012` | `=_CreateFuturesFixings(A4:A6, B4:B6, C8)` | shows `futures_fixings:3f9a1c:000015` |
| 10 | `=_CreateMarketHistory(A9, C9)` | shows `market_history:3f9a1c:000019` | | |
| 11 | `=_CreateMarketHistory(B20, B21)` | shows `market_history:3f9a1c:000020`, B20 a Gas Daily calendar and B21 Gas Daily fixings, both over one index cell | | |
| 12 | `=_CreateMarketHistory(B30, B31)` | shows `market_history:3f9a1c:000021`, B30 an IFERC calendar and B31 IFERC fixings, both over one index cell | | |

Two handles, both required, neither with a default: the index's calendar and the fixings of its market, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. There is no valuation date to give: the calendar carries its own, and its fixed flag says which periods have fixed. There is no index to give either: the calendar and the fixings each carry theirs, and the history asks that they carry the same one. The calendar is declared `Handle[Calendar]`, one kind, and a cell that is not a calendar's handle fails in the seam's words, `calendar is futures fixings handle 'futures_fixings:3f9a1c:000015', expected calendar handle`, before the function runs. The fixings are declared `Handle[object]`, the form decision 40 gave `util_ReadHandle` and the index takes for its schedule: the seam resolves the handle and hands over whatever object it finds, naming no kind, and the library says whether it is fixings and whether it is over the calendar's index. The result is a handle: text in the cell that stands for the history the seam keeps, declared `Handle[MarketHistory]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the history: the calendar itself, and the row and the price of each fixed period.

`=util_ReadHandle(A10)` on the futures history above shows the calendar's four columns, every row the calendar has in its order, and a fifth, `fixing_price`; among its rows:

| date | contract | is_priced | is_fixed | fixing_price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 20-May-2026 | n26 | TRUE | TRUE | 70.85 |
| 21-May-2026 | n26 | TRUE | TRUE | 71.1 |
| 22-May-2026 | n26 | TRUE | TRUE | 71.25 |
| 23-May-2026 | n26 | FALSE | TRUE | closed |
| 24-May-2026 | n26 | FALSE | TRUE | closed |
| 25-May-2026 | n26 | FALSE | TRUE | closed |
| 26-May-2026 | n26 | TRUE | FALSE | unfixed |
| 27-May-2026 | n26 | TRUE | FALSE | unfixed |
| … | … | … | … | … |
| 21-Jul-2026 | q26 | TRUE | FALSE | unfixed |

`=util_ReadHandle(A11)` on a Gas Daily history, the calendar of the schedule page's three months valued on 25 September 2026 with the fixings of every flow day through the 25th, shows every flow day, the valuation day itself fixed and priced since its print preceded it:

| date | contract | is_priced | is_fixed | fixing_price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 1-Sep-2026 | U26 | TRUE | TRUE | 2.91 |
| … | … | … | … | … |
| 25-Sep-2026 | U26 | TRUE | TRUE | 2.88 |
| 26-Sep-2026 | U26 | TRUE | FALSE | unfixed |
| … | … | … | … | … |
| 30-Nov-2026 | X26 | TRUE | FALSE | unfixed |

`=util_ReadHandle(A12)` on an IFERC history, the calendar of the schedule page's three months valued on 15 November 2026 with the indices of the two months published by then, November's pasted first, shows one row per month, the indices in the calendar's order:

| date | contract | is_priced | is_fixed | fixing_price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 1-Oct-2026 | V26 | TRUE | TRUE | 1.85 |
| 2-Nov-2026 | X26 | TRUE | TRUE | 2.1 |
| 1-Dec-2026 | Z26 | TRUE | FALSE | unfixed |

The fifth column is a number, the price as the fixings hold it, zero and below included, on every period that is fixed and priced; on every other period it is a word, `closed` where the calendar does not price the day, a futures weekend or holiday, fixed or not, and `unfixed` where it prices but has not fixed, the days to come on a futures or a Gas Daily calendar and the months not yet published on an IFERC one. The words are display, not values: they say why the period has no price, no number stands for the absence of one, so a price of zero is a price, and no cell is blank. The row of types says `float64`, the type of what the column holds where it holds anything. The first four columns are the calendar's own, as [calendar.md](../calendar/calendar.md) shows them.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the market history of one index, its calendar with the price fixed on each period that has fixed, from the fixings of the calendar's market, and shows its handle, the text other formulas take as the history. |
| `calendar` | The index's calendar handle: the cell showing _CreateCalendar's result, such as B7, or a name for it. |
| `fixings` | The index's fixings handle, futures, IFERC or Gas Daily as the index is: the cell showing its creator's result, such as B10, or a name for it, made over the calendar's own index cell, with a price for every period of the calendar that has fixed. |

## The library checks

Two rules on what arrived, then two on the fixings against the calendar, in this order, the first failure being the message; they are the history's, not the fixings', so fixings whole under their own rules are still fixings. The calendar is not checked at all: it was checked when it was made, and nothing of it is made again. Each message names the earliest offending period, since the calendar's periods are in order and so are the fixings' dates, and an IFERC month is named by its code. The kind of the fixings is read off the object the seam hands over, and the index off the fixings and off the calendar, the two compared as objects: no text is parsed, and no name is looked up.

| Rule | Message |
|---|---|
| the fixings are fixings: futures, IFERC or Gas Daily | `fixings is a holiday calendar, expected futures, IFERC or Gas Daily fixings` |
| the fixings are over the calendar's index, the one object `_CreateIndex` made, which the calendar and the fixings both refer to; another index of the same name is another index, made by another cell, and fixings of another kind are over another index | `fixings is over another index, 'Henry Hub IFERC', expected the calendar's, 'Henry Hub NYMEX'` |

With a futures calendar, two of the three rules of #84, the argument named as it is now; the third, that no fixing falls on a day the calendar closes, has nothing left to catch, since the fixings were checked against the same holiday calendar when they were made:

| Rule | Message |
|---|---|
| every fixing is historical: none is dated on or after the valuation date's day, inside the calendar's days or outside them, whatever fraction of the day has elapsed | `fixings date 2026-05-26 is on or after valuation date 2026-05-26, expected dates before the valuation date` |
| every fixed and priced day of the calendar has a fixing dated exactly on it, the first and the last as much as the days between | `fixings has no fixing for 2026-05-22, expected a fixing for every fixed day in calendar` |

With a Gas Daily calendar, two rules, every flow day being priced:

| Rule | Message |
|---|---|
| every print is on the fixed side: no flow day after the valuation date's day, inside the calendar's days or outside them, since the calendar fixes a flow day once its print has preceded it and no later print exists yet | `fixings flow_date 2026-09-26 is after valuation date 2026-09-25, expected flow days on or before the valuation date` |
| every fixed day of the calendar has a print dated exactly on it | `fixings has no fixing for 2026-09-20, expected a fixing for every fixed day in calendar` |

With an IFERC calendar, two rules, every month being priced and every code a month of the index, since the fixings' creator refuses any other from #NN, so that an index lands on its month's row without a miss:

| Rule | Message |
|---|---|
| every index is for a fixed month, one whose publication day is before the valuation date's day | `fixings contract_code 'X26' is a month not yet fixed in calendar, expected an index for fixed months alone` |
| every fixed month of the calendar has an index | `fixings has no index for V26, expected an index for every fixed month in calendar` |

The calendar's days are consecutive and the fixings' dates increase, so on a futures or a Gas Daily calendar a fixing's row is its day count from the calendar's first day, one subtraction over the fixings' dates; a fixing before the calendar's first day or after its last is allowed and unused, so the fixings may run longer than the calendar on either side, and the ends of the two need not meet. On an IFERC calendar a month's row is found by its code, one pass over the fixings' codes against the calendar's, and there is no side to run past: every code is a month of the index, so of the calendar, which has one row per month of the index's schedule. A fixing on a period the calendar prices but has not fixed cannot reach the last rule, since the one before has already refused it. Nothing is sorted, filled in, carried forward, interpolated or substituted, and the calendar is neither shortened nor extended: a fixed period without a fixing is a row the desk did not paste, never a price to invent, as each fixings page already decided, and the period is named so the desk can paste it. Then the two columns are made, once: the rows of the fixings that fall in the calendar, and their prices copied out of the fixings' column, both frozen. The calendar is kept by reference, its periods, contracts and flags neither copied nor changed, and the fixings are left as they were, so many histories can share one calendar. A failed call publishes nothing.

Boundary cases the rules decide: a calendar entirely fixed needs a fixing on every priced period it has; a calendar with no fixed period, valued on or before its first day or, for futures, whose fixed days are all closed, is a history with no price, both handles still required and the fixings still on the fixed side, which for an IFERC calendar with no month published yet means no index at all, a column the sheet cannot paste, so that calendar has no history until its first index prints; futures weekends and holidays stay in the calendar without a price, as do the periods to come; futures fixings whole under their own calendar can still leave a day of this one uncovered, when the series stops short; a Gas Daily print for the valuation day itself is required, since the day is fixed; an IFERC index for the month published on the valuation day is refused, since that month is not fixed until the day after; and two indices made from one set of inputs, by two `_CreateIndex` cells or by one cell recalculated between the calendar and the fixings, are two indices, so the pairing is refused and the desk points both at one cell.

## Tests

The examples and properties below are `tests/unit/test_market_history.py`; the seam's texts and the handle are `tests/unit/test_market_creators.py`, which reads the history back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, for each of the three kinds, and that neither creating a history nor reading it back makes anything of the calendar again, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market's tests build histories of the three kinds through this creator and move with it; since #106 the market takes any of them.

| Case | Kind |
|---|---|
| the futures sample above: the three fixed business days priced, in the calendar's rows, and no other day; the rows the page shows, every row of the calendar standing | example |
| a single required fixing, alone and inside a longer series | example |
| a settle of zero and one below zero kept as prices | example |
| futures fixings before the calendar's first day, and after its last, allowed and unused, no row added and the ends unmatched | example |
| a futures fixing on the valuation date, inside the calendar's days or outside them, and fixings running past it, the earliest named; the fraction of the day admitting none | example |
| the first, the last, a day between and both ends without a futures fixing, the earliest named; a calendar entirely fixed with fixings for its first days alone; fixings entirely before the calendar | example |
| the valuation date checked before the missing days | example |
| for any futures fixings over the calendar's index, every fixing inside the calendar's days is on a day it prices, both having been checked against one holiday calendar: the closed-day rule of #84 has nothing to catch and is gone | property |
| a futures calendar entirely to come, and one whose fixed days are all closed: a history without a price | example |
| the Gas Daily sample: every flow day through the valuation day priced, the valuation day included, and the days after it not; prints beyond the calendar on either side allowed and unused | example |
| a print for the day after the valuation day, inside the calendar or beyond it, the earliest named; a fixed flow day without a print, the first, the last and one between, the earliest named; a Gas Daily calendar entirely to come, a history without a price | example |
| the IFERC sample: the two published months priced, in the calendar's order whatever order the indices came in, and the month to come not; a calendar of one month, published, and one with nothing published, whose empty fixings only the library can make | example |
| an index for the month published on the valuation day and for a later month, each refused naming the code; a fixed month without an index, named; the fixed months checked before the missing months | example |
| fixings over another index than the calendar's: of another kind, of the same kind and another name, and of the same kind and the same name, each refused naming the two indices; a calendar and fixings over one index accepted whatever its name; the index checked before the fixings' dates | example |
| a holiday calendar, a schedule, a calendar and a history where the fixings should be: refused naming what arrived, before any index is read | example |
| the index remade from unchanged inputs, as a recalculated `_CreateIndex` cell remakes it: the calendar over the old index with fixings over the new refused, naming one name twice; the calendar and the fixings both remade over the new index accepted, with the same prices as before | example, and through the seam |
| for any futures calendar of two to eight contracts, any holidays and any valuation date, with fixings over the same index on every business day from before its first day to the day before the valuation date: exactly the fixed business days priced, each with its own day's settle, and the calendar kept | property |
| for any Gas Daily calendar of one to eight months and any valuation date, with a print on every flow day from before its first day through the valuation day: exactly the fixed days priced, each with its own day's print | property |
| for any IFERC calendar of one to eight months and any valuation date, with an index for every month published before it: exactly the fixed months priced, each with its own index, in the calendar's order whatever order the fixings came in | property |
| the calendar kept itself and its columns untouched, the history's columns read-only and refusing writes and its prices not the fixings' storage; neither input changed, and a second history sharing the calendar with prices of its own | example |
| two handles in and each of the three histories read back period by period; every calendar row standing with the fifth cell following the flags; the price a number where fixed and text elsewhere, the calendar's kinds before it; a price of zero a number and an absent one a word; a calendar with no fixed period | example, through the seam |
| a fixing on the valuation date, a fixed day without one, a print after the valuation day, an index for an unfixed month, and fixings over another index, the library's words; each argument left out, blank, a number, text naming no live object, a creator's failure relayed, or a handle of another kind where the calendar should be, the seam's words, the history's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; two histories from one calendar each read their own prices; a dead history handle cannot be read | example, with handles |
| the spill: five headers, five types, a row of the calendar's kinds and a number where the period fixed, text where it did not, for each of the three kinds | example |
| the creator's handle read back in a real workbook, 34 days over a two-contract futures schedule with a price, `closed` and `unfixed` read, a Gas Daily history over the schedule page's three months and an IFERC history over its three, a price and `unfixed` read from each, the futures refusals, a Gas Daily print after the valuation day, and fixings over another index of the same name and IFERC fixings with a Gas Daily calendar, both refused naming the indices | Excel smoke |

## Not here

The market itself, the history combined with the current prices: [market.md](market.md), since #86 for futures and #106 for any history, which quotes each unfixed period by its contract and decides the order of the price vector, the balance of the month first on a Gas Daily calendar and the first unpublished month on an IFERC one. A revision to a published price: a new fixings object, never an edit. Finding the index by name: a name is a label, two indices may share one, and nothing here reads it but to say which two were given; the one `_CreateIndex` cell both refer to is the binding, and remaking that cell remakes the calendar and the fixings with it. Whether a futures date is a business day of the index's holiday calendar, and an IFERC code a month of the index: the fixings' own creators', the IFERC one from #NN. Whether a futures or a Gas Daily date falls within the index's schedule: nobody's, since a series may run past the calendar on either side, and the history binds the overlap under its valuation-date rules, which stand as they are. A fixing on a day the calendar closes: nothing to refuse once the two are one index's, so the rule of #84 that refused it is gone; a series whose holidays disagree with the calendar's is a series over another index, refused as such. An index for the month published on the valuation day: refused, since the calendar fixes that month the day after, and the valuation date's fraction is read by nothing yet. A price read by date or by month, the average over a period and the join of two markets by contract code, which is how an index swap settles: the instruments', along this history. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any history as the calendar's columns and the fixing price. Pricing and risk.
