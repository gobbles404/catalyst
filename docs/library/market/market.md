# _CreateMarket

Built in #86; prices every day of a monthly calendar since #88.

The market of one index: its history, the calendar bound to the fixing on each of its days that has fixed, together with the current futures prices, one quote per contract from the contract prompt on the valuation day through the schedule's last, so that every day still to fix has a price, the prompt contract's quote, beside every day that has fixed. On a daily calendar every business day has a price, the fixing where the day has fixed and the quote where it has not, and every other day is closed; on a monthly calendar, since #88, every day has a price, the expired contracts' days from the history and every day of a contract still live, past days, weekends and holidays alike, from the vector. It is what the pricing will take: the history prepared once, and combined with the prices as often as they move. Creating one is the hot operation, so it keeps the two objects as they are and finds one number, the schedule row of the valuation day's prompt contract; the daily view is made only when the handle is read. The code is `src/goosedove/market/market.py`, the record and its builder, and `src/goosedove/excel/market.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMarket(
    market_history: Handle[MarketHistory],
    price_vector: Handle[PriceVector],
) -> Handle[Market]: ...
```

| | A | B |
|---|---|---|
| 10 | the market history of [market-history.md](market-history.md), over the daily calendar valued on 26-May-2026 | `=_CreateMarketHistory(C8, A9)` shows `market_history:3f9a1c:000019` |
| 11 | 72.10 | |
| 12 | 72.80 | `=_CreatePriceVector(A11:A12)` shows `price_vector:3f9a1c:000021` |
| 13 | `=_CreateMarket(B10, B12)` | shows `market:3f9a1c:000022` |

Two handles, both required, neither with a default: the index's market history and the price vector, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. There is no valuation date, calendar, holiday calendar or layout to give: the history carries its calendar, and the calendar its valuation date. The function receives the two objects the seam keeps, never the text, and a cell that is not the right kind's handle fails in the seam's words, `market_history is price vector handle 'price_vector:3f9a1c:000021', expected market history handle`, before the function runs. The seam resolves the two handles and nothing else; nothing here restates that. The result is a handle: text in the cell that stands for the market the seam keeps, declared `Handle[Market]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Each successful call publishes a new market and a fresh handle, a call with unchanged inputs included; earlier markets keep their own price vector, and neither input is changed.

## The price vector's order

The first price is the quote of the contract prompt on the calendar's valuation day, and the prices after it are the quotes of every remaining contract in the expiry schedule's order, through its last: exactly one price per contract in that sequence.

- The contracts that expired before the valuation day are left out.
- The contract expiring on the valuation day is in: its expiry day is its own, as [calendar.md](../calendar/calendar.md) decided.
- The sequence is the schedule as supplied, nonconsecutive months included; no code is read or generated.
- A weekend or a holiday removes no contract: a contract whose remaining days are all closed still has its place.
- A price too many or too few is refused; nothing is cut, padded, repeated or filled in.

Which quote is which contract is the sheet's to keep right: the prices carry no labels, and a count that matches cannot say that the order is right or that the vector is this index's. The order is the same over a monthly calendar: the contracts expired before the valuation day are the history's and are not quoted, and every other contract, the one expiring on the valuation day first, is.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the market of one index from its history and current futures prices, the prompt contract's quote on each day still to fix, and shows its handle, the text other formulas take as the market. |
| `market_history` | The market-history handle: the cell showing _CreateMarketHistory's result, such as B10, or a name for it. |
| `price_vector` | The price-vector handle from _CreatePriceVector, such as B12, with prices in schedule order from the valuation day's prompt through the last contract. |

## The library checks

Two rules, in this order, the first failure being the message; they are the market's, not its inputs', which were checked when they were made and are not checked again.

| Rule | Message |
|---|---|
| the valuation date lies within the calendar's days, the first and the last included; a calendar that starts after it or ends before it is refused, never extended, and no earlier prompt contract is guessed | `market_history valuation date is 2026-05-19, expected a date from 2026-05-20 through 2026-07-21` |
| the vector holds exactly one price per contract from the valuation day's prompt through the schedule's last | `price_vector has 1 price, expected 2, one per contract from 'n26' through 'q26'` |

