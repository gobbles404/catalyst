# _CreateMarket

Built in #86 over a futures history, and in #106 over any history; the vector's name checked since #112; a vector that stops before the schedule's last contract taken since #NN.

The market of one index: its history, the calendar bound to the price fixed on each period that has fixed, together with the quotes of the periods still to come, one quote per contract from the contract of the first period not yet fixed on, in the schedule's order, through the schedule's last contract or stopping before it, so that every priced period the quotes cover has a price, the fixing where the period has fixed and its contract's quote where it has not, and every other period of those is closed. It is what the pricing will take: the history prepared once, and combined with the quotes as often as they move. Creating one is the hot operation, so it keeps the two objects as they are and finds one number, the schedule row of the first unfixed period's contract, that period's row being the calendar's own, held since it was made; the view by period is made only when the handle is read. Since #86 it has read a futures history alone, quoting each business day from the valuation day on by its prompt contract. From #106 it reads any history the [market history](market-history.md) makes, since #105 over any [calendar](../calendar/calendar.md), and the one rule serves the three markets: on a futures calendar the first unfixed period is the valuation day and its contract the prompt, as before; on a Gas Daily calendar it is the day after the valuation day, since the valuation day's print preceded it, so the first quote is the balance of the month the valuation day falls in and each later month's quote prices every day of that month; on an IFERC calendar it is the first month whose index has not published, the month publishing on the valuation day included. From #112 it first asks the vector whose it is: the [price vector](../market-data/price-vector.md) carries the name of the index it prices, ordinary text typed at its creator, and a vector named for another index is refused before anything is counted, since a count that matches cannot tell WTI's quotes from Brent's. The name is a label compared as text, so two indices of one name are not told apart; that much the sheet keeps right, as it keeps the order of the quotes. From #NN the vector may stop before the schedule does, so that a schedule can run years past the quotes the desk has: the market's live prices cover the contracts from the first required one, the contract of the first period not yet fixed, through the last one quoted, the readback ends there, and a contract past it is refused by name, never priced from another contract's quote. The code is `src/goosedove/market/market.py`, the record and its builder, and `src/goosedove/excel/market.py`, the worksheet function.

## Worksheet contract

```python
def _CreateMarket(
    market_history: Handle[MarketHistory],
    price_vector: Handle[PriceVector],
) -> Handle[Market]: ...
```

| | A | B |
|---|---|---|
| 10 | the futures history of [market-history.md](market-history.md), valued on 26-May-2026 | `=_CreateMarketHistory(A9, C9)` shows `30512:market_history:WTI NYMEX:19` |
| 11 | 72.10 | |
| 12 | 72.80 | `=_CreatePriceVector("WTI NYMEX", A11:A12)` shows `30512:price_vector:WTI NYMEX:21`, named for the history's index |
| 13 | `=_CreateMarket(B10, B12)` | shows `30512:market:WTI NYMEX:22` |
| 14 | `=_CreateMarket(B20, B24)` | shows `30512:market:Henry Hub Gas Daily:23`, B20 the Gas Daily history of that page, valued on 25-Sep-2026, and B24 a vector named `Henry Hub Gas Daily` of three quotes, 2.95 for the balance of September, 3.10 for October and 3.40 for November |
| 15 | `=_CreateMarket(B30, B31)` | shows `30512:market:Henry Hub IFERC:24`, B30 the IFERC history of that page, valued on 15-Nov-2026, and B31 a vector named `Henry Hub IFERC` of one quote, 2.20 for December |
| 16 | `=_CreateMarket(B10, B40)` | shows `30512:market:WTI NYMEX:26`, B40 a vector named `WTI NYMEX` of one quote, 72.10, n26's alone: a market whose quotes stop before the schedule's last contract, q26 |

