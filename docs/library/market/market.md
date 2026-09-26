# _CreateMarket

Built in #86 over a futures history, and in #106 over any history; the vector's name checked since #112.

The market of one index: its history, the calendar bound to the price fixed on each period that has fixed, together with the quotes of the periods still to come, one quote per contract from the contract of the first period not yet fixed through the schedule's last, so that every priced period of the calendar has a price, the fixing where the period has fixed and its contract's quote where it has not, and every other period is closed. It is what the pricing will take: the history prepared once, and combined with the quotes as often as they move. Creating one is the hot operation, so it keeps the two objects as they are and finds one number, the schedule row of the first unfixed period's contract, that period's row being the calendar's own, held since it was made; the view by period is made only when the handle is read. Since #86 it has read a futures history alone, quoting each business day from the valuation day on by its prompt contract. From #106 it reads any history the [market history](market-history.md) makes, since #105 over any [calendar](../calendar/calendar.md), and the one rule serves the three markets: on a futures calendar the first unfixed period is the valuation day and its contract the prompt, as before; on a Gas Daily calendar it is the day after the valuation day, since the valuation day's print preceded it, so the first quote is the balance of the month the valuation day falls in and each later month's quote prices every day of that month; on an IFERC calendar it is the first month whose index has not published, the month publishing on the valuation day included. From #112 it first asks the vector whose it is: the [price vector](../market-data/price-vector.md) carries the name of the index it prices, ordinary text typed at its creator, and a vector named for another index is refused before anything is counted, since a count that matches cannot tell WTI's quotes from Brent's. The name is a label compared as text, so two indices of one name are not told apart; that much the sheet keeps right, as it keeps the order of the quotes. The code is `src/goosedove/market/market.py`, the record and its builder, and `src/goosedove/excel/market.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMarket(
    market_history: Handle[MarketHistory],
    price_vector: Handle[PriceVector],
) -> Handle[Market]: ...
```

| | A | B |
|---|---|---|
| 10 | the futures history of [market-history.md](market-history.md), valued on 26-May-2026 | `=_CreateMarketHistory(A9, C9)` shows `market_history:WTI NYMEX:19` |
| 11 | 72.10 | |
| 12 | 72.80 | `=_CreatePriceVector("WTI NYMEX", A11:A12)` shows `price_vector:WTI NYMEX:21`, named for the history's index |
| 13 | `=_CreateMarket(B10, B12)` | shows `market:WTI NYMEX:22` |
| 14 | `=_CreateMarket(B20, B24)` | shows `market:Henry Hub Gas Daily:23`, B20 the Gas Daily history of that page, valued on 25-Sep-2026, and B24 a vector named `Henry Hub Gas Daily` of three quotes, 2.95 for the balance of September, 3.10 for October and 3.40 for November |
| 15 | `=_CreateMarket(B30, B31)` | shows `market:Henry Hub IFERC:24`, B30 the IFERC history of that page, valued on 15-Nov-2026, and B31 a vector named `Henry Hub IFERC` of one quote, 2.20 for December |

Two handles, both required, neither with a default: the index's market history and the price vector, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. There is no valuation date, calendar, holiday calendar, kind, layout or index to give: the history carries its calendar, the calendar its valuation date, its kind and its index, and the vector the name of the index it was made for. The function receives the two objects the seam keeps, never the text, and a cell that is not the right kind's handle fails in the seam's words, `market_history is price vector handle 'price_vector:WTI NYMEX:21', expected market history handle`, before the function runs. The seam resolves the two handles and nothing else; nothing here restates that. The result is a handle: text in the cell that stands for the market the seam keeps, declared `Handle[Market]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Each successful call publishes a new market and a fresh handle, a call with unchanged inputs included; earlier markets keep their own price vector, and neither input is changed.

## The price vector's order

The first price is the quote of the contract of the first period not yet fixed, and the prices after it are the quotes of every remaining contract in the schedule's order, through its last: exactly one price per contract in that sequence. Which period is the first unfixed one is the calendar's `is_fixed` column, read and not decided here.

