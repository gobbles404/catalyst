# _CreateMarketHistory

Built in #84; takes the fixings of either kind, daily or monthly as the calendar's mode says, since #88.

The market history of one index: its calendar, kept as it is, bound to the fixing on each of its days that has fixed, taken from the index's fixings of the kind the calendar's mode names. For a daily calendar that is the settle fixed on each past business day, from the daily fixings, one price for every such day and none for any other; for a monthly calendar it is the price supplied for each contract that has expired, from the monthly fixings, on every day that contract is prompt, weekends and holidays included, and nothing on the days of a contract still live. It is built once from two objects the sheet already holds and reached by handle. The calendar determines the dates and the fixings supply the prices for those dates: creating the history never extends, shortens, reorders or regenerates the calendar, and a fixing's date never adds a row. It is the first object that reads the market data against the calendar, and it holds the side of the market that has already fixed; the days still to fix, the valuation day among them, are priced by the [market](market.md), since #86, which keeps the history as it is. The code is `src/goosedove/market/market_history.py`, the record and its builder, and `src/goosedove/excel/market.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMarketHistory(
    calendar: Handle[Calendar],
    fixings: Handle[DailyFixings | MonthlyFixings],
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
| 8 | `=_CreateHolidayCalendar(B2)` | shows `holiday_calendar:3f9a1c:000007` | `=_CreateCalendar(A7, "daily", C7, A8)` | shows `calendar:3f9a1c:000012` |
| 9 | `=_CreateDailyFixings(A3:B3, A4:B6, A8)` | shows `daily_fixings:3f9a1c:000015` | `=_CreateMarketHistory(C8, A9)` | shows `market_history:3f9a1c:000019` |

Two handles, both required, neither with a default: the index's calendar and its fixings, daily or monthly, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say, the fixings a handle of one of two kinds, decision 42. There is no valuation date to give, since the calendar carries its own, and no mode: the calendar carries that too, and the fixings must be of the kind it names. The function receives the two objects the seam keeps, never the text, and a cell that is not a handle of the right kind fails in the seam's words, `calendar is daily fixings handle 'daily_fixings:3f9a1c:000015', expected calendar handle`, or for the fixings `fixings is calendar handle 'calendar:3f9a1c:000012', expected daily fixings or monthly fixings handle`, before the function runs. The seam resolves the two handles and nothing else, and nothing in it says which of the two kinds the fixings are: that is the library's first rule, below, and it is never inferred from what the fixings hold. The result is a handle: text in the cell that stands for the history the seam keeps, declared `Handle[MarketHistory]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the history: the calendar itself, and the row and the price of each day that has fixed.

`=util_ReadHandle(C9)` on the daily history above shows the calendar's four columns, every row the calendar has in its order, and a fifth, `fixing_price`; among its rows:

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

On a daily calendar the fifth column is a number, the settle as the fixings hold it, zero and below included, on every day that is past and a business day; on every other day it is a word, `closed` where the calendar has the market shut, a weekend or a holiday, past or not, and `unfixed` where it is open but not past, the valuation day and the days after it. The words are display, not values: they say why the day has no price, no number stands for the absence of one, so a settle of zero is a price, and no cell is blank. The row of types says `float64`, the type of what the column holds where it holds anything. The first four columns are the calendar's own, as [calendar.md](../calendar/calendar.md) shows them.

### A monthly calendar

The same function over a monthly calendar, with the index's monthly fixings, four contracts with the day each is published, valued on 25 June 2026 with the 24th a holiday:

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | as_of | 25-Jun-2026 | future_code | future_expiry | publication_date |
| 2 | holiday | 24-Jun-2026 | m26 | 19-May-2026 | 20-May-2026 |
| 3 | publication_date | price | n26 | 22-Jun-2026 | 23-Jun-2026 |
| 4 | 23-Jun-2026 | 2.95 | q26 | 21-Jul-2026 | 22-Jul-2026 |
| 5 | | | u26 | 20-Aug-2026 | 21-Aug-2026 |
| 6 | `=_CreateValuationDate(B1, 0.5)` | shows `valuation_date:3f9a1c:000031` | `=_CreateExpirySchedule(C2:C5, D2:D5, , E2:E5)` | shows `expiry_schedule:3f9a1c:000032` | |
| 7 | `=_CreateHolidayCalendar(B2)` | shows `holiday_calendar:3f9a1c:000033` | `=_CreateCalendar(A6, "monthly", C6, A7)` | shows `calendar:3f9a1c:000034` | |
| 8 | `=_CreateMonthlyFixings(A4, B4, C6)` | shows `monthly_fixings:3f9a1c:000035` | `=_CreateMarketHistory(C7, A8)` | shows `market_history:3f9a1c:000036` | |

