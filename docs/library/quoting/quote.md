# _Quote

Built from [template-based-quoting.md](../../engineering-tickets/trade-valuation-pipeline/template-based-quoting.md), with [_CreateQuoteTemplate](quote-template.md). One whole-period indicative fixed price for a contract or strip on one market from a quote template's static terms, in the index's quote units: the fair fixed price making the equivalent trade's mark zero while every payment is still ahead, and with payments elapsed the same whole-period price under the convention below. A number, not a handle; nothing is booked, retained or reported. The code is `src/goosedove/quoting/quote.py`, the calculation, and `src/goosedove/excel/quoting.py`, the worksheet function.

## Worksheet contract

```python
def _Quote(
    market: Handle[Market],
    contract_code: str,
    template: Handle[QuoteTemplate],
    discount_curve_set: Handle[DiscountCurveSet] | None = None,
) -> float: ...
```

The ticket's example, the market in a cell named `ngl_market`, the templates in cells named for them and the collection of named curves in `rates`:

```excel
=_Quote(ngl_market, "CAL27", ngl_otc_template, rates)
=_Quote(ngl_market, "CAL27", ngl_cleared_template)
```

The first three arguments are required. The market is the one of [_CreateMarket](../market/market.md), the history it follows supplying the index, the valuation day, the calendar and the fixings, and its vector the day's quotes. The contract code is one month or a strip in the period grammar behind [util_StartDate](../utilities/start-date.md), `Z26`, `z26`, `F27-G27`, `1H27`, `CAL27`, or since [balance-of-period-quotes.md](../../engineering-tickets/trade-valuation-pipeline/balance-of-period-quotes.md) the balance of one, `BALZ26`, `BALCAL27`, read from the market's valuation day as the two date utilities read it, every month of it a contract of the market's schedule; a pair of dates is not a quote's period. The template is a quote template and no other kind, [quote-template.md](quote-template.md); a trade template is refused by its kind, `template is trade template handle '30512:trade_template:40', expected quote template handle`. The fourth argument is the collection of [_CollectDiscountCurves](../globals/collect-discount-curves.md), required when the template's route is bilateral and left out when it is cleared; a blank cell in its place is a blank, not a left-out argument, the seam's rule. The seam checks the declared types, [inputs.md](../../seam/inputs.md) and [outputs.md](../../seam/outputs.md), and the cell shows the number.

## Excel help

| Item | Text |
|---|---|
| Function | Quotes one whole-period fixed price for a contract or strip on one market from a quote template's terms, fixings for the observations that have passed and the day's quotes for the rest, a bilateral payment discounted on the template's curve. |
| market | The market handle: the cell showing _CreateMarket's result, such as I12, or a name for it, with the day's quotes over the history they follow. |
| contract_code | The contract, strip or balance to quote, such as Z26, F27-G27, CAL27 or BALZ26, the balance from the market's valuation day, every month of it a contract of the market's schedule. |
| template | The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as B3, or a name for it, which supplies the quote's terms. |
| [discount_curve_set] | The collection handle for a bilateral quote: the cell showing _CollectDiscountCurves's result, such as I13, or a name for it, holding the curve the template names; left out for a cleared quote. |

## The price

For each month `i` of the period, its floating price is its observations' weighted prices, the weights the schedule method's own, summing to one; its relative quantity is 1 for `quantity_per = month` and its calendar days, weekends and holidays included, for `calday`; and its payment factor is 1 on a cleared quote, 1 on a bilateral quote whose payment falls on or before the valuation day, and the selected curve's factor on its payment day otherwise.

```text
P_i = sum_j(weight_ij * price_ij)
q_i = 1, or the calendar days of month i
D_i = 1 cleared; 1 bilateral with payment_i <= as_of; curve(payment_i) bilateral otherwise
K   = sum_i(q_i * D_i * P_i) / sum_i(q_i * D_i)
```

The factors weight both sums, so one month with one payment quotes the same price cleared or bilateral, and a common factor on every payment cancels too; two months paying on different days do not, so a cleared price cannot be passed on to recover the bilateral one. A common quantity or unit scale cancels, and `calday` weights the months without touching the method's weights within a month: pricing days are never calendar days.

Each month's share of the price is its weight, quantity times factor, over the weights' sum, and the price is the shares' sum of the months' prices: a convex combination at each step, the observations' weights summing to one and the shares to one, so no product or sum runs past the largest number a finite input stays within, and a factor as small as the curve allows, positive by the curve's rule, scales nothing away; one month's share is one whatever its factor, which is the single-payment cancellation above. The quote refuses no arithmetic of its own: what a cell may hold is the seam's rule and a curve's factors the curve's.

Every month of the period stands in both sums whether its payment has passed, falls today or lies ahead, the agreed full-period convention: CAL27 quoted in June 2027 has January through May at their realized prices and factor 1, June at its fixed and live observations under its own payment's factor, and July through December at the day's quotes; it is never a seven-month quote, a balance of the year or a renormalization over the live observations, and a month's fixing state and its payment's timing are two facts, `payment_date <= as_of` deciding the factor and never `observation_date <= as_of`. Including paid months at factor 1 undoes no settled cash and claims nothing of a past cashflow's value; the zero-mark comparison with [_EvaluateTrades](../trades/evaluate-trades.md) holds while every payment is ahead.

