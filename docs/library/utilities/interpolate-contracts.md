# util_InterpolateContracts

Infers every monthly contract from the first anchor's month through the last's on a futures index's schedule, and gives each with the index's futures expiry and the price on the straight line between its anchors, weighted by the calendar days between the expiries: `J27` at 70 and `M27` at 76, expiring 22 March and 20 May 2027, put `K27`, expiring 20 April, 29 of 59 days along, at 72.94915254237289. Codes or the months as CME spells them and their prices in, a three-column table out, no handle: the desk types the few outright quotes it has and reads the monthly list it needs, the contract, the date and the price paired in view, and chooses the rows its price vector takes. The straight line between dated points is the library's one rule for interpolation, [conventions.md](../conventions.md#what-holds-everywhere), here with the futures expiries as the dates. The code is `src/catalyst/market_data/interpolated_contracts.py`, the rules and the interpolation, `src/catalyst/index_definitions/contract_codes.py`, the codes' reading and the schedule's monthly reading the trades share, and `src/catalyst/excel/utilities.py`, the worksheet function. [The ticket](../../engineering-tickets/trade-valuation-pipeline/interpolate-contract-prices.md) has the decisions.

## Worksheet contract

```python
def util_InterpolateContracts(
    index: Handle[Index], anchor_contracts: TextColumn, anchor_prices: NumberColumn
) -> MixedArray: ...
```

| | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| 1 | 202704 | 70 | | `=_CreateIndex("CL",…)` | `=util_InterpolateContracts(D1,A1:A2,B1:B2)` spills `contract_code` | `future_expiry` | `price` |
| 2 | 202706 | 76 | | | `str` | `datetime64[D]` | `float64` |
| 3 | | | | | `J27` | 22-Mar-2027 | 70 |
| 4 | | | | | `K27` | 20-Apr-2027 | 72.94915254237289 |
| 5 | | | | | `M27` | 20-May-2027 | 76 |

Three arguments, all required. The index is a handle, the cell showing `_CreateIndex`'s result, which the seam checks as it checks any handle, as [inputs.md](../../seam/inputs.md) says, and the library holds to a futures index, whose schedule has a futures expiry per contract; an IFERC or a Gas Daily index is refused rather than given a publication or a flow date. The anchors are two columns without headers, the months as text and the prices as numbers, one price per month in the same rows, which the seam checks as it checks any column of text and any column of numbers: a number where a month should be is refused, `202704` typed as a number among them, so the month is typed as text or taken from [util_FutToCme](fut-to-cme.md), whose six digits this function reads; a blank, a row and a boolean are refused in the seam's words, and the lengths disagreeing in the library's. The result is a table under the repository's two heading rows, as [outputs.md](../../seam/outputs.md) sends one: the codes as the schedule spells them, the expiries as dates and the prices as numbers, nothing rounded, nothing kept and no handle made.

A month is written either way, `Z27` or `z27`, a month letter and a two-digit year, or `202712`, the year then the month as CME's feeds spell it, six digits of 2000 to 2099 and 01 to 12, and the column may mix the two; each label is read whole, so a strip, a quarter, a half, a CAL, a BAL, a date and a product root are not months here. The months must increase down the column and name each month once, `Z27` and `202712` being one month; the anchors are never reordered. The schedule is read as the trades read it, every row for its month, so a schedule code that is no month or two rows of one month are refused in the reader's words, and every month from the first anchor's through the last's must be on it, the first that is not named with its month and code: nothing is skipped, chosen between two rows or made up. The selected months' expiries must be dates increasing in month order, the first pair that is not named with its contracts and dates. Then the line: numpy's `interp` over the days from the first anchor's expiry, the anchors the points and the months in between the targets, which the range keeps inside the anchors, so nothing is extrapolated and no endpoint repeated; an anchor keeps its price exactly; a supplied month between two others stands at its own price, and the months around it interpolate to it. Prices may rise, fall, repeat, be zero or be negative; each must be finite in, and the first that is not finite out is refused by its contract with the anchors on either side, under numpy's flags down.