Valued on the 25th, n26, expiring on the 22nd, has expired, and q26 and u26 have not; m26, the schedule's first contract, only bounds the calendar and is never prompt, so it needs no fixing. `=util_ReadHandle(C8)` shows, among its rows:

| date | prompt_contract | is_business_day | is_past | fixing_price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 20-Jun-2026 | n26 | FALSE | TRUE | 2.95 |
| 21-Jun-2026 | n26 | FALSE | TRUE | 2.95 |
| 22-Jun-2026 | n26 | TRUE | TRUE | 2.95 |
| 23-Jun-2026 | q26 | TRUE | TRUE | unfixed |
| 24-Jun-2026 | q26 | FALSE | TRUE | unfixed |
| 25-Jun-2026 | q26 | TRUE | FALSE | unfixed |
| 27-Jun-2026 | q26 | FALSE | FALSE | unfixed |
| … | … | … | … | … |
| 22-Jul-2026 | u26 | TRUE | FALSE | unfixed |

On a monthly calendar the fifth column is the contract's price on every day an expired contract is prompt, the Saturday and the Sunday before n26's expiry included, the number the fixings hold for it, provisional or published; and the word `unfixed` on every day of a contract still live, past or not, open or closed, since a monthly price falls on every day of its contract and a live contract's price is the market's quote, never history. No day of a monthly history is `closed`: whether the market is open on a day is still shown, in `is_business_day`, and changes nothing here.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the market history of one index, its calendar with the fixing on each day that has fixed, the settle of each past business day or the price of each expired contract, and shows its handle, the text other formulas take as the history. |
| `calendar` | The index's calendar handle: the cell showing _CreateCalendar's result, such as B7, or a name for it. |
| `fixings` | The index's fixings handle, daily or monthly as the calendar's mode says: the cell showing the result of _CreateDailyFixings or _CreateMonthlyFixings, such as B10, or a name for it. |

## The library checks

One rule first, whatever the calendar: the fixings are of the kind the calendar's mode names, daily fixings for a daily calendar and monthly fixings for a monthly one. The seam has established that they are one of the two kinds; which, and whether it is the calendar's, is decided here, once, and never inferred from the shape of the fixings, from whether the schedule has publication dates, or from what the prices look like.

| Rule | Message |
|---|---|
| a daily calendar takes daily fixings | `fixings is monthly fixings, expected daily fixings for a daily calendar` |
| a monthly calendar takes monthly fixings | `fixings is daily fixings, expected monthly fixings for a monthly calendar` |

Then the mode's own rules, in order, the first failure being the message; they are the history's, not the fixings', which were checked when they were made. Nothing else of the calendar is checked: it was checked when it was made, and nothing of it is made again. A failed call publishes nothing.

### A daily calendar

Three rules on the fixings against the calendar. Each message names the earliest offending date, since the calendar's days are in order and so are the fixings'.

| Rule | Message |
|---|---|
| every fixing is historical: none is dated on or after the valuation date's day, inside the calendar's days or outside them, whatever fraction of the day has elapsed | `fixings date 2026-05-26 is on or after valuation date 2026-05-26, expected dates before the valuation date` |
| every fixing inside the calendar's days is on a day the calendar has the market open, since a fixing on a day it closes means the two disagree about a holiday, and neither is guessed right | `fixings date 2026-05-25 is a non-business day in calendar, expected no fixing` |
| every past business day of the calendar, past and open both, has a fixing dated exactly on it, the first and the last as much as the days between | `fixings has no fixing for 2026-05-22, expected a fixing for every past business day in calendar` |

The calendar's days are consecutive and the fixings' dates increase, so a fixing's row is its day count from the calendar's first day, one subtraction over the fixings' dates; a fixing before the calendar's first day or after its last is allowed and unused, so the fixings may run longer than the calendar on either side, and the ends of the two need not meet. A fixing on a day the calendar has open but not past cannot reach the third rule, since the first has already refused it. Nothing is sorted, filled in, carried forward, interpolated or substituted, and the calendar is neither shortened nor extended: a past business day without a fixing is a row the desk did not paste, never a price to invent, as [daily-fixings.md](../market-data/daily-fixings.md) already decided, and the day is named so the desk can paste it. Then the two columns are made, once: the rows of the fixings that fall in the calendar, and their settles copied out of the fixings' column, both frozen. The calendar is kept by reference, its days, prompts and flags neither copied nor changed, and the fixings are left as they were, so many histories can share one calendar.

