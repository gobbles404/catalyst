# The monthly prices of a fit-to-curve deal from its agreed price

**Status:** Built in #251, agreed with the owner on 18 November 2026 for
[issue #250](https://github.com/gobbles404/catalyst/issues/250), this page in its first commit;
one pull request on `feat/ftc-prices`, stacked on #249.
[quote-ftc-prices.md](../../library/quoting/quote-ftc-prices.md) owns the function. It follows
[fit-to-curve-price.md](fit-to-curve-price.md), which built the fit-to-curve single price and
parked this, and [rfq-quoting.md](rfq-quoting.md), whose saved request it reads.

## The issue

A fit-to-curve deal is booked as one fixed price per month. The desk agrees one single price
with the customer, the average of those monthly prices by quantity alone, and then needs the
monthly prices themselves, each at the decimals a price may hold. #249 gave the single price
from the curve; this is the bridge back, from the one agreed price to the prices to book.

## Decisions of 18 November 2026

| Decision | Agreed |
|---|---|
| Where it lives | Its own function, so that `_QuoteRFQ` stays as it is: "this is just the bridge between the two without overloading that first function". |
| What it reads | The saved request the quote took, with the market: "the volumes that got us to are part of the solution of getting from scalar to vector". The request holds the months, the quantities and the template, so each month's own price is formed as `_QuoteRFQ` forms it and nothing is worked out twice. A form by contract code or by two dates is not built: a plain strip is a one-row request. |
| How the difference is spread | The same amount on every month, the agreed price less the request's fit-to-curve quote, and not the same percentage. It holds on prices at zero and below, which the library keeps and where a percentage has no meaning, and it leaves the differences from month to month the market's. |
| The decimals | A whole number of decimals a monthly price may hold. Each month is rounded alone. |
| What is done about a difference | Nothing by the function. Round, show the average the monthly prices come back to and its difference from the agreed price, and leave the adjustment to the desk, in the customer's favor. An earlier draft had the function move months a tick until the average tied, and so take the customer's side as an argument; the owner's own design was simpler and stands: "we need to know the weighted average price to see if it breaks with the input param then I would just manually adjust". |
| The check is spilled | With the months, always: "otherwise I'll just always end up checking". |

## What the build settled

The issue left the table's place for the check and the name to confirm, and three more things
came of building it against the seam and the sheet.

- **The name** is `_QuoteFTCPrices(market, rfq, price, decimals)`, as proposed, a Quote beside
  its three siblings. No collection of curves is an argument: a fit-to-curve price discounts
  nothing.
- **The table has no empty cell.** The way out of the seam refuses one, so the three rows of
  the check carry a dash in their two spare cells, as the risk report's context row does. They
  come first, so that they sit in the same cells whatever the request holds, and the months
  follow under a header row and the type row every table of the library carries. The words
  are the library's, `agreed_price`, `average_fixed_price`, `difference`, `period`,
  `quantity`, `curve_price` and `fixed_price`, the last the booking's own field name. The
  issue sketched plain words, blank cells and no type row.
- **The rounding is the sheet's own ROUND**, a half step away from zero on the fifteen digits
  a cell shows. By the bits alone 4.515 is a hair under itself and its nearest hundredth is
  4.51, and a curve quoted to three decimals with months held to two meets such a half
  often; the owner will check the table against a ROUND on the sheet, and it must agree. The
  smoke pins the two against each other in Excel.
- **The check reads as a cell shows it.** A month's own price is a sum of weighted
  observations and carries dust in its sixteenth digit, so prices that tied to the cent
  showed a difference of 4e-16. The average and the difference are read to fifteen digits,
  the reading the rounding already uses, and prices that tie say zero.

## Calculation

```text
curve_i    = each component's own price                 as the quote has it
ftc        = sum(q_i * curve_i) / sum(q_i)              _QuoteRFQ(market, rfq, "ftc", ...)
fixed_i    = ROUND(curve_i + (price - ftc), decimals)
average    = sum(q_i * fixed_i) / sum(q_i)
difference = average - price
```

| Month | Curve | Moved by 1.67 cents | Fixed, two decimals |
|---|---:|---:|---:|
| F27 | 4.50 | 4.5167 | 4.52 |
| G27 | 4.30 | 4.3167 | 4.32 |
| H27 | 3.00 | 3.0167 | 3.02 |

The same quantity each month, agreed at 3.95: the quote is 11.80 / 3 = 3.9333, the fixed
prices come back to 11.86 / 3 = 3.9533, and the difference is a third of a cent. The desk
knocks one month down a cent and is at 3.95.

Each fixed price is within half a step of its unrounded price, and the unrounded prices
average to the agreed price exactly, so the average is always within half a step of it.

## Ownership

| Fact | Owner |
|---|---|
| Each component's own price and its share | `component_prices` and `shares` in `quoting/request.py`, lifted out of `priced`, which the quote and this function both call |
| The market over the request's index | `on_its_index` in `quoting/rfq.py`, lifted out of `quote_rfq` |
| The prices, the rounding and the reading to fifteen digits | `ftc_prices`, `rounded` and `as_shown` in `quoting/ftc_prices.py` |
| The table | `ftc_prices_table` in `excel/quoting.py`, beside `_QuoteFTCPrices` |

## Refusals

| What | Words |
|---|---|
| The decimals outside 0 to 15 | `decimals is 16, expected a whole number from 0 to 15, the decimals a fixed price may hold` |
| A fraction of a decimal, a blank or a text price | the seam's: `decimals is number 2.5, expected whole number`; `price is blank, expected number`; `price is text '3.95', expected number` |
| A market over another index | `market is over another index, 'TOY_GAS', expected the request's, 'STRIP'`, the request's quote's own words |
| A price the curve's cannot be moved to | `price is 1e+308, expected a price the request's own can be moved to; F27 at 1e+308, moved by the price less the fit-to-curve quote of 0.0, outruns the largest number` |

## Delivery

One pull request stacked on #249: the two shared steps lifted out of the quote, the function,
the unit and performance tests, the host facts, the smoke's pins, the page and the kept
workbook's block from row 3332. The full gate before the pull request is opened.

## Outside this slice

- Fitting the months to the agreed price: which month moves, and in whose favor. The two
  earlier examples of issue #219, 10,000, 15,000 and 20,000 at 3.100 and 3.1001 with no exact
  fit, wait for that.
- A form by contract code or by two dates.
- A margin as its own input. The agreed price carries it.
- Spreading the difference by percentage.
- A price grid that is not a count of decimals.
- Booking the trades from the table, and a handle or a reader of the result.
