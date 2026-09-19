# _CreateMarketHistory

Built in #84.

The market history of one index: its calendar, kept as it is, bound to the settle fixed on each of its past business days, taken from the index's daily fixings, one price for every such day and none for any other, built once from two objects the sheet already holds and reached by handle. The calendar determines the dates and the fixings supply the prices for those dates: creating the history never extends, shortens, reorders or regenerates the calendar, and a fixing's date never adds a row. It is the first object that reads the market data against the calendar, and it holds the side of the market that has already happened; the days to come, the valuation day among them, wait for the market the pricing will take, which is not built. The code is `src/goosedove/market/market_history.py`, the record and its builder, and `src/goosedove/excel/market.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMarketHistory(
    calendar: Handle[Calendar],
    daily_fixings: Handle[DailyFixings],
) -> Handle[MarketHistory]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | as_of | 26-May-2026 | future_code | future_expiry |
| 2 | holiday | 25-May-2026 | m26 | 19-May-2026 |
| 3 | date | settle | n26 | 22-Jun-2026 |
| 4 | 20-May-2026 | 70.85 | q26 | 21-Jul-2026 |
| 5 | 21-May-2026 | 71.10 | | |
| 6 | 22-May-2026 | 71.25 | | |
| 7 | `=_CreateValuationDate(B1, 0.5)` | shows `valuation_date:3f9a1c:000001` | `=_CreateExpirySchedule(C2:C4, D2:D4)` | shows `expiry_schedule:3f9a1c:000004` |
| 8 | `=_CreateHolidayCalendar(B2)` | shows `holiday_calendar:3f9a1c:000007` | `=_CreateCalendar(A7, C7, A8)` | shows `calendar:3f9a1c:000012` |
| 9 | `=_CreateDailyFixings(A3:B3, A4:B6, A8)` | shows `daily_fixings:3f9a1c:000015` | `=_CreateMarketHistory(C8, A9)` | shows `market_history:3f9a1c:000019` |

Two handles, both required, neither with a default: the index's calendar and its daily fixings, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. There is no valuation date to give: the calendar carries its own, and its past flag says which days have fixed. The function receives the two objects the seam keeps, never the text, and a cell that is not the right kind's handle fails in the seam's words, `calendar is daily fixings handle 'daily_fixings:3f9a1c:000015', expected calendar handle`, before the function runs. The seam resolves the two handles and nothing else; nothing here restates that. The result is a handle: text in the cell that stands for the history the seam keeps, declared `Handle[MarketHistory]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the history: the calendar itself, and the row and the price of each past business day.

`=util_ReadHandle(D9)` on the history above shows the calendar's four columns, every row the calendar has in its order, and a fifth, `fixing_price`; among its rows:

| date | prompt_contract | is_business_day | is_past | fixing_price |
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

The fifth column is a number, the settle as the fixings hold it, zero and below included, on every day that is past and a business day; on every other day it is a word, `closed` where the calendar has the market shut, a weekend or a holiday, past or not, and `unfixed` where it is open but not past, the valuation day and the days after it. The words are display, not values: they say why the day has no price, no number stands for the absence of one, so a settle of zero is a price, and no cell is blank. The row of types says `float64`, the type of what the column holds where it holds anything. The first four columns are the calendar's own, as [calendar.md](../calendar/calendar.md) shows them.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the market history of one index, its calendar with the settle fixed on each past business day, and shows its handle, the text other formulas take as the history. |
| `calendar` | The index's calendar handle: the cell showing _CreateCalendar's result, such as B7, or a name for it. |
| `daily_fixings` | The index's daily-fixings handle: the cell showing the result of _CreateDailyFixings, such as B10, or a name for it, with a fixing on every past business day of the calendar. |

## The library checks

Three rules on the fixings against the calendar, in this order, the first failure being the message; they are the history's, not the fixings', so daily fixings whole under their own holiday calendar are still fixings. The calendar is not checked at all: it was checked when it was made, and nothing of it is made again. Each message names the earliest offending date, since the calendar's days are in order and so are the fixings'.

| Rule | Message |
|---|---|
| every fixing is historical: none is dated on or after the valuation date's day, inside the calendar's days or outside them, whatever fraction of the day has elapsed | `daily_fixings date 2026-05-26 is on or after valuation date 2026-05-26, expected dates before the valuation date` |
| every fixing inside the calendar's days is on a day the calendar has the market open, since a fixing on a day it closes means the two disagree about a holiday, and neither is guessed right | `daily_fixings date 2026-05-25 is a non-business day in calendar, expected no fixing` |
| every past business day of the calendar, past and open both, has a fixing dated exactly on it, the first and the last as much as the days between | `daily_fixings has no fixing for 2026-05-22, expected a fixing for every past business day in calendar` |