- The contracts whose periods have all fixed are left out: a futures contract expired before the valuation day, a Gas Daily month whose last day is on or before it, an IFERC month published before it.
- The futures contract expiring on the valuation day is in: its expiry day is its own, as [calendar.md](../calendar/calendar.md) decided. The IFERC month publishing on the valuation day is in: its index prints during the day. The Gas Daily month ending on the valuation day is out: its last print preceded the day, and no unfixed day of it remains, so there is no balance of it to quote.
- The first Gas Daily quote is the price of every day of its month after the valuation day, which is what a balance-of-month quote means when the valuation day falls inside a month, and the whole month's price when the calendar has not begun. The library does not know the difference and does not need to: a quote is the price of every unfixed period of its contract.
- The sequence is the schedule as supplied, nonconsecutive months included; no code is read or generated.
- A futures weekend or holiday removes no contract: a contract whose remaining days are all closed still has its place.
- A price too many or too few is refused; nothing is cut, padded, repeated or filled in.

Which quote is which contract is the sheet's to keep right: the prices carry no labels, and a count that matches cannot say that the order is right. That the vector is this index's is asked first, by the name the vector carries, and no further: two indices of one name pass. So is where a quote comes from the sheet's: a Gas Daily month's quote may be the IFERC forward for the month plus a basis, typed or computed in the price vector's cells, and the market does not ask, as it does not ask where a settle came from.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the market of one index from its history and the quotes of the periods still to come, and shows its handle, the text other formulas take as the market. |
| `market_history` | The market-history handle: the cell showing _CreateMarketHistory's result, such as B10, or a name for it. |
| `price_vector` | The price-vector handle from _CreatePriceVector, such as B12, named for this index, with one quote per contract in schedule order, from the first period not yet fixed through the last contract. |

## The library checks

Three rules, in this order, the first failure being the message; they are the market's, not its inputs', which were checked when they were made and are not checked again.

| Rule | Message |
|---|---|
| the vector names the history's index: its `index_name` is the name the index was created with, compared as text, spelling and case as typed, since a vector labelled for another index is another market's quotes whatever its length; two indices of one name are not told apart, a name being a label | `price_vector names index 'Brent', expected market_history's index 'WTI NYMEX'` |
| the history has a period not yet fixed, since a market is the history with the quotes of the periods to come, and a calendar fixed through its last period has nothing to quote; the sheet cannot hand over an empty vector, so such a history has no market | `market_history has no unfixed period, expected at least one to quote` |
| the vector holds exactly one price per contract from the first unfixed period's contract through the schedule's last | `price_vector has 1 price, expected 2, one per contract from 'n26' through 'q26'` |

A count of one reads `1 price`. The name check is one comparison of two texts, `wti nymex` and `WTI NYMEX ` being other names, and it holds for the three kinds alike; on the hot path it costs that comparison and nothing else. Nothing else is checked: no price bound, and no second look at the fixings' coverage, which the history settled. A failed call publishes nothing.

Two rules of #86 go with this build. The kind rule of #105, `market_history is over a Gas Daily calendar, expected a futures calendar`, since every history is a market's now. And the rule that the valuation date lie within the calendar's days, which existed to find the prompt contract by the valuation day's row: the first unfixed period needs no such row, so a futures calendar valued before its first day is a market from its first day on, every contract but the first quoted, as an IFERC or Gas Daily calendar valued before its first period is, and a day before the calendar is not a row, so an instrument that needs it says so in its own words. A calendar valued after its last period is refused by the first rule, as it was by the old one in other words.

## The mapping

The calendar's periods are in date order and the fixed ones come first, the fixed side being before the valuation date or, for a Gas Daily flow day, on or before it, so the row of the first unfixed period is the count of the fixed flags, which the calendar took once when it was made and holds as `first_unfixed`; the market reads that row, reads the schedule row of its contract from the calendar's contract column there, and requires the schedule's contracts less that row. That row, `first_contract`, counted from zero, is the one number the market holds beside its two inputs: two reads, no count, no search, no scan and no array made, however long the calendar. On an unfixed period the price is the vector's entry at the period's contract row less `first_contract`.

