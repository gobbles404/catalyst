# _CreateRFQ and _QuoteRFQ

Built from [rfq-quoting.md](../../engineering-tickets/trade-valuation-pipeline/rfq-quoting.md) and since [dated-quotes.md](../../engineering-tickets/trade-valuation-pipeline/dated-quotes.md) a ticket's rows, with [_Quote](quote.md), [_QuoteByDates](quote-by-dates.md) and [_CreateQuoteTemplate](quote-template.md). A request for quote: a saved quantity and payment schedule for quoting, one index and one quote template's terms over a ticket's rows, each row a contract month or a strip by its code or the days between two dates, with its quantity, and either the template's payment days or a column of the request's own dates, which takes precedence over the template's day for this request alone. `_CreateRFQ` resolves the request once and shows its handle; `_QuoteRFQ` prices it on any market over the request's index by [_Quote](quote.md)'s own calculation, each component at its quantity, so that a quote tick, a corrected fixing or a rolled valuation day reprices the saved request and nothing of its periods, observations or payments is made again. The code is `src/catalyst/quoting/rfq.py`, the request, `src/catalyst/quoting/request.py`, what it shares with the quote, `src/catalyst/trades/resolution.py`, the rule a row's period is chosen and resolved by, shared with a booking, and `src/catalyst/excel/quoting.py`, the two worksheet functions.

## Worksheet contract