The calendar's days are consecutive and the fixings' dates increase, so a fixing's row is its day count from the calendar's first day, one subtraction over the fixings' dates; a fixing before the calendar's first day or after its last is allowed and unused, so the fixings may run longer than the calendar on either side, and the ends of the two need not meet. A fixing on a day the calendar has open but not past cannot reach the third rule, since the first has already refused it. Nothing is sorted, filled in, carried forward, interpolated or substituted, and the calendar is neither shortened nor extended: a past business day without a fixing is a row the desk did not paste, never a price to invent, as [daily-fixings.md](../market-data/daily-fixings.md) already decided, and the day is named so the desk can paste it. Then the two columns are made, once: the rows of the fixings that fall in the calendar, and their settles copied out of the fixings' column, both frozen. The calendar is kept by reference, its days, prompts and flags neither copied nor changed, and the fixings are left as they were, so many histories can share one calendar. A failed call publishes nothing.

Boundary cases the rules decide: a calendar entirely before the valuation date needs a fixing on every business day it has; a calendar with no past business day, valued on or before its first day or whose past days are all closed, is a history with no price, both handles still required and the fixings still before the valuation date; weekends and holidays stay in the calendar without a price, as do the valuation day and the days after it; and daily fixings whole under their own calendar can still leave a day of this one uncovered, when the two calendars disagree about a holiday or the series stops short.

## Tests

The examples and properties below are `tests/unit/test_market_history.py`; the seam's texts and the handle are `tests/unit/test_market.py`, which reads the history back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs, and that neither creating a history nor reading it back makes anything of the calendar again, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample above: the three past business days priced, in the calendar's rows, and no other day; the rows the page shows, every row of the calendar standing | example |
| a single required fixing, alone and inside a longer series | example |
| a settle of zero and one below zero kept as prices | example |
| fixings before the calendar's first day, and after its last, allowed and unused, no row added and the ends unmatched | example |
| a fixing on the valuation date, inside the calendar's days or outside them, and fixings running past it, the earliest named; the fraction of the day admitting none | example |
| a fixing on a day the calendar closes while the fixings' own calendar is open, and two such days, the earliest named | example |
| the first, the last, a day between and both ends without a fixing, the earliest named; a calendar open on the holiday the fixings skip; a calendar entirely past with fixings for its first days alone; fixings entirely before the calendar | example |
| the valuation date checked before the closed days, and the closed days before the missing days | example |
| a calendar entirely to come, and one whose past days are all closed: a history without a price | example |
| for any calendar of two to eight contracts, any holidays and any valuation date, with fixings on every business day from before its first day to the day before the valuation date: exactly the past business days priced, each with its own day's settle, and the calendar kept | property |
| the calendar kept itself and its columns untouched, the history's columns read-only and refusing writes and its prices not the fixings' storage; neither input changed, and a second history sharing the calendar with prices of its own | example |
| two handles in and the history read back day by day; every calendar row standing with the fifth cell following the flags; the fixing price a number where fixed and text elsewhere, the calendar's kinds before it; a settle of zero a number and an absent one a word; a calendar with no past business day | example, through the seam |
| a fixing on the valuation date, on a holiday the calendar closes, a past business day without one and a calendar open on the holiday the fixings skip, the library's words; each argument left out, blank, a number, text naming no live object, a creator's failure relayed, or a handle of another kind, the seam's words, the history's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; two histories from one calendar each read their own prices; a dead history handle cannot be read | example, with handles |
| the spill: five headers, five types, a row of the calendar's kinds and a number where the day fixed, text where it did not | example |
| the creator's handle read back in a real workbook, 34 days over a two-contract schedule, a price, `closed` and `unfixed` read, and the four refusals | Excel smoke |

## Not here

The market itself, the history combined with a price for each day to come, `_CreateMarket`: the next function. Live prices, the ordering of a price vector against the calendar, and what prices the valuation day and the days after it: the market's. Monthly fixings bound to the calendar, and a revision to a published settle: not built, and when a revision arrives it is a new fixings object, never an edit. Whether the calendar and the fixings belong to the same index: nothing in either says which index it is, so nothing checks it; the desk pairs them, and [daily-fixings.md](../market-data/daily-fixings.md) parks the binding of fixings to an index definition. A settle read by date, and the average over a period, which is how a swap settles: the first pricing function's, along this history. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any history as the calendar's columns and the fixing price. Pricing and risk.