A count of one reads `1 price`. Nothing else is checked: no price bound, no look at the calendar's mode, which the history's reader reads, and no second look at the fixings' coverage, which the history settled. A failed call publishes nothing.

## The mapping

The calendar's days are consecutive, so the valuation day's row is its day count from the calendar's first day, one subtraction; the schedule row of the contract prompt on it is read from the calendar's prompt column there, and the number of quotes required is the schedule's contracts less that row. That row, `first_contract`, counted from zero, is the one number the market holds beside its two inputs: no search, no scan and no array made, whatever the calendar's mode. On a day still to fix, the price is the vector's entry at the day's prompt row less `first_contract`.

The price on a daily calendar, row by row of the calendar, every row kept in its order:

| Calendar row | Market price |
|---|---|
| a day the market is closed, past or not | none; shown as `closed` |
| a business day before the valuation date | the history's fixing |
| the valuation day, when the market is open | the quote of that day's prompt contract, whatever fraction of the day has elapsed, 1 included |
| a business day after the valuation date | the quote of that day's prompt contract |

And on a monthly calendar, where a contract's price falls on every day it is prompt:

| Calendar row | Market price |
|---|---|
| a day of a contract that expired before the valuation date, open or closed | the history's fixing, that contract's price |
| a day of a contract not yet expired, the one expiring on the valuation date included: past days, weekends and holidays alike | the quote of that day's prompt contract |

No day of a monthly market is closed: `is_business_day` is still shown and prices nothing, and the days of a live contract before the valuation date take its quote, since their price, the contract's, has not fixed. The live rows are found by the history's calendar and its mode, the business days from the valuation day on of a daily calendar, every day of a contract not yet expired of a monthly one, without inspecting the fixings. No interpolation, averaging, carrying forward or business-day adjustment happens, and a fixing stands even where its contract has a live quote too.

`=util_ReadHandle(A13)` on a market valued on 22 June 2026, n26's expiry day, with 19 June a holiday and the quotes `72.10` and `72.80`, shows among its rows:

| date | prompt_contract | is_business_day | is_past | price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 18-Jun-2026 | n26 | TRUE | TRUE | 71.6 |
| 19-Jun-2026 | n26 | FALSE | TRUE | closed |
| 20-Jun-2026 | n26 | FALSE | TRUE | closed |
| 21-Jun-2026 | n26 | FALSE | TRUE | closed |
| 22-Jun-2026 | n26 | TRUE | FALSE | 72.1 |
| 23-Jun-2026 | q26 | TRUE | FALSE | 72.8 |

The first four columns are the calendar's own, every row it has; the fifth, `price`, is a number on every business day and the word `closed` on every other, its row of types `float64`, as the market history's `fixing_price` column is shown, with no `unfixed` day left. The reader gathers the quotes for the live rows alone, since a past day's prompt contract may precede the first one quoted; the fixings and the quotes are written into their rows and the calendar's columns stand as they are.

`=util_ReadHandle(...)` on a market over the monthly history of [market-history.md](market-history.md), valued on 25 June 2026 with the 24th a holiday, n26 expired with its fixing 2.95 and the quotes `3.10` and `3.20` of q26 and u26, shows among its rows:

| date | prompt_contract | is_business_day | is_past | price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 20-Jun-2026 | n26 | FALSE | TRUE | 2.95 |
| 22-Jun-2026 | n26 | TRUE | TRUE | 2.95 |
| 23-Jun-2026 | q26 | TRUE | TRUE | 3.1 |
| 24-Jun-2026 | q26 | FALSE | TRUE | 3.1 |
| 25-Jun-2026 | q26 | TRUE | FALSE | 3.1 |
| 27-Jun-2026 | q26 | FALSE | FALSE | 3.1 |
| … | … | … | … | … |
| 22-Jul-2026 | u26 | TRUE | FALSE | 3.2 |