The price, row by row of the calendar, every row kept in its order:

| Calendar row | Market price |
|---|---|
| a period the calendar does not price, a futures weekend or holiday, fixed or not | none; shown as `closed` |
| a fixed and priced period | the history's fixing |
| an unfixed period | the quote of its contract, whatever fraction of the valuation day has elapsed, 1 included |

The unfixed periods are, on a futures calendar, the valuation day when the market is open and every business day after it; on a Gas Daily calendar, every day after the valuation day; on an IFERC calendar, every month whose publication day is on or after the valuation date. No interpolation, averaging, carrying forward or business-day adjustment happens, and a fixing stands even where its contract has a live quote too.

`=util_ReadHandle(A13)` on a futures market valued on 22 June 2026, n26's expiry day, with 19 June a holiday and the quotes `72.10` and `72.80`, shows among its rows:

| date | contract | is_priced | is_fixed | price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 18-Jun-2026 | n26 | TRUE | TRUE | 71.6 |
| 19-Jun-2026 | n26 | FALSE | TRUE | closed |
| 20-Jun-2026 | n26 | FALSE | TRUE | closed |
| 21-Jun-2026 | n26 | FALSE | TRUE | closed |
| 22-Jun-2026 | n26 | TRUE | FALSE | 72.1 |
| 23-Jun-2026 | q26 | TRUE | FALSE | 72.8 |

`=util_ReadHandle(A14)` on the Gas Daily market, valued on 25 September 2026 with the prints through the 25th and the quotes `2.95`, `3.10` and `3.40`, shows every flow day, the balance-of-month quote on the rest of September and each month's quote on its days:

| date | contract | is_priced | is_fixed | price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 25-Sep-2026 | U26 | TRUE | TRUE | 2.88 |
| 26-Sep-2026 | U26 | TRUE | FALSE | 2.95 |
| … | … | … | … | … |
| 30-Sep-2026 | U26 | TRUE | FALSE | 2.95 |
| 1-Oct-2026 | V26 | TRUE | FALSE | 3.1 |
| … | … | … | … | … |
| 30-Nov-2026 | X26 | TRUE | FALSE | 3.4 |

`=util_ReadHandle(A15)` on the IFERC market, valued on 15 November 2026 with the two published indices and the quote `2.20`, shows one row per month:

| date | contract | is_priced | is_fixed | price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 1-Oct-2026 | V26 | TRUE | TRUE | 1.85 |
| 2-Nov-2026 | X26 | TRUE | TRUE | 2.1 |
| 1-Dec-2026 | Z26 | TRUE | FALSE | 2.2 |

The first four columns are the calendar's own, every row it has; the fifth, `price`, is a number on every priced period and the word `closed` on every other, its row of types `float64`, as the market history's `fixing_price` column is shown, with no `unfixed` period left. The reader gathers the quotes for the unfixed periods alone, since a fixed period's contract may precede the first one quoted; the fixings and the quotes are written into their rows and the calendar's columns stand as they are.

## Tests

The examples and the properties below are `tests/unit/test_market.py`; the seam's texts and the handle are `tests/unit/test_market_creators.py`, which reads the market back through `util_ReadHandle`; the spill, its kinds and the price for any calendar are `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. That creating a market costs the same whatever the calendar's kind and length and the vector's, and what reading one back costs for each kind, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market history's tests are unchanged; [read-handle.md](../utilities/read-handle.md)'s market row moves with the words here.

