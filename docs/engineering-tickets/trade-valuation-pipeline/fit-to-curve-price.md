# A fit-to-curve single price from the quote functions

**Status:** Built in #NNN, agreed with the owner on 17 November 2026 for
[issue #219](https://github.com/gobbles404/catalyst/issues/219), this page in its first commit;
one pull request on `feat/ftc-quote`, from main after #248.
[quote.md](../../library/quoting/quote.md) owns the calculation;
[quote-by-dates.md](../../library/quoting/quote-by-dates.md) and
[rfq.md](../../library/quoting/rfq.md) are the other owners it updates. It follows
[template-based-quoting.md](template-based-quoting.md), [rfq-quoting.md](rfq-quoting.md) and
[dated-quotes.md](dated-quotes.md), to whose three functions it adds one argument.

## The issue

A regular swap has one flat fixed price for the whole strip. A fit-to-curve swap, FTC, gives
the customer one fixed price per month, each set at that month's own price on the curve. The
desk speaks of an FTC deal by its single price, the summary of those monthly prices: their
average weighted by quantity alone. A customer asked for one, a third-party platform showed a
flat and a fit-to-curve price about 18 cents apart on a 27-month request, and the library
quoted the flat price alone.

## Decisions of 17 November 2026

| Decision | Agreed |
|---|---|
| Where it lives | A quoting feature. Nothing is added to the instrument, the quote template or a booking: an FTC deal is booked as a regular swap, a row per month at its own price, which knows nothing of how it was quoted. |
| The argument | `pricing`, text, `flat` or `ftc`, required, on `_Quote`, `_QuoteByDates` and `_QuoteRFQ`, before the optional `discount_curve_set`, since a required argument cannot follow an optional one. No default: every quote cell says which price it shows, and every existing formula gains the word, with no compatibility path. Chosen over three more worksheet functions, a field on the quote template and a default of `flat`. |
| The words | Matched exactly, case and all, as every code of the library is, so `FTC` is refused by name. A blank cell and a left-out argument fail in the seam's words. |
| The collection | Taken the same way under either pricing, so that one formula serves both with the one word changed and a cell can hold the word: on a bilateral template the collection is required, its key bound and its start checked. Under `ftc` no factor is read of it, so a curve too short to cover a late payment is not refused. The owner's choice, "so the signature isn't volatile", over refusing the collection under `ftc` as a cleared quote refuses it. |
| A cleared quote | Allowed under `ftc`, and the same number as under `flat`, since a cleared quote already discounts nothing. |
| One payment | Allowed under `ftc`, and the same number as under `flat`: one month, a `onetime` window, a one-row request. A request may hold several `onetime` rows, where the two differ, so a refusal by frequency would be wrong. |

## Calculation

```text
flat = sum(quantity * factor * price) / sum(quantity * factor)     the quote as it was
ftc  = sum(quantity * price)          / sum(quantity)
```

`price` is each component's floating price as the quote forms it, and `factor` its payment's
discount factor. `ftc` is the same request with every factor taken as 1. Everything before the
last average is unchanged: the period, the observations, the fixings, the live prices, the
nearby, the quantities and the payment days.

Under a flat price on a sloped curve the early months sit on one side of the price and the late
months on the other, so value moves across time, and the factors are what make it net to
nothing today. Under FTC each month stands at its own level, so nothing moves between months
and no factor is needed. The difference between the two prices is the time value of that
movement.

| Month | Price | Quantity | Discount factor |
|---|---:|---:|---:|
| 1 | 4.50 | 3,100,000 | 0.99 |
| 2 | 4.30 | 280,000 | 0.95 |
| 3 | 3.00 | 310,000 | 0.90 |

- flat = 15,791,300 / 3,614,000 = 4.36948
- ftc = 16,084,000 / 3,690,000 = 4.35881

The quantities are a request's rows, so the example as written runs on `_QuoteRFQ`. `_Quote`
and `_QuoteByDates` take no quantities and weigh by the template's basis: the same prices and
factors quote 11.24 / 2.84 = 3.95775 flat and 11.8 / 3 = 3.93333 fit to curve per month, and
per calendar day, 31, 28 and 31 days, 336.185 / 85.19 = 3.94630 and 352.9 / 90 = 3.92111.

The owner's check before the build: a 27-month WTI request with a declining quantity per
month, on a curve falling from 82.51 to 67.47, gave 72.925 flat and 72.748 fit to curve, 17.7
cents apart, against about 18 cents from a third-party platform for the same request.

A cleared quote takes every factor as 1, so an `ftc` price on a bilateral template is the
`flat` price of the same terms cleared: the same calculation, and the same number to the last
digit. That is the build's own check on every fixture the quote tests price, and it needs no
new hand arithmetic.

## Ownership

| Fact | Owner |
|---|---|
| The two words and their reader | `Pricing` and `pricing_of` in `quoting/request.py`, through `choice` in `trades/template.py`, the reader of every code |
| The calculation | `priced` in `quoting/request.py`: under `ftc` every factor is one and `_the_factors` is not run |
| The collection, taken alike | `the_curve` in `quoting/request.py`, unchanged but for its words when the collection is missing |
| The argument on each function | `quote` and `quote_by_dates` in `quoting/quote.py` and `quote_rfq` in `quoting/rfq.py`, each reading the text once and first; `_Quote`, `_QuoteByDates` and `_QuoteRFQ` in `excel/quoting.py` |

## Refusals

| What | Words |
|---|---|
| Any other text | `pricing is 'FTC', expected flat or ftc` |
| A blank cell, a left-out argument, a number | the seam's: `pricing is blank, expected text`; `pricing is missing, expected text`; `pricing is number 1.0, expected text` |
| A bilateral formula written before the argument existed, its collection where the pricing now goes | `pricing is '30512:discount_curve_set:41', expected flat or ftc` |
| A cleared formula written before it, a cell short | `pricing is missing, expected text` |
| The collection left out on a bilateral template, under either pricing | `discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, under flat and ftc alike`, where it ended `whose payments it discounts`, which a fit-to-curve price does not |

## Also pin

- The pricing is read before the template's terms and before the market's index, so a formula
  written before the argument existed is told of the pricing whatever else is wrong.
- Each month booked at its own price marks zero, and so does every month at the flat price;
  every month at the fit-to-curve price marks the time value between the two, the discounted
  quantity times the difference, 38,569 on the example. The single price is a summary, not a
  price to book on every month.
- The payment terms stand under `ftc` as they do on a cleared quote: the request is made the
  same whatever the pricing, a saved one before the pricing is known, so a payment day on or
  before a month's last observation is refused all the same.
- Work: under `ftc` a bilateral quote reports the flat quote's counts but
  `payment_factors_read`, which is not counted at all, as on a cleared quote; `curves_selected`
  stays 1. The function ledgers gain `pricing_of` and one `choice` on every quote, and under
  `ftc` lose `_the_factors`, `factors_on` and the read of the curve's last day.

## Delivery

One pull request: the argument, the calculation, the unit and performance tests, the host
facts, the smoke's pins, the lifetime script's formulas, the three pages and the kept
workbook's quote cells, every one of which gains the word, with a block of its own from row
3320. The full gate before the pull request is opened.

## Outside this slice

- The monthly prices as an output.
- A margin on them.
- Rounding them to a price grid, and what to do with the leftover.
- Booking an FTC trade from a quote.

**Still parked: allocating an agreed price into monthly legs.** The earlier form of issue #219
asked how to split an agreed headline price into monthly fixed prices that follow the curve.
It is not started, and when it is taken up it is its own issue. What the conversation of 17
November settled for it: the headline must be a fit-to-curve price and not a flat one, since
legs set at the curve are worth the same today as the flat swap and their quantity-weighted
average is the FTC price; the two only conflict if a flat price is used as the headline. Still
open: what preserving the curve's shape means, a common shift in price, a common percentage or
another convention; the price grid; the rounding leftovers, with the earlier examples to settle
them against, 10,000, 15,000 and 20,000 at 3.100 leaving a shortfall of 5, and 3.1001 having no
exact fit; and whether the surface spills the legs or saves a handle. The quote's full-period
convention can carry over. Equal value today does not mean equal sensitivity to later rate
moves, since the flat and the shaped payment profiles differ.

Reference: AEGIS,
[High Rates Equal Higher Cost of Hedging](https://aegis-hedging.com/insights/high-rates-equal-higher-cost-of-hedging),
the fit-to-curve section.
