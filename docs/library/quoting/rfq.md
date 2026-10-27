# _CreateRFQ and _QuoteRFQ

Built from [rfq-quoting.md](../../engineering-tickets/trade-valuation-pipeline/rfq-quoting.md), with [_Quote](quote.md) and [_CreateQuoteTemplate](quote-template.md). A request for quote: a saved quantity and payment schedule for quoting, one index and one quote template's terms over aligned columns of contract months and quantities, and either the template's payment days or a complete column of the request's own, which takes precedence over the template's day for this request alone. `_CreateRFQ` resolves the request once and shows its handle; `_QuoteRFQ` prices it on any market over the request's index by the quote's own calculation, each month at its quantity, the market supplying the day, the history, the quotes and the curve on each call. The code is `src/goosedove/quoting/rfq.py`, the record, its builder and its price, `src/goosedove/quoting/request.py`, what the quote and the request share, and `src/goosedove/excel/quoting.py`, the worksheet functions.

## Worksheet contract

```python
def _CreateRFQ(
    index: Handle[Index],
    contract_codes: TextColumn,
    quantities: NumberColumn,
    template: Handle[QuoteTemplate],
    payment_dates: DateColumn | None = None,
) -> Handle[Rfq]: ...


def _QuoteRFQ(
    market: Handle[Market],
    rfq: Handle[Rfq],
    discount_curve_set: Handle[DiscountCurveSet] | None = None,
) -> float: ...
```

The ticket's example, the index in a cell named `propane_index`, its market in `propane_market`, a bilateral quote template paying `+5bd` in `quote_template` and the collection of named curves in `rates`:

| | A | B | C | D |
|---|---|---|---|---|
| 1 | contract | quantity | payment | |
| 2 | F27 | 100000 | 8-Feb-2027 | `=_CreateRFQ(propane_index, A2:A3, B2:B3, quote_template)` shows `30512:rfq:PROPANE:46` |
| 3 | G27 | 300000 | 8-Mar-2027 | `=_CreateRFQ(propane_index, A2:A3, B2:B3, quote_template, C2:C3)` shows `30512:rfq:PROPANE:47` |
| 4 | | | | `=_QuoteRFQ(propane_market, D2, rates)` shows 1.1492307692307693 |
| 5 | | | | `=_QuoteRFQ(propane_market, D3, rates)` shows 1.1492227979274612 |

`_CreateRFQ` takes four arguments and a fifth that may be left out. The index is the one of [_CreateIndex](../index-definitions/index.md), the cell showing its handle or a name for it, the one index every row is on; `_QuoteRFQ` holds the market to that exact object. The contract codes are one column of text, a month per row, `F27` or `g27`, read by the one reader of a contract code, [contract-codes](../time.md), in any order and a month more than once allowed; a strip, a balance or any other label is refused by its row, since a row of a request is one month with its own quantity and payment. The quantities are one column of numbers beside them, one per row, finite and zero or more with at least one positive, in one common unit the caller chose and the signature does not carry: a common scale cancels in the price, no reporting lot is read and no specification selected. The template is a quote template and no other kind, [quote-template.md](quote-template.md). The payment dates, when given, are one column of dates beside the rows, one per row, taken exactly in place of the template's `payment_day`; left out, the argument is nothing and the template's day or rule pays each month, and a blank cell in its place is a blank, not a left-out argument, the seam's rule. A single cell is a column of one; a row or a wider range is refused by its shape, and a cell of another type by its place, `contract_codes cell (2, 1) is number 1.0, expected text`. The result is a handle, `30512:rfq:PROPANE:46`, the index's name between the kind and the count, [handles.md](../../seam/handles.md). A successful call publishes a request and changes neither input; an unchanged recalculation shares the live one; a changed cell under it, a code, a quantity, a date, the template's or the index's own creator, makes a new one and every quote over it anew, the old released when Excel disconnects its last creator.

`_QuoteRFQ` takes the market, the one of [_CreateMarket](../market/market.md) over the request's index, the request's handle, and the collection of [_CollectDiscountCurves](../globals/collect-discount-curves.md), required when the template's route is bilateral and left out when it is cleared, as `_Quote` takes it. The cell shows the number, in the index's quote units, exactly as `_Quote` shows one; nothing is published and nothing retained.

## Excel help