Boundary cases the rules decide: a calendar entirely before the valuation date needs a fixing on every business day it has; a calendar with no past business day, valued on or before its first day or whose past days are all closed, is a history with no price, both handles still required and the fixings still before the valuation date; weekends and holidays stay in the calendar without a price, as do the valuation day and the days after it; and daily fixings whole under their own calendar can still leave a day of this one uncovered, when the two calendars disagree about a holiday or the series stops short.

### A monthly calendar

A contract has expired when its future expires before the valuation date's day: the expiry day itself is live, whatever fraction of the day has elapsed, since [market.md](market.md) quotes the expiring contract on it. The expiries increase, so the expired contracts are the schedule's first rows; the first of them, the schedule's anchor, only bounds the calendar and is never prompt, so it needs no fixing. Each other expired contract needs the fixing dated its publication date, the day the schedule says its price is published, and takes that price on every day it is prompt. Three rules on the schedule and the fixings against it.

| Rule | Message |
|---|---|
| the schedule's publication dates are each one contract's, since a fixing keyed by date alone cannot tell two contracts apart; every contract sharing the date is named | `calendar publication date 2026-06-23 is 'n26' and 'q26', expected one contract per publication date` |
| no fixing is dated the publication date of a contract the calendar represents that has not expired, since a live contract's price is the market's quote and never history | `fixings date 2026-07-22 is 'q26', not expired on 2026-06-25, expected fixings of expired contracts only` |
| every expired contract but the anchor has a fixing dated its publication date; the first without one is named with the date to paste | `fixings has no fixing for 'n26' published 2026-06-23, expected a fixing for every expired contract in calendar` |

Nothing else is asked of the fixings. A fixing dated no contract's publication date, or the anchor's, is allowed and unused, so the fixings may run longer than the calendar's contracts on either side; the fixings are neither filtered by the valuation date nor clipped to the calendar's days, and a publication date may fall after the valuation date or after the calendar's last day, since it is the key a contract's price is found by, not a claim that the price has been published. Whether a price is provisional or published is not a fact of the fixings: a value supplied is a value. Then the rows are assigned, once: the calendar's prompt rows never decrease, so the days of the expired contracts are the calendar's first rows, found in one search over the prompts and listed in one `np.arange`, and each takes its contract's price through its prompt row, one gather over the prices, so a contract's days share one number. The calendar is kept by reference and the fixings are left as they were; the two columns are frozen.

Boundary cases the rules decide: valued before the calendar's first day, no contract has expired, nothing is required and nothing is priced, the anchor's fixing among what is allowed and unused; valued on the calendar's last day, the last contract is live, and every contract before it but the anchor requires its fixing; valued after the calendar's last day, every contract but the anchor has expired, requires its fixing, and every row is priced; a fixing of zero or below is a price; and an expired contract requires its fixing whether the calendar has the market open on any of its days or not.

#### The provisional roll

On n26's expiry day, 22 June, n26 is live: its days show `unfixed` in the history, the [market](market.md) quotes it, and the fixings may hold nothing of it. The day after, n26 has expired and its fixing is required, though the index publishes it later, on the 23rd in the sample or after: the desk supplies the value it has, a provisional settle keyed by n26's scheduled publication date, whatever that date is, `=_CreateMonthlyFixings(A4, B4, C6)` with A4 the 23rd and B4 the provisional value, and the history takes it as it takes any fixing. When the published price arrives the desk replaces the value, a new fixings object and a new history, and the earlier history stands as it was. The library generates no placeholder, tracks no publication status and tells a provisional value from a published one in no way: what to supply meanwhile is the desk's, and [monthly-fixings.md](../market-data/monthly-fixings.md) says the same of the fixings.

## Tests