## The balance of a period

Since [balance-of-period-quotes.md](../../engineering-tickets/trade-valuation-pipeline/balance-of-period-quotes.md) the request may be the balance of any label the quote accepts, `BALZ26` or `BALCAL27` in either case, read exactly as [util_StartDate](../utilities/start-date.md) and [util_EndDate](../utilities/end-date.md) read it with the market's valuation day: from the later of that day and the period's first day to the period's last day. A period still ahead is the whole period, so `BALG27` asked in January is `G27`; the balance of the current period runs from the valuation day itself, which is live; a period that has ended is refused in the utilities' words. A balance is asked for by name and never inferred: `CAL27` in June keeps every month, and `BALCAL27` in June is the seven months left.

The span is split at month ends into components, the first and the last month clipped to the days the span covers, as a ticket row booked by dates is. The components then follow the rules a dated row meets: a part of a month prices under `asian` alone, its observations the pricing days within the balance, and is refused under `lastday`, `penultimate` and `last3day`, and on an IFERC index, whose month is one price; a component whose remaining days hold no pricing day is refused, and an empty first component refuses the whole strip rather than dropping it. Per month, a partial month weighs one, as the booking model weighs it; per calendar day it weighs the days the balance covers. Payments count from each component's last observation as before, so a balance pays on the day the whole month would.

On the strip of the tests, valued Monday 11 January 2027 with the 4th to the 8th fixed at 25 and F27 live at 29: `F27` quotes 28 and `BALF27` the fifteen live days alone, 29; `BALF27-G27` with G27 at 60 quotes 44.5 per month and 2289/49 per calendar day, January's balance covering 21 days against February's 28. On the calendar-year index valued 16 June: `BALCAL27` quotes June from its eleven live days alone, 42, and the six months after at 40, 282/7 per month and 7990/199 per calendar day; on a curve at 0.98 for every payment ahead the bilateral quotes equal those, every payment carrying one factor, where `CAL27`'s paid months at factor one keep it at 424.4/11.86. An equivalent trade booked on the balance's own dates at the quote marks zero on either route under either basis.

## The library checks

The rules in this order, the first failure being the cell's text after `#ERROR _Quote: ValueError:`.

| Check | Refused as |
|---|---|
| the template holds every term a completed quote requires, the `quote_required` and `quote_required_when` rows of [_ShowInstrument](../instruments/show-instrument.md): the four codes always, the two payment fields with a financial settlement and the curve key on the bilateral route, each conditional field present exactly when its condition holds; a physical settlement on the cleared route alone | `schedule_method is missing, expected it in the quote template`; `discount_curve_key is missing, expected it in the quote template when route = bilateral`; `payment_time_lag is '+1bd', expected none in the quote template unless settlement_method = financial`; `settlement_method is 'physical', expected 'financial' with route = bilateral; a physical delivery has no payment to discount` |
| the collection is supplied with a bilateral quote and left out with a cleared one; the template's key names a curve of the collection, exactly, case and all, no fallback to the first curve, a collection of one included; the selected curve starts on the valuation day, never rebased | `discount_curve_set is missing, expected a collection of discount curves holding 'SOFR' with route = bilateral, whose payments it discounts`; `discount_curve_set is a collection of 2 curves, expected none with route = cleared; a cleared quote discounts nothing`; `discount_curve_key 'SOFR' names no curve of the collection, which holds 'FFOIS'; expected a curve of that name`; `discount curve 'LATE' starts on 2027-01-04, expected 2026-12-31, the valuation date; a curve is never rebased` |
| the market's index takes the terms: a futures or an IFERC index, an IFERC index with a financial settlement and lastday, a physical settlement with lastday alone | `index is a Gas Daily index, expected a futures or an IFERC index for a fixed_float`; `schedule_method is 'asian', expected 'lastday' on an IFERC index; an IFERC month has one index, published once`; `settlement_method is 'physical', expected 'financial' with the asian method; an asian future is cash settled on the average of its month's pricing days` |
| every month of the period is a contract of the schedule, through the period grammar; a balance from the valuation day, a period that has ended refused as the date utilities refuse it | `contract_code is 'CAL28', expected months the index's schedule has a contract for; it has none for 2028-01`; `contract_code is 'Z2027', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28`; `valuation_date is 2027-02-01, after 'BALF27' ended on 2027-01-31, expected a valuation day on or before the period's last day` |
| a balance that cuts a month prices under asian alone and holds a pricing day, the observations' own rules for a dated row | `F27 of the quote is covered from 2027-01-11 to 2027-01-31, part of its month, expected the whole month under lastday; the expiry-based methods take the contract's month entire, and a part of it prices under asian`; `F27 of the quote has no pricing day from 2027-01-30 to 2027-01-31, expected a Monday to Friday of the days it covers the index's market is open on; the asian method averages the pricing days a component covers` |
| the observations, their pricing contracts and their calendar rows by the batch's rules, [create-trades.md](../trades/create-trades.md): a closed expiry, a day beyond the schedule, a day before the calendar; a fixed day's price off the history, which holds one for every fixed priced day, and a live day's off the market's quotes, each distinct live contract once, within the market's coverage, [market.md](../market/market.md) | `F27 observes 2027-01-28, a day the index's market is closed; no settle exists or will`; `requested contract 'G27' is beyond live-price coverage ending at 'F27'` |
| a financial quote's payments, each month's rule applied to its last observation day on the payment calendar, [compound-date-offsets.md](../../engineering-tickets/trade-valuation-pipeline/compound-date-offsets.md), the expiry under lastday on a futures index and the publication day on an IFERC one, [iferc-publication-payment-anchor.md](../../engineering-tickets/trade-valuation-pipeline/iferc-publication-payment-anchor.md): within the sheet's calendar and after that observation, when the month's final price exists; a physical quote's contracts not yet expired, the expiry day itself live | `F27 pays on 2027-01-29, expected a day after its last observation, 2027-01-29, when its final price exists`; `F27 expired 2027-01-29, before valuation date 2027-02-01; a physical fixed_float after its expiry is not supported` |
| the selected curve covers every payment day after the valuation day; a payment on or before it reads no factor, so a curve starting on the valuation day need not cover the months already paid | `the payment of Z27 on 2028-01-03 on SOFR is past the discount curve 'SOFR', which runs from 2027-06-16 to 2027-12-31; expected every payment day after the valuation date covered` |