| Item | Text |
|---|---|
| Function | Creates a request for quote on one index from aligned columns of contract months and quantities under a quote template's terms, paying on the template's days or on the dates given, and shows its handle, the text _QuoteRFQ takes as the request. |
| index | The index handle: the cell showing _CreateIndex's result, such as I3, or a name for it, the one index every row of the request is on. |
| contract_codes | The contract months in one column, such as A2:A4, one month per row, F27 or g27, in any order and a month more than once allowed; no strip or balance. |
| quantities | The quantities beside them, such as B2:B4, one per row in one common unit, zero or more with at least one positive: a month's total, or per calendar day under the template's calday. |
| template | The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as B3, or a name for it, which supplies the request's terms. |
| [payment_dates] | The payment days beside them, such as C2:C4, one date per row taken exactly in place of the template's payment_day; left out to pay by the template's day or rule. |

| Item | Text |
|---|---|
| Function | Quotes one fixed price for a saved request on one market, each month at its quantity, fixings for the observations that have passed and the day's quotes for the rest, a bilateral payment discounted on the template's curve on each month's own day. |
| market | The market handle over the request's index: the cell showing _CreateMarket's result, such as I12, or a name for it, with the day's quotes over the history they follow. |
| rfq | The request handle: the cell showing _CreateRFQ's result, such as B5, or a name for it. |
| [discount_curve_set] | The collection handle for a bilateral request: the cell showing _CollectDiscountCurves's result, such as I13, or a name for it, holding the curve the template names; left out for a cleared request. |

## The quantities and the payment days

Each row's quantity means what the template's `quantity_per` says: per `month` the row's total for the month, per `calday` the quantity per calendar day, which the request multiplies by the month's calendar days, weekends and holidays included, once when it is made. The calendar days never replace the method's observation weights within a month, and a monthly total is multiplied by nothing. A zero row has no weight in the price and is checked as any other, its month, its quantity and its date; a negative quantity and a request of nothing are refused by name, since a request is a weighted quote, not a spread or a net position.

The payment days are chosen before any payment is resolved. With the column left out, the template's `payment_day` serves as it serves a quote: its date on every month as entered, or its rule applied to each month's last observation day on the template's payment calendar, [compound-date-offsets.md](../../engineering-tickets/trade-valuation-pipeline/compound-date-offsets.md). With the column given, each date is the month's payment day exactly, never shifted for a weekend or a holiday and never tested against the template's rule, so a template paying `+5bd` serves requests with and without agreed dates and holds its default still, and a template without a `payment_day` is complete for a dated request; the payment calendar stays required for a financial request either way, as the template's own rules say. Either source's day must fall after its month's last observation, when the month's final price exists, the kernel's rule, [create-trades.md](../trades/create-trades.md); a physical request takes no dates and pays on no day. Repeated months paying on different days stay apart until each is discounted; nothing is collapsed. Dates turn no discounting on or off: the route does.

The precedence is the request's own, decision of [rfq-quoting.md](../../engineering-tickets/trade-valuation-pipeline/rfq-quoting.md): booking's rule that no field comes from both a template and a ticket is unchanged, the template is never changed, and no other field is overridden this way.

## The price