Two handles, both required, neither with a default: the index's market history and the price vector, each the cell showing its creator's result or a defined name referring to it, as [inputs.md](../../seam/inputs.md) decisions 34 to 37 say. There is no valuation date, calendar, holiday calendar, kind, layout or index to give: the history carries its calendar, the calendar its valuation date, its kind and its index, and the vector the name of the index it was made for. The function receives the two objects the seam keeps, never the text, and a cell that is not the right kind's handle fails in the seam's words, `market_history is price vector handle '30512:price_vector:WTI NYMEX:21', expected market history handle`, before the function runs. The seam resolves the two handles and nothing else; nothing here restates that. The result is a handle: text in the cell that stands for the market the seam keeps, declared `Handle[Market]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. A successful call publishes a market, and neither input is changed. A recalculation with unchanged inputs, or a second cell with the same arguments, shares the live market and its handle; a new vector makes a new market, and the old one is released when Excel disconnects its last creator, as [handles.md](../../seam/handles.md#publication-and-release) says. A market holds its vector by reference, the snapshot it was made with, however the vector's cell moves on.

## The price vector's order

The first price is the quote of the contract of the first period not yet fixed, and the prices after it are the quotes of the contracts that follow it in the schedule's order, none skipped: at least one price, and at most one per contract through the schedule's last. Which period is the first unfixed one is the calendar's `is_fixed` column, read and not decided here.

- The contracts whose periods have all fixed are left out: a futures contract expired before the valuation day, a Gas Daily month whose last day is on or before it, an IFERC month published before it.
- The futures contract expiring on the valuation day is in: its expiry day is its own, as [calendar.md](../calendar/calendar.md) decided. The IFERC month publishing on the valuation day is in: its index prints during the day. The Gas Daily month ending on the valuation day is out: its last print preceded the day, and no unfixed day of it remains, so there is no balance of it to quote.
- The first Gas Daily quote is the price of every day of its month after the valuation day, which is what a balance-of-month quote means when the valuation day falls inside a month, and the whole month's price when the calendar has not begun. The library does not know the difference and does not need to: a quote is the price of every unfixed period of its contract.
- The sequence is the schedule as supplied, nonconsecutive months included; no code is read or generated.
- A futures weekend or holiday removes no contract: a contract whose remaining days are all closed still has its place, the last one quoted included.
- The vector may stop at any contract. A schedule from F23 through Z30, with Z26 the first required contract, takes quotes for Z26 through Z28, twenty-five of them, or for all forty-nine through Z30. No price at all is refused, since a history alone is not a market, and so is a price past the schedule's last contract; nothing is cut, padded, repeated or filled in.

Which quote is which contract is the sheet's to keep right: the prices carry no labels, and a count that matches cannot say that the order is right. That the vector is this index's is asked first, by the name the vector carries, and no further: two indices of one name pass. So is where a quote comes from the sheet's: a Gas Daily month's quote may be the IFERC forward for the month plus a basis, typed or computed in the price vector's cells, and the market does not ask, as it does not ask where a settle came from.

### When the first contract rolls

The vector carries prices and no contract code, so the market reads its first price as the first required contract's, whatever the desk meant by it. When that contract's last period fixes and the next contract becomes the first required, the sheet must move the vector on by dropping the old first price. A vector left as it was is still taken, and each price is read against the contract after the one it was quoted for:

| State | First required contract | Unchanged vector | How the library reads it |
|---|---|---|---|
| before the roll | Z26 | 70, 71 | Z26 = 70, F27 = 71 |
| after the roll | F27 | 70, 71 | F27 = 70, G27 = 71 |

If 70 and 71 are still the quotes of Z26 and F27, the second reading is wrong, and nothing here can tell, there being no label to compare. Until #NN the count caught this one case by accident: a vector had to reach the schedule's end, so one left unchanged was a price too many after a roll. A vector that reaches the end still fails that way; one that stops before it does not. That is the price of letting the schedule run past the quotes, accepted with it: keeping the first price on the first required contract is the sheet's to do, as the order of the quotes is. A contract code carried by the vector, and the checks it would allow, are deferred.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the market of one index from its history and the quotes of the periods still to come, and shows its handle, the text other formulas take as the market. |
| `market_history` | The market-history handle: the cell showing _CreateMarketHistory's result, such as B10, or a name for it. |
| `price_vector` | The price-vector handle from _CreatePriceVector, such as B12, named for this index, with one quote per contract in schedule order, starting at the first period not yet fixed and stopping at or before the last contract. |

## The library checks

Three rules, in this order, the first failure being the message; they are the market's, not its inputs', which were checked when they were made and are not checked again.

| Rule | Message |
|---|---|
| the vector names the history's index: its `index_name` is the name the index was created with, compared as text, spelling and case as typed, since a vector labelled for another index is another market's quotes whatever its length; two indices of one name are not told apart, a name being a label | `price_vector names index 'Brent', expected market_history's index 'WTI NYMEX'` |
| the history has a period not yet fixed, since a market is the history with the quotes of the periods to come, and a calendar fixed through its last period has nothing to quote; the sheet cannot hand over an empty vector, so such a history has no market | `market_history has no unfixed period, expected at least one to quote` |
| the vector holds at least one price, and at most one per contract from the first unfixed period's contract through the schedule's last | `price_vector has 26 prices, expected at most 25, one per contract from 'Z26' through 'Z28'`, or `price_vector has 0 prices, expected at least 1, one per contract from 'Z26' through 'Z28'` |

