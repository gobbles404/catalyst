# _QuoteFTCPrices

Built in #NNN from [ftc-monthly-prices.md](../../engineering-tickets/trade-valuation-pipeline/ftc-monthly-prices.md), with [_CreateRFQ and _QuoteRFQ](rfq.md). The bridge from the one price a desk agrees for a fit-to-curve deal back to the fixed price of each month the deal is booked at: every month's own price on the curve moved by the same amount, the agreed price less the request's fit-to-curve quote, and rounded alone to the decimals a price may hold, with the average the fixed prices come back to and its difference from the agreed price shown above them. It reads the saved request [_QuoteRFQ](rfq.md) prices, so each month's own price and its share are formed once, by the quote's own steps. The code is `src/catalyst/quoting/ftc_prices.py`, the prices, `src/catalyst/quoting/request.py`, the two steps it shares with the quote, and `src/catalyst/excel/quoting.py`, the worksheet function and its table.

## Worksheet contract

```python
def _QuoteFTCPrices(
    market: Handle[Market],
    rfq: Handle[Rfq],
    price: float,
    decimals: int,
) -> MixedArray: ...
```

Three months at 4.50, 4.30 and 3.00, the same quantity each, agreed at 3.95 with two decimals allowed; the request in B5, the market in a cell named `gas_market` and the collection of curves in `rates`:

| | A | B | C | D |
|---|---|---|---|---|
| 6 | quote | `=_QuoteRFQ(gas_market, B5, "ftc", rates)` shows 3.9333 | | |
| 7 | agreed | 3.95 | | |
| 9 | `=_QuoteFTCPrices(gas_market, B5, B7, 2)` spills from here: `agreed_price` | 3.95 | - | - |
| 10 | `average_fixed_price` | 3.95333333333333 | - | - |
| 11 | `difference` | 0.00333333333332986 | - | - |
| 12 | `period` | `quantity` | `curve_price` | `fixed_price` |
| 13 | `str` | `float64` | `float64` | `float64` |
| 14 | F27 | 10000 | 4.5 | 4.52 |
| 15 | G27 | 10000 | 4.3 | 4.32 |
| 16 | H27 | 10000 | 3 | 3.02 |

All four arguments are required. The market is the one of [_CreateMarket](../market/market.md) over the request's index, held to that exact object as `_QuoteRFQ` holds it. The request is the handle of [_CreateRFQ](rfq.md): its rows give the months and their quantities, and its quote template how each month's own price is formed. The price is the one agreed for the whole request, a fit-to-curve price, any number. The decimals are a whole number from 0 to 15. No collection of curves is taken on either route: a fit-to-curve price discounts nothing.

The cell spills a table four cells wide. The check comes first, three rows that sit in the same cells whatever the request holds, each a word, its number and a dash in the two cells beside them, since a spilled table holds no empty cell: `agreed_price`, the price as given; `average_fixed_price`, what the fixed prices come back to; and `difference`, the average less the agreed. Then the header row, the type row every table of the library carries, and one row per component in the request's order: its `period`, a contract code in the schedule's spelling or a window's two dates; its `quantity`, the one the average weighs it by, the row's own per month or per period and the row's times its days per calendar day; its `curve_price`, the component's own price as the quote forms it; and its `fixed_price`, the price to book, under the name the booking's own field has. Nothing is published and nothing retained.

## Excel help

| Item | Text |
|---|---|
| Function | Quotes the fixed price of each month of a saved request from one agreed fit-to-curve price, each month's own price moved by the same amount and rounded, and above them the agreed price, the average the fixed prices come back to and the difference. |
| market | The market handle over the request's index: the cell showing _CreateMarket's result, such as I12, or a name for it, with the day's quotes over the history they follow. |
| rfq | The request handle: the cell showing _CreateRFQ's result, such as B5, or a name for it. |
| price | The one price agreed for the request, a fit-to-curve price, such as B7 or 3.95; every month's own price is moved by the same amount, this price less the request's fit-to-curve quote. |
| decimals | The decimals a fixed price may hold, a whole number from 0 to 15, such as 2; each fixed price is rounded alone, as ROUND rounds. |

## The prices

```text
curve_i    = each component's own price                 as the quote has it
ftc        = sum(q_i * curve_i) / sum(q_i)              the request's fit-to-curve quote
fixed_i    = ROUND(curve_i + (price - ftc), decimals)   the same amount on every component
average    = sum(q_i * fixed_i) / sum(q_i)
difference = average - price
```

`curve_i` and the shares are [_QuoteRFQ](rfq.md)'s own under `ftc`, [quote.md](quote.md#the-pricing): the fixings for the observations that have passed, the day's quotes for the rest, the template's method, nearby and basis. So `ftc` here is to the last digit the number `_QuoteRFQ(market, rfq, "ftc", ...)` shows, and with that cell as the price nothing moves: the fixed prices are the curve's own at the decimals it is quoted to, and the difference is zero.

Every component takes the same amount and not the same percentage. The differences from month to month stay the market's; the amount is what a margin of two cents means; and it holds on any price a market holds, zero and below included, where a percentage turns the wrong way or has no meaning: a basis strip at 0.02, -0.50 and 0.00 quotes -0.16, and agreed at -0.15 its months are 0.03, -0.49 and 0.01.