The calculation is [quote.md](quote.md#the-price)'s, the two functions sharing one code path, `src/goosedove/quoting/request.py`: each month's floating price is its observations' weighted prices, its payment factor is 1 cleared, 1 for a bilateral payment on or before the valuation day and the selected curve's factor on its own payment day otherwise, and the price is the quantity-and-factor-weighted mean of the months' prices.

```text
P_i = sum_j(weight_ij * price_ij)
q_i = the month's quantity, per month or per calendar day
D_i = 1 cleared; 1 bilateral with payment_i <= as_of; curve(payment_i) bilateral otherwise
K   = sum_i(q_i * D_i * P_i) / sum_i(q_i * D_i)
```

Each month's weight, its quantity times its factor, is formed from the mantissas and exponents of the two apart and shifted by one power of two from the largest weight's exponent, so that the largest weight is at least a quarter and none is above one: a power of two moves the exponent alone, so every price is as the plain products give it, while no quantity or factor the inputs allow drives a positive weight below the smallest number or the weights' sum above the largest, a quantity of 1e300 or 1e-300 pricing as a convex combination like any other; a month whose weight is negligible beside the largest counts for nothing, as it should. A row of nothing beside a month at the smallest positive factor, which the curve accepts, prices that month; 1e-100 at a factor of one beside 1e224 at 5e-324 keeps both months, 1.166333687; and a request of 1 and 2 at 5e-324 on both payments prices its cleared 3.4/3, not the larger month alone. One month quotes its floating price whatever its quantity and its factor, a common factor on every payment cancels, and every month stands in both sums whether its payment has passed or not, the full-period convention of the quote.

The ticket's worked acceptance, a month-matching asian index valued 31 December 2026 with January at 1.00 and February at 1.20, last observations Friday 29 January and Friday 26 February, a weekend-only payment calendar, a template per month paying `+5bd` and, bilateral, keyed `SOFR`; the curve 1 on the valuation day and the four payment points, fixture data and no claim about any rate:

| Code | Quantity | Default payment | Default DF | Explicit payment | Explicit DF |
|---|---:|---|---:|---|---:|
| F27 | 100,000 | 5-Feb-2027 | 0.99 | 8-Feb-2027 | 0.98 |
| G27 | 300,000 | 5-Mar-2027 | 0.97 | 8-Mar-2027 | 0.96 |

| Case | Price |
|---|---:|
| cleared, either payment input | `(100000 * 1.00 + 300000 * 1.20) / 400000 = 1.15` |
| bilateral, the template's `+5bd` | `448200 / 390000 = 1.1492307692307693` |
| bilateral, the request's 8 February and 8 March | `443600 / 386000 = 1.1492227979274612` |
| both payments on 8 March, one factor 0.96 | `1.15` |
| the same request with February quoted 1.30 | `472400 / 386000 = 1.2238341968911917` |
| per calendar day, 3,100,000 and 8,400,000, cleared | `13180000 / 11500000 = 1.1460869565217391` |

An equal-quantity request prices as `_Quote` prices the same strip under the same template, both bases, both routes and every method, and a trade booked at the request's price on its months, quantities and payment days marks zero while every payment is ahead, [evaluate-trades.md](../trades/evaluate-trades.md).

## The library checks

The rules in this order, the first failure being the cell's text after `#ERROR _CreateRFQ: ValueError:`, then `_QuoteRFQ`'s after its own prefix.

| Check | Refused as |
|---|---|
| the template holds every term a completed quote requires, [quote.md](quote.md)'s rules, the request's own dates standing in for a missing `payment_day` and a request without them told of that other source | `payment_day is missing, expected it in the quote template when settlement_method = financial, or payment_dates with the request`; `discount_curve_key is missing, expected it in the quote template when route = bilateral` |
| the index takes the terms as a quote's market would: a futures or an IFERC index, an IFERC index with lastday and a financial settlement, a physical settlement with lastday alone | `settlement_method is 'physical', expected 'financial' with the asian method; an asian future is cash settled on the average of its month's pricing days` |
| the columns align, one quantity and, when given, one date per contract code, none empty; a physical request takes no dates | `quantities has 3 rows, expected 2, one per contract code`; `payment_dates has 1 rows, expected 2, one per contract code`; `contract_codes has 0 rows, expected one or more, a month per row`; `payment_dates is supplied, expected none with settlement_method = physical; a physical delivery pays on no day` |
| each code is one month, a letter and two digits in either case, no strip, balance or other spelling, and a contract of the index's schedule | `contract_codes row 2 is 'F27-G27', expected a month letter and a two-digit year, such as F26`; `contract_codes row 1 is 'X26', expected months the index's schedule has a contract for; it has none for 2026-11` |
| each quantity finite and zero or more, at least one positive, and under `calday` its product with the month's days finite | `quantities row 2 is -1.0, expected a finite number of zero or more; a request is a weighted quote, not a spread or a net position`; `quantities are all zero, expected at least one positive; a request of nothing has no price`; `quantities row 1 is 1e+308 per calendar day, expected a finite quantity for the month; times its 31 days it outruns the largest number` |
| the observations and their pricing contracts by the pipeline's rules, each refusal naming the month's row | `F27 of row 1 has no pricing day from 2027-01-01 to 2027-01-31, expected a Monday to Friday of the days it covers the index's market is open on; the asian method averages the pricing days a component covers` |
| each payment day after its month's last observation, the template's or the request's | `F27 of row 1 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its final price exists`; `G27 of row 2 pays on 2027-02-15, expected a day after its last observation, 2027-02-26, when its final price exists` |
| `_QuoteRFQ`: the market's index is the request's, the one object, before any data is gathered; the collection supplied with a bilateral request and left out with a cleared one, the key bound and the curve starting on the valuation day; then the quote's own market rules, a day before the calendar, a contract beyond the market's coverage, an expired physical contract and a payment past the curve, [quote.md](quote.md) | `market is over another index, 'TOY_GAS', expected the request's, 'STRIP'`; `discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, whose payments it discounts`; `the payment of G27 on 2027-03-08 on SOFR is past the discount curve 'SOFR', which runs from 2026-12-31 to 2027-03-01; expected every payment day after the valuation date covered` |

## What it retains

```text
Rfq
    template            the quote template, by reference
    contract_codes      the codes as typed, one month per row, in the order given
    quantity            the entered quantities, finite and zero or more
    component_quantity  each month's quantity by the template's basis, the entered one per month
                        by reference and the entered one times the month's days per calendar day
    payment_source      template, request, or None for a physical request
    request             Request: the index and its schedule, the terms, each month as a row of the
                        schedule, the observations and each one's pricing reference, the
                        quantities, the component quantities themselves, and the payment days,
                        None for physical
```

No history, price, factor, curve or valuation day: those are the market's and the collection's, read when the request is priced, so a price tick, a corrected fixing, a valuation day rolled or a new collection reprices the same request and nothing of its months, observations or payments is made again, and no fixed or live flag is saved that a later day would outdate. An as-of change never shortens the request; a month whose payment has passed stays in the price at its realized price and factor one, as in the quote.

## Reading it back

`util_ReadHandle` on the handle spills one row per entered row in the order given, under two heading rows: `row`, counted from one; `contract_code`, the schedule's spelling; `quantity`, as entered; `quantity_per`; `component_quantity`, the month's quantity by the basis, the calendar-day effect visible; `payment_source`, `template` or `request`; `payment_date`, each month's effective day, the source's; then the request's facts on every row so that a row reads whole, `index`, `schedule_method`, `route`, `settlement_method`, `quote_unit`, `USD per BBL`, and `discount_curve_key`, a dash on the cleared route. A physical request shows a dash under both payment columns, the date column then typed `str`. Saved facts alone: nothing is priced, no factor and no price is shown, and the template's own readback shows its default still, so the precedence is visible on the sheet.

## Work

The request reports what it did in the quote's counters: at creation the template's values read, the schedule's codes read, the months resolved, one per row, the observations made, the payment rule read and its instructions applied once over the months and the payment days made, none of the rule and no shift for the request's own dates; nothing of a history, a price, a curve or a factor. A quote of the request reports the curve selected, the fixings read, one per fixed observation, the live prices read, one per distinct live contract, the payment factors read, one per distinct payment day ahead, and the four reductions, and nothing of the months, the observations or the payments, which it never makes again. The readback reports nothing.

## Tests

| Case | Where |
|---|---|
| the ticket's cases by hand: cleared on either payment input, bilateral on the template's days and on the request's, one factor cancelling, a tick repricing the same request; the readback's columns, sources and dates; a single month at any quantity; calendar-day quantities, 3,100,000 and 8,400,000; equal quantities matching `_Quote` under every method and both bases on both routes; rows reversed, a month twice, the same month paying on two days kept apart, a zero row weighed at nothing and checked | `tests/unit/test_rfq.py` |
| the market's states through the request's reuse, half fixed, fixed and paying ahead, both months paid, a corrected fixing; a trade booked at the price marking zero; the request's dates standing in for a missing `payment_day` and for a template's date the month outruns, a weekend date kept exactly, a date on the last observation refused, a physical request without dates | the same |
| the columns, the codes, the quantities at every edge and scale, the template, the index and the market refused in their words; the page's example through the seam and the seam's refusals in signature order | the same |
| the request's counts at a month and a year, by the template's rule and by its own dates; a quote of a saved request reading the history, the prices and the factors and resolving nothing; the functions each runs once; the readback pricing nothing; the seam creating once and quoting over three handles, publishing nothing; the retained bytes, 32 an observation and 24 a month, and the peaks | `tests/performance/test_rfq_budgets.py` |
| the request on the sheet: the host's fact, the smoke's XA block on the quoting strip, `tools/excel_lifetime.ps1 -Groups rfq` and the kept workbook's block from row 3147 | `host/Goosedove.Host.Tests/CallTests.cs`, `tools/excel_smoke.ps1`, `tools/excel_lifetime.ps1`, `workbooks/handles.xlsx` |

## Not here

Mixed quantity units, signed or spread quantities, bid and ask, several indexes or several keys in one request, a method, route or key per row, strips, balances or partial periods in a row, a partial column of dates or a single date broadcast, horizontal ranges, booking or accepting a request, a quote's risk, a result handle or reader, a cache or any override of another field: the ticket's deferred list, for UAT to weigh. A request books nothing and changes nothing: the index, the template, the market, the collection and its curves are read-only inputs.