```python
def _CreateRFQ(
    index: Handle[Index],
    fields: TextRow,
    rows: FieldRows[QuoteTemplate],
    template: Handle[QuoteTemplate],
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
| 1 | contract_code | quantity | payment_day | |
| 2 | F27 | 100000 | 8-Feb-2027 | `=_CreateRFQ(propane_index, A1:B1, A2:B3, quote_template)` shows `30512:rfq:PROPANE:46` |
| 3 | G27 | 300000 | 8-Mar-2027 | `=_CreateRFQ(propane_index, A1:C1, A2:C3, quote_template)` shows `30512:rfq:PROPANE:47` |
| 4 | | | | `=_QuoteRFQ(propane_market, D2, rates)` shows 1.1492307692307693 |
| 5 | | | | `=_QuoteRFQ(propane_market, D3, rates)` shows 1.1492227979274612 |

And two windows by their dates under a template of the same terms holding `settlement_frequency = onetime` and `quantity_per = period` in `window_template`:

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 7 | start_date | end_date | quantity | payment_day | |
| 8 | 11-Jan-2027 | 26-Feb-2027 | 100000 | 8-Mar-2027 | `=_CreateRFQ(propane_index, A7:D7, A8:D9, window_template)` shows `30512:rfq:PROPANE:48` |
| 9 | 1-Feb-2027 | 12-Feb-2027 | 300000 | 5-Mar-2027 | `=_QuoteRFQ(propane_market, E8, rates)` shows 1.178737541528239 |

`_CreateRFQ` takes four arguments, all required. The index is the one of [_CreateIndex](../index-definitions/index.md), the cell showing its handle or a name for it, the one index every row is on; `_QuoteRFQ` holds the market to that exact object. The headers are one row of the `fixed_float`'s field names, exactly as [_ShowInstrument](../instruments/show-instrument.md) spells them, from the five a request's rows hold, `contract_code`, `start_date`, `end_date`, `quantity` and `payment_day`, in any order and any subset that gives every row a period and a quantity; any other field is a field of booking and refused by name. The rows are the rectangle under them, one row per entered row, bound by the headers as a booking's ticket is bound, [create-trades.md](../trades/create-trades.md): a cell's type follows its field, a code text, a quantity a number, a date a date, and only a cell of the three period fields may be left blank, since a row chooses its period from them. The template is a quote template and no other kind, [quote-template.md](quote-template.md); it supplies the request's terms, and its `settlement_frequency` says what each row's period is.

Each row's period is chosen by booking's rule, since [dated-quotes.md](../../engineering-tickets/trade-valuation-pipeline/dated-quotes.md) the one rule a booking's rows and a request's share: a row with both dates books the days between them, a code beside them kept as entered text and never read; a row with neither books its code, read once per distinct text through the period grammar behind [util_StartDate](../utilities/start-date.md), `F27`, `g27`, `F27-G27` or `CAL27`, every month a contract of the index's schedule, a balance refused since a request has no valuation day; a row with one date and not the other, or with no code and no pair, is refused by the first such row from the top. The quantities are one number per row in one common unit, and the payment days, when the column is given, one date per row taken exactly; a template's rule stays in the template.

`_QuoteRFQ` takes the market, the one of [_CreateMarket](../market/market.md) over the request's index, the request's handle, and the collection of [_CollectDiscountCurves](../globals/collect-discount-curves.md), required when the template's route is bilateral and left out when it is cleared, as `_Quote` takes it. The cell shows the number, in the index's quote units, exactly as `_Quote` shows one; nothing is published and nothing retained.

## Excel help

| Item | Text |
|---|---|
| Function | Creates a request for quote on one index from a ticket's rows under a quote template's terms, a month or two dates and a quantity per row, paying on the template's days or the dates given, and shows its handle, the text _QuoteRFQ takes as the request. |
| index | The index handle: the cell showing _CreateIndex's result, such as I3, or a name for it, the one index every row of the request is on. |
| fields | The request's header cells in one row, such as A1:D1, from contract_code, start_date, end_date, quantity and payment_day, in any order. |
| rows | The rows under the headers, such as A2:D4, each a contract month or two dates with its quantity, and a payment date where that column is given. |
| template | The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as B3, or a name for it, which supplies the request's terms and its frequency. |

| Item | Text |
|---|---|
| Function | Quotes one fixed price for a saved request on one market, each month at its quantity, fixings for the observations that have passed and the day's quotes for the rest, a bilateral payment discounted on the template's curve on each month's own day. |
| market | The market handle over the request's index: the cell showing _CreateMarket's result, such as I12, or a name for it, with the day's quotes over the history they follow. |
| rfq | The request handle: the cell showing _CreateRFQ's result, such as B5, or a name for it. |
| [discount_curve_set] | The collection handle for a bilateral request: the cell showing _CollectDiscountCurves's result, such as I13, or a name for it, holding the curve the template names; left out for a cleared request. |

## The rows under the template's frequency

The template's `settlement_frequency` is every row's, since a request prices under one set of terms, and it says what a row's period is, as it says what a booking row's is, [kernel.md](../trades/kernel.md). Under `monthly` a row is its calendar months, each a component with its own average, quantity and payment: a code row's month, a strip row's months each at the row's quantity, as a booking's strip row is, and a dated row's months split at month ends, the first and the last clipped to the dates given, a part of a month pricing under `asian` alone. Under `onetime` a row is one window whatever months it crosses, one average over every pricing day of it, a dated row's two dates or a code row's first day to its last, the window's contract the one pricing its first day, found as a booking finds it and read for nothing that prices, so no contract is needed for the month a window opens in; the kernel's rule over the frequency holds, a futures index, a financial settlement, the `asian` method and a quantity per `period`, the window's total, or `calday`. Code rows and dated rows stand together in one request, every row under the template's one frequency; mixing monthly and onetime calculations in one request is outside this version. The readback names each component under `period`, a month's code in the schedule's spelling or a window's two dates, `2027-01-11 to 2027-02-26`, and the row it came from.

## The quantities and the payment days

Each row's quantity means what the template's `quantity_per` says: per `month` the row's total for each of its months, per `period` the total of the row's window, and per `calday` the quantity per calendar day, which the request multiplies by each component's calendar days, weekends and holidays included, once when it is made. The quantities are weights, finite and zero or more with at least one positive, fractions among them: a request is a weighted quote, not a booking, and no whole-number rule applies. The calendar days never replace the method's weights within a component: pricing days are never calendar days.

The payment days are chosen before any payment is resolved. With the `payment_day` column left out, the template's `payment_day` serves as it serves a quote: its date on every component as entered, or its rule applied to each component's last observation day on the template's payment calendar, [compound-date-offsets.md](../../engineering-tickets/trade-valuation-pipeline/compound-date-offsets.md), a window's from its final observation. With the column given, each row's date is the payment day of each of its components exactly, never shifted for a weekend or a holiday and never tested against the template's rule, so a template paying `+5bd` serves requests with and without their own days, and a template without a `payment_day` serves a request that has them. The column holds dates alone: a rule in a cell is refused by its row, since a request's rows pay on dates and a rule is the template's to hold; a blank cell in the column fails in the seam's words, no row falling back to the template. Every payment day is after its component's last observation, when the component's final price exists.

The precedence is the request's own, decision of [rfq-quoting.md](../../engineering-tickets/trade-valuation-pipeline/rfq-quoting.md): booking's rule that no field comes from both a template and a ticket is unchanged, the template is never changed, and no other field is overridden this way.

## The price

The calculation is [quote.md](quote.md#the-price)'s, the two functions sharing one code path, `src/catalyst/quoting/request.py`: each component's floating price is its observations' weighted prices, its payment factor is 1 cleared, 1 for a bilateral payment on or before the valuation day and the selected curve's factor on its own payment day otherwise, and the price is the quantity-and-factor-weighted mean of the components' prices.

```text
P_i = sum_j(weight_ij * price_ij)
q_i = the component's quantity, per month, per period or per calendar day
D_i = 1 cleared; 1 bilateral with payment_i <= as_of; curve(payment_i) bilateral otherwise
K   = sum_i(q_i * D_i * P_i) / sum_i(q_i * D_i)
```

Each component's weight, its quantity times its factor, is formed from the mantissas and exponents of the two apart and shifted by one power of two from the largest weight's exponent, so that the largest weight is at least a quarter and none is above one: a power of two moves the exponent alone, so every price is as the plain products give it, while no quantity or factor the inputs allow drives a positive weight below the smallest number or the weights' sum above the largest, a quantity of 1e300 or 1e-300 pricing as a convex combination like any other; a component whose weight is negligible beside the largest counts for nothing, as it should. Every component stands in both sums whether its payment has passed or not, the full-period convention of the quote.

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

The same index's windows under a `onetime` template of the same terms, bilateral on `SOFR`, since [dated-quotes.md](../../engineering-tickets/trade-valuation-pipeline/dated-quotes.md): 11 January to 26 February, fifteen F27 days at 1.00 through its expiry and twenty G27 days at 1.20, one average of 35, `39/35`; and 1 to 12 February, ten G27 days at 1.20:

| Window | Quantity | Payment | DF | Average |
|---|---:|---|---:|---:|
| 11-Jan-2027 to 26-Feb-2027 | 100,000 | 8-Mar-2027 | 0.96 | `39/35 = 1.1142857142857143` |
| 1-Feb-2027 to 12-Feb-2027 | 300,000 | 5-Mar-2027 | 0.97 | `1.20` |

| Case | Price |
|---|---:|
| the two windows, bilateral | `(96000 * 39/35 + 349200) / 387000 = 1.178737541528239` |
| the two windows, cleared | `(100000 * 39/35 + 300000 * 1.20) / 400000 = 1.1785714285714286` |
| one window at any quantity, either route or basis | `39/35`, the price `_QuoteByDates` gives the same dates under the same template |
| 11 January to 26 February as one row under `monthly`, per month | January's fifteen days and February's twenty, each at the row's quantity: the price of the rows `F27` and `G27` at that quantity |

An equal-quantity request prices as `_Quote` prices the same strip under the same template, both bases, both routes and every method; a one-row window prices as `_QuoteByDates` prices its dates; and the rows booked at the request's price, the months as monthly rows and the windows as onetime rows, with their quantities and payment days, mark zero while every payment is ahead, [evaluate-trades.md](../trades/evaluate-trades.md), the same in either row order and with a window repeated at a part of its quantity.

## The library checks

The rules in this order, the first failure being the cell's text after `#ERROR _CreateRFQ: ValueError:`, then `_QuoteRFQ`'s after its own prefix. The seam's own come first in its words: a header that is no field of the `fixed_float`, `fields cell (1, 1) is text 'contract_codes', expected a field of fixed_float: ...`, a cell of the wrong type or a blank cell outside the period fields, `rows cell (2, 2) is text 'ten', expected number`, and a template of another kind.