| Case | Kind |
|---|---|
| the futures sample: n26 the first contract quoted and two quotes required; valued on the calendar's first day, a Saturday, the holiday, n26's expiry day, the day after it and the calendar's last day: the prompt contract of that day first, and the count that follows; the fraction of the day changing nothing | example |
| valued on the calendar's last day, a holiday: the last contract's quote required though no open day remains; a contract whose days are a weekend alone, valued on its Saturday or Sunday: its place kept | example |
| codes that are labels, in the schedule's order; five contracts valued after the fourth expiry, one quote and four past contracts whose prompts precede it | example |
| a futures calendar valued before its first day, and on its first contract's expiry day: a market from its first day on, every contract but the first quoted, and no row before the first day | example |
| the Gas Daily sample: the prints through the valuation day kept, the first quote on every later day of that month and each following month's quote on its days; valued on a month's last day, no quote for that month and the next month's first; valued before the first day, one quote per month, the first pricing the whole month; a calendar of one month | example |
| the IFERC sample: the published months keep their index, the month publishing on the valuation day and the months after take their quotes in the calendar's order; valued before the first month, one quote per month; valued on the first publication day, every month quoted | example |
| no unfixed period, the library's words before the count is looked at: a futures calendar valued after its last day, a Gas Daily calendar valued on or after its last flow day, an IFERC calendar valued after its last publication day; a quote too few, one too many, and two where one remains, on each kind | example |
| a vector named for another index, on each kind, refused naming both though the count matches; a name in another case, with a space, and empty of meaning; the name checked before the unfixed period and before the count; two indices of one name with a vector so named accepted, since the name is a label | example |
| for any futures history of two to eight contracts, any holidays and any valuation day from before its calendar to its last day: the first contract is the first unfixed day's prompt, every business day from that day on has a quote in the vector, no day before it reads one, and one quote too many is refused | property |
| for any Gas Daily history of one to eight months and for any IFERC history of one to eight months, valued on any day from before the calendar to its last period: every fixed period reads its fixing, every unfixed period its contract's quote, and the count required is the contracts from the first unfixed period's through the last | property |
| both objects kept themselves, no array made, the record refusing writes; neither input changed, two markets sharing one history, and a repeated call a new market | example |
| two handles in and each of the three markets read back period by period; the futures page's example, the expiring contract quoted on its expiry day and the next from the day after; valued on the first day, the last day and a Saturday; the price a number on every priced period and text on every closed day; a zero, a negative and a repeated quote as given; two markets sharing a history | example, through the seam |
| a quote too few or too many, a history with no unfixed period and a vector named for another index, the library's words, on each kind; each argument left out, blank, a number, text naming no live object, a creator's failure relayed or a handle of another kind, the seam's words, the market's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; repeated calls publish fresh handles and the earlier ones stand; a dead market handle cannot be read | example, with handles |
| the spill of a one-day futures market: the quote a number on the open day, `closed` as text when the day is a holiday, the quote still required; the spill of a one-month Gas Daily market and of a one-month IFERC market, fixed and not | example |
| for any history and the quotes it requires: every row of the calendar's spill stands, and the fifth cell is the fixing, the contract's quote or `closed`, with no `unfixed` period | property |
| the creator's handle read back in a real workbook, 34 days over a two-contract futures schedule with one quote, a fixing, `closed` and the quote read; a Gas Daily market over the schedule page's three months with a balance-of-month and two month quotes, and an IFERC market over its three with one quote, a fixing and a quote read from each; a quote too few, a history with no unfixed period, a vector named for another index and a futures history valued before its calendar, which builds | Excel smoke |

## Not here

A quote derived from another market, a Gas Daily month from the IFERC forward for the month and a basis: a formula in the price vector's cells today, and a creator of its own if the desk wants one, never a branch here. The average of a month's days, the settle of a period, pricing and risk: the instruments' work, built on this. A feed subscription, the freshness of a quote, and a quote for the periods already fixed: the vector is a snapshot as [price-vector.md](../market-data/price-vector.md) says, and a fixing stands. Whether the vector is this index's beyond its name: the name is a label compared as text, never a lookup and never the index object, so two indices of one name pass and a vendor column labelled wrongly passes; the order of the quotes is the sheet's, as before. A layout handle, a cache, the release of a handle, float32 storage and a typed transport for the prices: none of them here. Reading a price by date or by month: the instruments', along this market. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any market as the calendar's columns and the price.