## Using the spill as market input

The spill is the monthly list; the sheet chooses the rows a market takes. [`_CreatePriceVector`](../market-data/price-vector.md) takes a column of prices and the index's name, the first price the market's prompt's, the first unfixed contract on the calendar, and the rest the schedule's contracts in order; so the applicable rows are a contiguous run of the price column starting at the prompt, `G3:G5` in the grid above when `J27` is the prompt, and the vector goes to [`_CreateMarket`](../market/market.md) with the history as any vector does. The vector carries prices and a name, not labels or expiries, so the sheet keeps the alignment, and the whole spill is wrong when its first month is not the prompt, [market.md](../market/market.md#when-the-first-contract-rolls); a one-off price is looked up by code in the spill. An anchor price or a schedule expiry changed recalculates the spill and whatever hangs off it through Excel's dependencies; the function is not volatile and reads no valuation date, market, history or prompt, so a roll of the valuation date moves nothing here and the sheet moves the run it selects. The kept workbook's block from row 2812 holds the grid above feeding a vector, a market and one lot of `K27` marked on it, then June moved to 82, then `K27`'s expiry moved to 5 May, then the three prices typed by hand with the same mark.

## Excel help

Quoted from the declaration in `src/catalyst/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Infers every monthly contract from the first anchor's month through the last's, each with the index's futures expiry and the price on the straight line between its anchors weighted by calendar days, and spills contract_code, future_expiry and price. |
| `index` | The index handle: the cell showing _CreateIndex's result, such as B9, or a name for it; a futures index, whose schedule has a futures expiry per contract. |
| `anchor_contracts` | A column of at least two contract months in increasing order, each a code such as F26 or the month as CME spells it, 202601, as text, without a header, such as A2:A3. |
| `anchor_prices` | A column of one price per anchor, in the same rows and the index's quote convention, without a header, such as B2:B3. |

## The library checks

In this order, the first failure being the message, which names the argument and the one-based row it read, or the contract and the schedule row, and says what was expected; a repeated month names both rows.

| Rule | Named |
|---|---|
| the index is a futures index | the index's kind |
| one price per anchor | the counts |
| at least two anchors | the count |
| each label a code or a CME month | `anchor_contracts` and the row |
| each price finite | `anchor_prices` and the row |
| each month once | `anchor_contracts` and both rows, with the month |
| the months increasing by row | `anchor_contracts`, the row and the row before it, with the months |
| every schedule row a month, each month once | the schedule rows, in the trades' reader's words |
| every month from the first anchor's through the last's on the schedule | the month and its code, with the range |
| each selected expiry a date | the schedule row and its code |
| the selected expiries increasing in month order | the two contracts and their dates |
| each price out finite | the contract and the anchors on either side |

The exact words are pinned in `tests/unit/test_interpolate_contracts.py`.

## Tests

The hand answers, the rules and the seam's columns are `tests/unit/test_interpolate_contracts.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_interpolation_budgets.py`, the library's anchors, schedule rows, months and one interpolation at three months and at a hundred and twenty, and in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py` through the seam.

## Not here

Which months are reliable anchors, whether a straight line suits the commodity and its seasons, and any curve fitted or strip average held: the desk's, before the anchors are typed. Which month is the market's prompt, and the rows the vector takes: the sheet's, as above. A price-unit conversion: none, the prices being in the index's quote convention as supplied, as the help says. IFERC and Gas Daily indexes, whose dates are publications and flows: refused, not substituted. Extrapolation before the first anchor or after the last, a month the schedule lacks, an expiry made up or moved by a holiday, and rounding to a tick: none. The sensitivity of a hedge to the sparse anchor quotes rather than to the monthly prices: separate work, as [the ticket](../../engineering-tickets/trade-valuation-pipeline/interpolate-contract-prices.md) says.