The examples and properties below are `tests/unit/test_market_history.py`; the seam's texts and the handle are `tests/unit/test_market_creators.py`, which reads the history back through `util_ReadHandle`; the spill and the kinds it carries are `tests/unit/test_utilities.py`; the handle of one of two kinds is `tests/unit/test_handles.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs in either mode, and that neither creating a history nor reading it back makes anything of the calendar again, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the daily sample above: the three past business days priced, in the calendar's rows, and no other day; the rows the page shows, every row of the calendar standing | example |
| monthly fixings under a daily calendar and daily fixings under a monthly one: refused, naming the kind wanted, before any fixing is looked at; the same schedule with its publication dates serving a daily calendar as before | example, and through the seam |
| a single required fixing, alone and inside a longer series | example |
| a settle of zero and one below zero kept as prices | example |
| fixings before the calendar's first day, and after its last, allowed and unused, no row added and the ends unmatched | example |
| a fixing on the valuation date, inside the calendar's days or outside them, and fixings running past it, the earliest named; the fraction of the day admitting none | example |
| a fixing on a day the calendar closes while the fixings' own calendar is open, and two such days, the earliest named | example |
| the first, the last, a day between and both ends without a fixing, the earliest named; a calendar open on the holiday the fixings skip; a calendar entirely past with fixings for its first days alone; fixings entirely before the calendar | example |
| the valuation date checked before the closed days, and the closed days before the missing days | example |
| a calendar entirely to come, and one whose past days are all closed: a history without a price | example |
| for any daily calendar of two to eight contracts, any holidays and any valuation date, with fixings on every business day from before its first day to the day before the valuation date: exactly the past business days priced, each with its own day's settle, and the calendar kept | property |
| the monthly sample above: n26's price on each of its 34 days, the weekend included, and no other day priced; two expired contracts each priced on their own days | example |
| the expiring contract live on its expiry day, whatever the fraction, and expired the day after; a live contract's past days unfixed | example |
| a publication date after the valuation date, or after the calendar's last day, still keying its contract's fixing | example |
| an expired contract without its fixing named with its publication date; two contracts sharing a publication date named, and three | example |
| fixings of the anchor and of contracts beyond the calendar allowed and unused; a fixing of a live contract refused, naming it | example |
| the provisional roll: nothing required on the expiry day, a provisional value the day after, the published one replacing it in a new history and the earlier history standing | example, and through the seam |
| valued before the calendar, inside it and after its last day: nothing, the expired contracts, every contract but the anchor required | example |
| a monthly fixing of zero and one below zero kept as prices | example |
| for any monthly calendar of two to eight contracts published in the order they expire, any holidays and any valuation day from its first to the day after its last, with a fixing for every expired contract: exactly the days of the expired contracts priced, each with its contract's price, the anchor never among them | property |
| the calendar kept itself and its columns untouched in either mode, the history's columns read-only and refusing writes and its prices not the fixings' storage; neither input changed, and a second history sharing the calendar with prices of its own | example |
| two handles in and the history read back day by day; every calendar row standing with the fifth cell following the flags; the fixing price a number where fixed and text elsewhere, the calendar's kinds before it; a settle of zero a number and an absent one a word; a calendar with no past business day | example, through the seam |
| a fixing on the valuation date, on a holiday the calendar closes, a past business day without one and a calendar open on the holiday the fixings skip, the library's words; each argument left out, blank, a number, text naming no live object, a creator's failure relayed, or a handle of another kind, the seam's words naming both kinds of fixings, the history's own handle included | example, through the seam |
| a monthly history read back day by day: n26's price a number on each of its days, `unfixed` on every day after, the calendar's kinds before it; a fixing of a live contract, a missing fixing and two contracts sharing a publication date, the library's words; a failed monthly history publishing nothing | example, through the seam |
| a handle of either declared kind resolving to its object, a third kind refused naming both, every other failure in the seam's words, and what registration refuses around a handle of several kinds | example, in the seam's own tests |
| a failed construction publishes no object and no handle; two histories from one calendar each read their own prices; a dead history handle cannot be read | example, with handles |
| the spill: five headers, five types, a row of the calendar's kinds and a number where the day fixed, text where it did not; a monthly history and its market over four days, the holiday included, a number on each day of the expired contract and `unfixed` on the rest, no day closed; and for any monthly history valued inside its calendar, every day its contract's fixing or `unfixed` | example and property |
| the creator's handle read back in a real workbook, 34 days over a two-contract schedule, a price, `closed` and `unfixed` read, and the four refusals; a monthly history of 156 rows over the six-contract schedule with its publication dates, the price on a Saturday and on the expiry day, `unfixed` the day after, and the three refusals, the fixings of the wrong kind among them | Excel smoke |

## Not here

The market itself, the history combined with the current futures prices: [market.md](market.md), since #86, which quotes each day still to fix by its prompt contract and decides the order of the price vector, [price-vector.md](../market-data/price-vector.md), the column snapped as it stands since #85. A provisional price generated here, the status of a publication, whether provisional or final, and a revision to a published price: none of them; a value supplied is a value, and when a revision arrives it is a new fixings object, never an edit. The averaging of a contract's price over the days a trade covers, and its weighting by delivery: the pricing's. Whether the calendar and the fixings belong to the same index: nothing in either says which index it is, so nothing checks it; the desk pairs them, and [daily-fixings.md](../market-data/daily-fixings.md) parks the binding of fixings to an index definition. A settle read by date, and the average over a period, which is how a swap settles: the first pricing function's, along this history. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any history as the calendar's columns and the fixing price. Pricing and risk.