Every row is a number: n26's price on each of its days, the Saturday 20th included, q26's quote from the 23rd, the past 23rd and 24th and the Saturday 27th among them, and u26's from 22 July.

## Tests

The examples and the property below are `tests/unit/test_market.py`; the seam's texts and the handle are `tests/unit/test_market_creators.py`, which reads the market back through `util_ReadHandle`; the spill, its kinds and the price of every day for any calendar of either mode are `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. That creating a market costs the same whatever the calendar's length and the vector's, and what reading one back costs, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample: n26 the first contract quoted and two quotes required; valued on the calendar's first day, a Saturday, the holiday, n26's expiry day, the day after it and the calendar's last day: the prompt contract of that day first, and the count that follows; the fraction of the day changing nothing | example |
| valued on the calendar's last day, a holiday: the last contract's quote required though no open day remains; a contract whose days are a weekend alone, valued on its Saturday or Sunday: its place kept | example |
| codes that are labels, in the schedule's order; five contracts valued after the fourth expiry, one quote and four past contracts whose prompts precede it | example |
| valued the day before the calendar, the day after it or long before, the library's words, before the count is looked at; a quote too few, one too many, and two where one remains | example |
| for any history of two to eight contracts, any holidays and any valuation day of its calendar: the first contract is the valuation day's prompt, every business day from that day on has a quote in the vector, no day before it reads one, and one quote too many is refused | property |
| both objects kept themselves, no array made, the record refusing writes; neither input changed, two markets sharing one history, and a repeated call a new market | example |
| a monthly market over the sample history: n26 the history's, q26 and u26 quoted, two quotes required, the first contract read from the calendar as on a daily one | example |
| two handles in and the market read back day by day; the page's example, the expiring contract quoted on its expiry day and the next from the day after; valued on the first day, the last day and a Saturday; the price a number on every business day and text on every closed day; a zero, a negative and a repeated quote as given; two markets sharing a history | example, through the seam |
| a quote too few or too many and a history valued outside its calendar, the library's words; each argument left out, blank, a number, text naming no live object, a creator's failure relayed or a handle of another kind, the seam's words, the market's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; repeated calls publish fresh handles and the earlier ones stand; a dead market handle cannot be read | example, with handles |
| a monthly market read back day by day: the expired contract's price on each of its days, the quote on every day of the live contracts, the past 23rd and 24th and the Saturday 27th included, a number in every row | example, through the seam |
| the spill of a one-day market: the quote a number on the open day, `closed` as text when the day is a holiday, the quote still required; a monthly market over four days, the holiday included, a number on each, the fixing on the expired contract's days and the quote on the rest | example |
| for any daily history and the quotes it requires: every row of the calendar's spill stands, and the fifth cell is the fixing, the prompt contract's quote or `closed`, with no `unfixed` day; for any monthly history valued inside its calendar, every day its contract's fixing or quote and no day closed | property |
| the creator's handle read back in a real workbook, 34 days over a two-contract schedule with one quote, a fixing, `closed` and the quote read, and the three refusals; a monthly market of 156 rows over the six-contract schedule with four quotes, the expired contract's price on a Saturday and the quotes on a past day, the holiday, the valuation day, a Saturday and the day the next contract becomes prompt | Excel smoke |

## Not here

Pricing and risk, and the settle of a period: the work built on this. The averaging of a monthly contract's price over the days a trade covers and its weighting by delivery: the pricing's too, since here a contract's price falls on every one of its days alike. A feed subscription, the freshness of a quote, and a quote for the days already fixed: the vector is a snapshot as [price-vector.md](../market-data/price-vector.md) says, and a fixing stands. Whether the vector is this index's, in this order: nothing in it says so, and the sheet keeps the two together. A layout handle, a cache, the release of a handle, float32 storage and a typed transport for the prices: none of them here. Reading a settle by date or the average over a period: the pricing's, along this market. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any market as the calendar's columns and the price.