The count is two comparisons of numbers already held, and `through` names the schedule's last contract whatever the count: it says how far the vector may go, not how far it went. The sheet cannot hand over an empty vector, the seam refusing an empty column where the vector is created, so the lower bound answers a Python caller; it stays because a market is a history with at least one live price, and a vector of none would have no coverage to name. The name check is one comparison of two texts, `wti nymex` and `WTI NYMEX ` being other names, and it holds for the three kinds alike; on the hot path it costs that comparison and nothing else. Nothing else is checked: no price bound, and no second look at the fixings' coverage, which the history settled. A failed call publishes nothing.

Two rules of #86 went in #106. The kind rule of #105, `market_history is over a Gas Daily calendar, expected a futures calendar`, since every history is a market's now. And the rule that the valuation date lie within the calendar's days, which existed to find the prompt contract by the valuation day's row: the first unfixed period needs no such row, so a futures calendar valued before its first day is a market from its first day on, the quotes starting at the contract after the first, as an IFERC or Gas Daily calendar valued before its first period is, and a day before the calendar is not a row, so an instrument that needs it says so in its own words. A calendar valued after its last period is refused by the first rule, as it was by the old one in other words.

## Live-price coverage

The quotes cover the contracts from the first required one through the last one quoted: `first_contract` through `last_contract`, which is `first_contract` plus the vector's length, less one, read off the vector and not held. Inside the coverage every unfixed period reads its contract's quote. Outside it there is no live price, and none is made up: the last quote is not carried forward, and no other contract's quote stands in.

One reader hands out live prices, `Market.live_prices` in `src/goosedove/market/market.py`, a method for the library's own readers and not a worksheet function. Given the schedule rows of the contracts wanted, as the calendar's contract column holds them, it returns their quotes in the order asked, or refuses the first contract outside the coverage by name:

| Asked for | Message |
|---|---|
| a contract after the last one quoted | `requested contract 'F29' is beyond live-price coverage ending at 'Z28'` |
| a contract before the first one quoted | `requested contract 'X26' is before live-price coverage starting at 'Z26'` |

The second matters as much as the first: a row before the vector would otherwise count back from the vector's end and return another contract's quote with no failure at all. The words say live-price coverage because a contract before it may be priced in full by the history's fixings; the market does not lack its history. The readback below is the one reader today, and every reader to come, the period average first, takes its live prices through this method, so the rule is one rule. It answers by contract and for live prices only: which price a date takes, a fixing or a quote, is the instruments' question, as it was.

## The mapping

The calendar's periods are in date order and the fixed ones come first, the fixed side being before the valuation date or, for a Gas Daily flow day, on or before it, so the row of the first unfixed period is the count of the fixed flags, which the calendar took once when it was made and holds as `first_unfixed`; the market reads that row, reads the schedule row of its contract from the calendar's contract column there, and takes at most the schedule's contracts less that row. That row, `first_contract`, counted from zero, is the one number the market holds beside its two inputs: two reads, no count, no search, no scan and no array made, however long the calendar. On an unfixed period of a contract the quotes cover, the price is the vector's entry at the period's contract row less `first_contract`.

The price, row by row of the calendar, every row through the last period of the last contract quoted, in its order:

| Calendar row | Market price |
|---|---|
| a period the calendar does not price, a futures weekend or holiday, fixed or not | none; shown as `closed` |
| a fixed and priced period | the history's fixing |
| an unfixed period of a contract the quotes cover | the quote of its contract, whatever fraction of the valuation day has elapsed, 1 included |
| a period after the last contract quoted | no price, and no row in the readback; a reader that asks for its contract is refused |

The unfixed periods are, on a futures calendar, the valuation day when the market is open and every business day after it; on a Gas Daily calendar, every day after the valuation day; on an IFERC calendar, every month whose publication day is on or after the valuation date; each as far as the last contract quoted. No interpolation, averaging, carrying forward or business-day adjustment happens, and a fixing stands even where its contract has a live quote too.

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

The first four columns are the calendar's own, every row it has through the last period of the last contract quoted; the fifth, `price`, is a number on every priced period and the word `closed` on every other, its row of types `float64`, as the market history's `fixing_price` column is shown, with no `unfixed` period left. The reader gathers the quotes for the unfixed periods alone, since a fixed period's contract may precede the first one quoted; the fixings and the quotes are written into their rows and the calendar's columns stand as they are.