On the example each month takes 1.67 cents, 4.5167, 4.3167 and 3.0167, which round to 4.52, 4.32 and 3.02 and come back to 11.86 / 3 = 3.9533, a third of a cent over the agreed 3.95. With unequal quantities, January at 10,000 and March at 20,000, the quote is 105,000 / 30,000 = 3.50; agreed at 3.516 the months are 4.52 and 3.02 and come back to 105,600 / 30,000 = 3.52. A component of no quantity takes a fixed price as the others do and has no share in either average.

## The rounding

Each fixed price is rounded alone, as the sheet's own `ROUND` rounds, so that a cell of `=ROUND(curve + price - quote, decimals)` beside the table agrees with it: the price is read to the fifteen significant digits a cell shows, and a half step goes away from zero. The reading is what makes 4.515 at two decimals 4.52. The number a cell holds for 4.515 is a hair under it, and by its bits alone its nearest hundredth is 4.51, which no one reading the sheet would call rounded; -4.515 is -4.52. A price too large to hold a digit at the allowed decimals, fifteen digits or more of steps, is left as it is, and a price that rounds to nothing is zero, never minus zero.

## The check

The fixed prices are not fitted to the agreed price. Each is within half a step of its unrounded price, and the unrounded prices average to the agreed price, so the average is within half a step of it; where it matters that they tie, to the dollar or beyond the decimals, the desk sees the difference and moves a month by hand, in the customer's favor.

The average and the difference are read to the fifteen significant digits a cell shows, as the rounding reads a price. A month's own price is a sum of weighted observations and carries the sixteenth digit's dust, twenty settles of 4.30 averaging 4.299999999999999, so that prices which tie to the cent would otherwise differ from the agreed price by 4e-16, and a check that says so is no check. Read as shown, prices that tie say zero. A difference that is not zero is the one the sheet's own subtraction of the two cells above it gives, 3.95333333333333 less 3.95 showing 0.00333333333332986: its last digits are the subtraction's, and no one's miss.

## The library checks

The rules in this order, the first failure being the cell's text after `#ERROR _QuoteFTCPrices: ValueError:`. The seam's come first and are each argument's alone: `price is blank, expected number`, `price is text '3.95', expected number`, `decimals is missing, expected whole number`, `decimals is number 2.5, expected whole number`, and a handle of another kind by its kind.

| Check | Refused as |
|---|---|
| the decimals from 0 to 15, the digits a cell shows of a number | `decimals is 16, expected a whole number from 0 to 15, the decimals a fixed price may hold` |
| the market's index is the request's, the one object, before any data is gathered, [rfq.md](rfq.md)'s check | `market is over another index, 'TOY_GAS', expected the request's, 'STRIP'` |
| the market's own rules, as the request's quote meets them: a day before the calendar, a contract beyond the market's coverage, a physical request's contract expired, [quote.md](quote.md) | `F27 expired 2027-01-29, before valuation date 2027-02-01; a physical fixed_float after its expiry is not supported` |
| every component's price, moved, is a finite number | `price is 1e+308, expected a price the request's own can be moved to; F27 at 1e+308, moved by the price less the fit-to-curve quote of 0.0, outruns the largest number` |

The collection's checks are not among them: no collection is taken, so a request whose payments run past its curve, which a flat quote refuses, is priced as any.

## Work

The function reports what it did in the quote's counters: the fixings read, one per fixed observation, and the live prices read, one per distinct live contract, as a quote of the request reads them; five reductions, the components' prices, the largest weight's exponent, the weights, the quote and the average; and `prices_rounded`, one per component. No curve is selected and no factor read, and nothing of the request's periods, observations or payments is made again. The rounding is one pass over the components. The budgets under `tests/performance` pin the counts, the functions it runs once whatever the request and the peak, within the quote's own.

## Tests

| Rule | Test |
|---|---|
| the issue's example by hand, one more decimal and none; unequal quantities, their scale and their order; a component of no quantity | `tests/unit/test_ftc_prices.py`, example |
| at the request's own quote the curve's prices and a difference of exactly zero; a cleared request the same table; every component moved by the same amount | example |
| the rounding as `ROUND`: 4.515, 4.505, 2.675 and 1.005 up, their negatives away from zero, halves the bits hold exactly, a price under a half by more than fifteen digits, more decimals than the number holds, a price with no digit at the decimals, zero never minus zero | example |
| every rounded price at the decimals and within half a step, rounded once is rounded, either side of zero alike; the average within half a step of the agreed price for any price, decimals and quantities | property |
| prices at zero and below; a request of windows under their dates; a request per calendar day weighed by its days | example |
| no curve taken and no factor read; the decimals' range; another index's market; a physical request's expired contract; a price that cannot be moved to | example |
| the table through the seam, cell by cell, and the seam's refusals of each argument | example, through the seam |
| the counts, the functions run once for a month and a year, the peak within the quote's bound, the seam's own steps | `tests/performance/test_ftc_prices_budgets.py` |
| the help lines | `tests/unit/test_help.py` |
| from the host, in the request's fact | `host/Catalyst.Host.Tests/CallTests.cs` |
| in Excel, against the sheet's own `ROUND` | `tools/excel_smoke.ps1` |

## Not here

Fitting the fixed prices to the agreed price, which month would move and in whose favor; a form by contract code or by two dates, which a one-row request already is; a margin as its own input, which the agreed price carries; spreading the difference by percentage; rounding to a price grid that is not a count of decimals; booking the months from the table; a handle or a reader of the result; and any cache. The function books nothing and changes nothing: the market and the request are read-only inputs.