A fully fixed period reads no live price, a period whose every payment has passed reads no factor, and a bilateral quote binds its key and checks its curve's start either way. An unused curve of the collection is read for nothing: another start or a shorter span fails nothing until that curve is selected. A rates change is a new curve and a new collection over the same template and market; for a bump scenario the collection holds [util_BumpDiscountCurve](../utilities/bump-discount-curve.md)'s curve in place of the base, never both, since both carry the name and the collection refuses the repeat.

## Work

The quote reports what it did, in the counters the pipeline's stages use for the same facts: the template's values read, the schedule's codes read, the months resolved, the observations made, the fixings read, one per fixed observation, the live prices read, one per distinct live contract, the payment rule read and its instructions applied once over the months, the payment days made, the curve selected and the payment factors read, one per distinct payment day after the valuation day, and three reductions whatever the strip. Each request is resolved whole on every call; nothing is cached between calls, and an unchanged call recomputes the same number.

## Tests

| Case | Where |
|---|---|
| the ticket's worked acceptance by hand: the cleared and bilateral strip on month and calendar-day weights, January alone, the prices reversed; the key selecting its curve, the collection reordered, a flat factor cancelling, the selected curve updated alone, an unused curve never read, a bumped curve in place of the base; a payment holiday moving one factor; fixings and live prices sharing a month, 28, 28.75 and 28.10; an asian month rolling with the calendar, 1582/22, before and after the roll; lastday, penultimate and last3day with a holiday before the expiry, a month and a strip; an IFERC month observing its publication day and paying from it under both routes; a leap February; a fully fixed month discounting its unpaid payment and a payment on the valuation day taking 1; a physical quote before and after the expiry; CAL27 in June27, 430/12, 424.4/11.86, 13090/365 and 12918.8/360.72, a fixing correction, a live move, a factor move, the paid months alone and the curve's coverage | `tests/unit/test_quote.py` |
| the template's terms complete and agreeing before anything is priced; the collection required or refused; the period, the market, the payment and the Gas Daily index refused in their words; zero and negative prices and cents a gallon; extreme but finite inputs priced as exact convex combinations, a factor of 1e-300 and prices of 1e308 among them; an equivalent trade booked at the quote marking zero on either route; the page's example through the seam and the seam's refusals, a blank fourth cell among them | the same |
| the balance of a period by hand: `BALF27` the live days alone, the strip's balance per month and per calendar day on both routes, `BALCAL27` the seven months left and equal to the cleared on a flat curve, a balance still ahead the period; a period that has ended, a cut month under the expiry-based methods and on an IFERC index, a balance with no pricing day and the strip it heads, a bad label under the prefix; an equivalent trade booked on the balance's dates at the quote marking zero on either route under either basis | the same |
| the work of a month, a year and the balance of a year, the functions run once, and the peak, measured | `tests/performance/test_quote_budgets.py` |

## Not here

Bid, ask and theoretical sets, executable prices and depth, a quote's risk or decomposition, a readback of the resolved months, several indexes or several keys in one quote, a custom quantity profile, a dated request, fees and reserves in the price, credit or funding adjustments, a curve built from rates, and any cache: the ticket's deferred list, for UAT to weigh. A quote books nothing and changes nothing: the template, the market, the calendars, the collection and its curves are read-only inputs.