A vector that stops before the schedule does ends the readback with it. `=util_ReadHandle(A16)` on the futures market of one quote, n26's, valued on 26 May 2026 with the 25th a holiday, shows the history and every day through n26's expiry, 22 June, 34 days under the two heading rows, and no day of q26's:

| date | contract | is_priced | is_fixed | price |
|---|---|---|---|---|
| datetime64[D] | str | bool | bool | float64 |
| 20-May-2026 | n26 | TRUE | TRUE | 70.85 |
| … | … | … | … | … |
| 25-May-2026 | n26 | FALSE | TRUE | closed |
| 26-May-2026 | n26 | TRUE | FALSE | 72.1 |
| … | … | … | … | … |
| 22-Jun-2026 | n26 | TRUE | FALSE | 72.1 |

The last row is the last period of the last contract quoted: its expiry day on a futures calendar, the last day of its month on a Gas Daily one, its own row on an IFERC one. The history is always whole, since every fixed period comes before the first unfixed one, which the quotes always cover. The last contract quoted keeps all its rows, open or closed: one whose remaining days are a weekend or holidays alone still holds its place in the vector and its days in the readback. The reader finds the last row by one search down the calendar's contract column, which never decreases, and cuts the calendar's columns there before the table is made, each cut a view of the calendar's own column, and it takes the schedule's codes no further than the last contract quoted, so it builds the rows it shows and no others, however long the calendar and the schedule run on; a vector that reaches the schedule's end takes the same path and shows every row. The calendar is not changed, and reads in full through its own handle.

## Tests