| Check | Refused as |
|---|---|
| the headers among the five fields a request's rows hold, a quantity column, one row at least | `trade_id is a field of booking alone, expected one a request's rows hold: contract_code, start_date, end_date, quantity, payment_day`; `quantity is missing, expected a column of the request, one per row` |
| the template holds every term a completed quote requires, [quote.md](quote.md)'s rules, the request's own dates standing in for a missing `payment_day` and a request without them told of that other source | `payment_day is missing, expected it in the quote template when settlement_method = financial, or a payment_day column in the request`; `discount_curve_key is missing, expected it in the quote template when route = bilateral` |
| the frequency with the terms it stands under, the kernel's rule over the template's one set of terms, the request named in the trade's place, [kernel.md](../trades/kernel.md) | `quantity_per of the request is 'period', expected 'month' or 'calday' under settlement_frequency = monthly; period is the total of a onetime period and says nothing of a month`; `quantity_per of the request is 'month', expected 'period' or 'calday' under settlement_frequency = onetime; month says nothing of a window, period is its total and calday its days`; `schedule_method of the request is 'lastday', expected 'asian' under settlement_frequency = onetime; a onetime period averages every pricing day it covers, and the expiry-based methods take their contract's month` |
| the template's `nearby` with the terms it stands under, since [nearby-selection.md](../../engineering-tickets/trade-valuation-pipeline/nearby-selection.md), every row's as the frequency is, the request named in the trade's place; each row's references are made once when the request is created, the day's prompt and the nearby counted on, and priced on any market as a quote's are, [quote.md](quote.md) | `nearby of the request is 2, expected 1 under schedule_method = lastday; the expiry-based methods take their own contract's days, and a later nearby is priced under asian` |
| the index takes the terms as a quote's market would: a futures or an IFERC index, an IFERC index with lastday and a financial settlement, a physical settlement with lastday alone; a physical request takes no dates | `settlement_method is 'physical', expected 'financial' with the asian method; an asian future is cash settled on the average of its month's pricing days`; `payment_day is supplied, expected none with settlement_method = physical; a physical delivery pays on no day` |
| each row's period by booking's rule: both dates, a code, or refused by the first row with one date or none; the end on or after the start; a code through the period grammar and every month a contract of the schedule; a window opening on or before the last day the schedule's contracts price | `start_date row 1 is 2027-01-11 without end_date row 1, expected both dates, the period's first and last day, or neither and a contract_code`; `row 2 has no period, expected a contract_code or start_date with end_date on each row; contract_code, start_date and end_date are not supplied`; `end_date row 1 is 2027-01-11, expected a day on or after start_date row 1, 2027-02-26`; `contract_code row 2 is 'Z6', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28`; `contract_code row 1 is 'X26', expected months the index's schedule has a contract for; it has none for 2026-11`; `start_date row 1 is 2027-03-01 and end_date row 1 2027-03-31, expected a window priced by the contracts of the index's schedule; it opens on 2027-03-01, after the last day they price, 2027-02-26` |
| each quantity finite and zero or more, at least one positive, and under `calday` its product with the component's days finite | `quantity row 2 is -1.0, expected a finite number of zero or more; a request is a weighted quote, not a spread or a net position`; `quantity is zero on every row, expected at least one positive; a request of nothing has no price`; `quantity row 1 is 1e+308 per calendar day, expected a finite quantity for the period; times its 31 days it outruns the largest number` |
| the observations and their pricing contracts by the pipeline's rules, each refusal naming the row and the window as a booking names it | `F27 of row 1 has no pricing day from 2027-01-01 to 2027-01-31, expected a Monday to Friday of the days it covers the index's market is open on; the asian method averages the pricing days a component covers`; `the window of row 1 has no pricing day from 2027-01-30 to 2027-01-31, expected ...` |
| the request's payment days dates alone; each payment day after its component's last observation, the template's or the request's, a window named by its dates | `payment_day row 2 is '+5bd', expected a date; a request's rows pay on dates, and a rule is the template's to hold`; `F27 of row 1 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its final price exists`; `2027-01-11 to 2027-02-26 of row 1 pays on 2027-02-26, expected a day after its last observation, 2027-02-26, when its final price exists` |
| `_QuoteRFQ`: the market's index is the request's, the one object, before any data is gathered; the collection supplied with a bilateral request and left out with a cleared one, the key bound and the curve starting on the valuation day; then the quote's own market rules, a day before the calendar, a contract beyond the market's coverage, an expired physical contract and a payment past the curve, [quote.md](quote.md) | `market is over another index, 'TOY_GAS', expected the request's, 'STRIP'`; `discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, whose payments it discounts`; `the payment of 2027-01-11 to 2027-02-26 on 2027-03-08 on SOFR is past the discount curve 'SOFR', which runs from 2026-12-31 to 2027-03-05; expected every payment day after the valuation date covered` |

