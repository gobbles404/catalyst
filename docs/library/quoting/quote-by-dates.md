# _QuoteByDates

Built from [dated-quotes.md](../../engineering-tickets/trade-valuation-pipeline/dated-quotes.md), beside [_Quote](quote.md), which prices a label, and with [_CreateQuoteTemplate](quote-template.md). One indicative fixed price for the days from one date to another on one market from a quote template's static terms, in the index's quote units, the price [_Quote](quote.md) gives a label: the fair fixed price making the equivalent trade's mark zero while every payment is still ahead, and with payments elapsed the same whole-period price under the quote's convention. The template's `settlement_frequency` says what the days are. Under `onetime` they are one calculation period, one average over every pricing day of the window whatever months it crosses, the trade-month window of [onetime-averaging.md](../../engineering-tickets/trade-valuation-pipeline/onetime-averaging.md) among them; under `monthly` they are a dated strip, split at month ends into components as a ticket row booked by dates is split. A number, not a handle; nothing is booked, retained or reported. The code is `src/catalyst/quoting/quote.py`, the two entries and their one path, `src/catalyst/quoting/request.py`, the period a label and two dates resolve through, the frequency's rules, the request and the price, and `src/catalyst/excel/quoting.py`, the worksheet function.

## Worksheet contract

```python
def _QuoteByDates(
    market: Handle[Market],
    start_date: Date,
    end_date: Date,
    template: Handle[QuoteTemplate],
    discount_curve_set: Handle[DiscountCurveSet] | None = None,
) -> float: ...
```

The trade month, the market in a cell named `wti_market` and the templates in cells named for them:

```excel
=_QuoteByDates(wti_market, DATE(2026,5,26), DATE(2026,6,25), wti_onetime_template)
=_QuoteByDates(wti_market, DATE(2026,5,26), DATE(2026,6,25), wti_monthly_template)
```

The first four arguments are required. The market is the one of [_CreateMarket](../market/market.md), the history it follows supplying the index, the valuation day, the calendar and the fixings, and its vector the day's quotes. The two dates are the first and the last day the quote covers, both inclusive, dates and never text, a blank cell refused as a blank, the end on or after the start; a label is [_Quote](quote.md)'s period and a pair of dates this function's, and neither reads the other's. The template is a quote template and no other kind, [quote-template.md](quote-template.md), its `settlement_frequency` choosing between the window and the strip; a trade template is refused by its kind. The fifth argument is the collection of [_CollectDiscountCurves](../globals/collect-discount-curves.md), required when the template's route is bilateral and left out when it is cleared; a blank cell in its place is a blank, not a left-out argument, the seam's rule. The seam checks the declared types, [inputs.md](../../seam/inputs.md) and [outputs.md](../../seam/outputs.md), and the cell shows the number.

## Excel help

| Item | Text |
|---|---|
| Function | Quotes one fixed price from start_date to end_date on one market from a quote template's terms, one average over the window under onetime and a strip by the month under monthly, fixings for the days passed and the day's quotes for the rest. |
| market | The market handle: the cell showing _CreateMarket's result, such as I12, or a name for it, with the day's quotes over the history they follow. |
| start_date | The first day the quote covers, such as A2 or DATE(2026,5,26). |
| end_date | The last day it covers, inclusive, such as B2 or DATE(2026,6,25), on or after start_date. |
| template | The quote-template handle: the cell showing _CreateQuoteTemplate's result, such as B3, or a name for it, whose settlement_frequency makes the days one average or a strip by the month. |
| [discount_curve_set] | The collection handle for a bilateral quote: the cell showing _CollectDiscountCurves's result, such as I13, or a name for it, holding the curve the template names; left out for a cleared quote. |

## What the days are

Each input keeps its own duty. The two dates give the inclusive period. The template's `schedule_method` says which prices are observed, `settlement_frequency` whether the days are separate monthly calculations or one calculation across the window, `quantity_per` how the quantity applies, and `payment_day` when each resulting amount pays. Supplying dates chooses no averaging frequency: the same dates under two frequencies are two quotes.

**Under `onetime`** the days are one component, the window. The kernel's rule over the frequency holds, [kernel.md](../trades/kernel.md): a futures index, a financial settlement, the `asian` method and a quantity per `period`, the window's total, or `calday`, so that the window is the same contract a `onetime` ticket row books. Its schedule row is the contract pricing its first day, the first whose expiry is on or after it, as the calendar gives a day its contract, found by the one search a booking's windows take and read for nothing that prices, so no contract is needed for the month the window opens in; the observations are every pricing day of the window, an equal share each, every day priced by the contract the calendar gives it, N26 through its expiry on 22 June and Q26 after; the payment is the template's date, or its rule counted from the window's final observation. One component has one quantity and one payment, so the quantity cancels, `period` and `calday` quoting alike, and the factor cancels, cleared and bilateral quoting alike.

**Under `monthly`** the days are a dated strip. The span is split at month ends, the first and the last month clipped to the days given and a month between them whole, every month a contract of the schedule, each month its own average over its own days, its quantity one per `month` or its covered calendar days per `calday`, and its payment the template's date on every month or its rule from its own last observation, as [_Quote](quote.md)'s balance of a period is split and as a dated booking row is. A part of a month prices under `asian` alone and is refused under the expiry-based methods.

The trade month, 26 May to 25 June 2026, on the WTI-like index of the tests with N26 at 70 and Q26 at 72 before any day fixes, has 22 pricing days, four in May and eighteen in June, N26's nineteen through its expiry and Q26's three. Cleared:

| Template | What is priced | Quote |
|---|---|---:|
| `monthly`, `month` | May's four days at 70 and June's eighteen at 70.333333, in equal quantities | 70.166667 |
| `monthly`, `calday` | the two portions weighted 6 and 25 calendar days | 70.268817 |
| `onetime`, `period` or `calday` | one average of the 22 fixings, `(19 * 70 + 3 * 72) / 22` | 70.272727 |

Two things hold these numbers to the cleared route or to equal factors. Each monthly portion pays from its own final observation when the payment is a rule, so a bilateral dated strip weighs each portion by its payment's factor as well: paying +2bd on 2 June and 29 June at 0.995 and 0.99, the strip quotes `(0.995 * 70 + 0.99 * 70.333333) / (0.995 + 0.99)`; an explicit common payment date pays both portions together and keeps their averages apart, and the factor cancels again. The window pays once whatever the template says, so its one factor never matters.

As days fix the window keeps its weights: on 10 June, eleven days fixed at 69 and eight N26 days and three Q26 days ahead, it quotes `(11 * 69 + 8 * 70 + 3 * 72) / 22`, 69.772727; fully fixed it quotes the realized average and reads no live price; a corrected fixing moves it. The dates stand as entered as the valuation day moves, never turned into a balance of the days left, which a label asks for by name, `BALK26`, and two dates cannot. Booking the equivalent row at the quote, the same dates, index, method, basis, frequency, payment and curve, marks zero on either route while every payment is ahead, fees and reserves apart; that is the test's check and the desk's.

## The library checks

The rules in this order, the first failure being the cell's text after `#ERROR _QuoteByDates: ValueError:`. The template's completeness, the collection, the index's terms, the observations' calendar rows, the prices and the curve's coverage are [_Quote](quote.md)'s own checks in its own words; the rows below are this function's.

| Check | Refused as |
|---|---|
| the frequency with the terms it stands under, the kernel's rule over the template's one set of terms, the quote named in the trade's place: `onetime` on a futures index, financially settled, under `asian` and per `period` or `calday`; `monthly` per `month` or `calday` | `settlement_frequency of the quote is 'onetime', expected 'monthly' on an IFERC index; an IFERC month has one index, published once, and a onetime period averages the pricing days of a futures index`; `settlement_method is 'physical', expected 'financial' with settlement_frequency = onetime of the quote; a onetime period is cash settled on its average`; `schedule_method of the quote is 'lastday', expected 'asian' under settlement_frequency = onetime; a onetime period averages every pricing day it covers, and the expiry-based methods take their contract's month`; `quantity_per of the quote is 'month', expected 'period' or 'calday' under settlement_frequency = onetime; month says nothing of a window, period is its total and calday its days`; `quantity_per of the quote is 'period', expected 'month' or 'calday' under settlement_frequency = monthly; period is the total of a onetime period and says nothing of a month` |
| the end on or after the start | `end_date is 2026-05-26, expected a day on or after start_date, 2026-06-25` |
| the period: under `monthly` every month of the days a contract of the schedule; under `onetime` a window opening on or before the last day the schedule's contracts price, which no contract's month decides | `start_date is 2026-05-26 and end_date 2026-06-25, expected months the index's schedule has a contract for; it has none for 2026-05`; `start_date is 2027-04-01 and end_date 2027-04-30, expected a window priced by the contracts of the index's schedule; it opens on 2027-04-01, after the last day they price, 2027-03-22` |
| the observations, the pipeline's rules for a dated row, the window named as the batch names it | `the window of the quote has no pricing day from 2026-05-30 to 2026-05-31, expected a Monday to Friday of the days it covers the index's market is open on; the asian method averages the pricing days a component covers`; `F27 of the quote is covered from 2027-01-11 to 2027-01-31, part of its month, expected the whole month under lastday; the expiry-based methods take the contract's month entire, and a part of it prices under asian` |
| the payments after each component's final observation, a window named by its two dates, and the curve covering every payment ahead | `2026-05-26 to 2026-06-25 pays on 2026-06-25, expected a day after its last observation, 2026-06-25, when its final price exists`; `the payment of 2026-05-26 to 2026-06-25 on 2026-06-29 on SOFR is past the discount curve 'SOFR', which runs from 2026-05-20 to 2026-06-26; expected every payment day after the valuation date covered` |

[_Quote](quote.md) keeps its label and its month: a `onetime` template under it is refused by name, `settlement_frequency is 'onetime', expected 'monthly'; a quote by contract code prices by the month, and _QuoteByDates prices a onetime period across two dates`. A request's rows take dates and follow the template's frequency as this function does, [rfq.md](rfq.md), a one-row window quoting the same number.

## Work

The quote reports what it did in the counters [_Quote](quote.md) uses for the same facts. Under `onetime` the window is resolved once, `windows_resolved`, one search over the days the schedule's contracts price on and no code read for a month; under `monthly` the schedule's codes are read and the months resolved as the label's are. Then the observations made, the fixings read, one per fixed observation, the live prices read, one per distinct live contract, the payment rule read and applied once over the components, the payment days made, one for a window, the curve selected and the factors read, one per distinct payment day ahead, and four reductions. Each call resolves the span whole; nothing is cached between calls.

## Not here

A label under a `onetime` template, which [_Quote](quote.md) refuses by name; several windows at their own quantities and payment days, which a request for quote's rows are, [rfq.md](rfq.md); a window on two indexes, physically settled or on an IFERC index, which the kernel's rule refuses; a named trade-month window made from a contract code, a payment anchored on a strip's final observation across monthly components, bid and ask, a readback of the resolved components, fees and reserves in the price, and any cache. The quote books nothing and changes nothing: the template, the market, the calendars, the collection and its curves are read-only inputs.