The examples and the properties below are `tests/unit/test_market.py`; the seam's texts and the handle are `tests/unit/test_market_creators.py`, which reads the market back through `util_ReadHandle`; the spill, its kinds and the price for any calendar are `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. That creating a market costs the same whatever the calendar's kind and length and the vector's, whether the vector reaches the schedule's end or stops before it, and what reading one back costs for each kind, the rows its quotes cover and no others, is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`. The market history's tests are unchanged; [read-handle.md](../utilities/read-handle.md)'s market row moves with the words here.

| Case | Kind |
|---|---|
| the futures sample: n26 the first contract quoted and up to two quotes taken; valued on the calendar's first day, a Saturday, the holiday, n26's expiry day, the day after it and the calendar's last day: the prompt contract of that day first, and the count that follows; the fraction of the day changing nothing | example |
| valued on the calendar's last day, a holiday: the last contract's quote required though no open day remains; a contract whose days are a weekend alone, valued on its Saturday or Sunday: its place kept | example |
| codes that are labels, in the schedule's order; five contracts valued after the fourth expiry, one quote and four past contracts whose prompts precede it | example |
| a futures calendar valued before its first day, and on its first contract's expiry day: a market from its first day on, the quotes starting at the contract after the first, and no row before the first day | example |
| the Gas Daily sample: the prints through the valuation day kept, the first quote on every later day of that month and each following month's quote on its days; valued on a month's last day, no quote for that month and the next month's first; valued before the first day, one quote per month, the first pricing the whole month; a calendar of one month | example |
| the IFERC sample: the published months keep their index, the month publishing on the valuation day and the months after take their quotes in the calendar's order; valued before the first month, one quote per month; valued on the first publication day, every month quoted | example |
| no unfixed period, the library's words before the count is looked at: a futures calendar valued after its last day, a Gas Daily calendar valued on or after its last flow day, an IFERC calendar valued after its last publication day; no quote at all, one past the schedule's last contract, and two where one remains, on each kind | example |
| a vector named for another index, on each kind, refused naming both though the count matches; a name in another case, with a space, and empty of meaning; the name checked before the unfixed period and before the count, with a count that fits, one too many and none; two indices of one name with a vector so named accepted, since the name is a label | example |
| a vector of every length from the first required contract's quote alone to one per remaining contract, on each kind: the first contract the calendar's whatever the length, the coverage ending that many contracts on, and one price more refused; a schedule from F23 through Z30 with Z26 first required, taking prices through Z28 and through Z30 and refusing a fiftieth, and one ending at Z28 refusing a twenty-sixth | example |
| live prices by contract: the quotes of the contracts asked for, in the order asked, a contract asked twice answered twice; a contract after the last quoted and one before the first refused by name, the first asked for outside the coverage being the one named, on each kind and for a vector that reaches the schedule's end | example |
| a last covered contract with no open day left, a weekend alone or two holidays alone: its place in the vector kept, the coverage ending with it, its quote there to be read and the contract after it refused | example |
| a roll: a vector moved on with the calendar starts at the new first contract and ends one contract later; a vector left unchanged is taken and read one contract later, the limitation above; a vector that reached the schedule's end is one price too many | example |
| for any history of any kind and any count of quotes from one to the contracts that remain: the market is made, its first contract is the calendar's, every unfixed period of a covered contract reads its quote, and the first period past the coverage is refused | property |
| for any futures history of two to eight contracts, any holidays and any valuation day from before its calendar to its last day: the first contract is the first unfixed day's prompt, every business day from that day on has a quote in the vector, no day before it reads one, and one quote too many is refused | property |
| for any Gas Daily history of one to eight months and for any IFERC history of one to eight months, valued on any day from before the calendar to its last period: every fixed period reads its fixing, every unfixed period its contract's quote, one quote past the schedule's last contract is refused, and so is none | property |
| both objects kept themselves, no array made, the record refusing writes; neither input changed, two markets sharing one history, and a repeated call a new market | example |
| two handles in and each of the three markets read back period by period; the futures page's example, the expiring contract quoted on its expiry day and the next from the day after; valued on the first day, the last day and a Saturday; the price a number on every priced period and text on every closed day; a zero, a negative and a repeated quote as given; two markets sharing a history; a futures market with the first quote alone read back through that contract's expiry day, a Gas Daily market through the last day of the last month quoted and an IFERC market through its last month's row, the history kept in each, and a last covered contract of closed days alone keeping its rows | example, through the seam |
| a quote past the schedule's last contract, a history with no unfixed period and a vector named for another index, the library's words, on each kind; each argument left out, blank, a number, text naming no live object, a creator's failure relayed or a handle of another kind, the seam's words, the market's own handle included | example, through the seam |
| a failed construction publishes no object and no handle; repeated calls through the seam's prepared path publish fresh handles and the earlier ones stand, nothing being released there; a dead market handle cannot be read | example, with handles |
| a market's call typed in another cell shares the live market, and a changed price gives the vector and the market new handles and releases the old two, through the production registration | the lifetime script's `edits` and `core` groups |
| the spill of a one-day futures market: the quote a number on the open day, `closed` as text when the day is a holiday, the quote still required; the spill of a one-month Gas Daily market and of a one-month IFERC market, fixed and not | example |
| for any history of any of the three kinds and any count of quotes from one to the contracts that remain: the rows are the calendar's spill through the last period of the last contract quoted, every one and no other, and the fifth cell is the fixing, the contract's quote or `closed`, with no `unfixed` period | property |
| the creator's handle read back in a real workbook, 34 days over a two-contract futures schedule with one quote, a fixing, `closed` and the quote read; a Gas Daily market over the schedule page's three months with a balance-of-month and two month quotes, and an IFERC market over its three with one quote, a fixing and a quote read from each; a quote past the schedule's last contract on a futures and on a Gas Daily history, a history with no unfixed period, a vector named for another index and a futures history valued before its calendar, which builds; a Gas Daily market with one quote of its three months, read back through September's last day, the valuation day's print kept and no row of October | Excel smoke |

## Not here

A quote derived from another market, a Gas Daily month from the IFERC forward for the month and a basis: a formula in the price vector's cells today, and a creator of its own if the desk wants one, never a branch here. The average of a month's days, the settle of a period, pricing and risk: the instruments' work, built on this. A feed subscription, the freshness of a quote, and a quote for the periods already fixed: the vector is a snapshot as [price-vector.md](../market-data/price-vector.md) says, and a fixing stands. Whether the vector is this index's beyond its name: the name is a label compared as text, never a lookup and never the index object, so two indices of one name pass and a vendor column labelled wrongly passes; the order of the quotes is the sheet's, as before. A layout handle, a cache, float32 storage and a typed transport for the prices: none of them here. The sharing and the release of a market's handle: the seam's, since #114, the same for every creator. Reading a price by date or by month: the instruments', along this market. A contract code on the vector, a starting contract, and any check that the first price is the first required contract's: deferred, as When the first contract rolls says. A price for a period past the last contract quoted: none, by design, the last quote never carried forward and no other contract's borrowed. A worksheet function that reads one price: none, the live prices being read by the library's own readers through the market. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any market as the calendar's columns and the price.