## What it retains

```text
Rfq
    template            the quote template, by reference
    rows                how many rows the ticket held
    occurrence          each component's entered row, in row order
    quantity            the entered quantities, one per row, finite and zero or more
    component_quantity  each component's quantity by the template's basis, the entered column by
                        reference where every row is one component
    payment_source      template, request, or None for a physical request
    request             Request: the index and its schedule, the terms, the period, each component
                        a row of the schedule with the days it covers and whether it is a window,
                        the observations and each one's pricing reference, the component
                        quantities themselves, and the payment days, None for physical
```

No history, price, factor, curve or valuation day: those are the market's and the collection's, read when the request is priced, so a price tick, a corrected fixing, a valuation day rolled or a new collection reprices the same request and nothing of its periods, observations or payments is made again, and no fixed or live flag is saved that a later day would outdate. An as-of change never shortens the request; a component whose payment has passed stays in the price at its realized price and factor one, as in the quote, and a window's dates stand as entered, never turned into a balance.

## Reading it back

`util_ReadHandle` on the handle spills one row per component in row order, under two heading rows: `row`, the entered row the component came from, counted from one; `period`, the component's contract code in the schedule's spelling or a window's two dates; `quantity`, as its row entered it; `quantity_per`; `component_quantity`, the component's quantity by the basis, the calendar-day effect visible; `payment_source`, `template` or `request`; `payment_date`, the component's effective day, the source's; then the request's facts on every row so that a row reads whole, `index`, `schedule_method`, `route`, `settlement_method`, `quote_unit`, `USD per BBL`, `discount_curve_key`, a dash on the cleared route, `settlement_frequency` and, since [nearby-selection.md](../../engineering-tickets/trade-valuation-pipeline/nearby-selection.md), `nearby`, the template's whole number. A physical request shows a dash for the source and the date. A dated row under `monthly` reads as one row per month, each carrying the row's number; nothing is priced and no factor is shown.

## Work

The request reports what it did in the quote's counters: at creation the template's values read, the schedule's codes read, the ticket's distinct codes read, the months resolved, one per component, or under `onetime` the windows resolved, one per row, the observations made, the payment rule read and its instructions applied once over the components and the payment days made, none of the rule and no shift for the request's own dates; nothing of a history, a price, a curve or a factor. A quote of the request reports the curve selected, the fixings read, one per fixed observation, the live prices read, one per distinct live contract, the payment factors read, one per distinct payment day ahead, and four reductions, and resolves nothing: no period, observation or payment is made again on a tick. The budgets under `tests/performance` pin the counts, the functions each step runs once, the retained bytes, 32 an observation and 49 a component, and the peaks.

## Not here

Mixed quantity units, signed or spread quantities, bid and ask, several indexes or several keys in one request, a method, route, basis or frequency per row, a rule per row in the payment column, a partial column of dates or a single date broadcast, a balance in a row, horizontal ranges, booking or accepting a request, a quote's risk, a result handle or reader, a cache or any override of another field: the tickets' deferred lists, for UAT to weigh. A request books nothing and changes nothing: the index, the template, the market, the collection and its curves are read-only inputs.
