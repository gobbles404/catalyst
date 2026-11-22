# _CreateQuoteTemplate

Built from [template-based-quoting.md](../../engineering-tickets/trade-valuation-pipeline/template-based-quoting.md), with [_Quote](quote.md). The static terms of a quote under the `fixed_float`'s definition, created once and taken by every quote made under it beside the market and the contract code the quote prices: the fields a quote reads, held as a trade template holds its defaults, and none of the booking facts, so a quote template books nothing and a trade template quotes nothing. The code is `src/catalyst/quoting/template.py`, the record and its builder, and `src/catalyst/excel/quoting.py`, the worksheet function.

## Worksheet contract

```python
def _CreateQuoteTemplate(
    instrument: str,
    fields: TextRow,
    values: FieldRow[str],
    holiday_calendars: Handle[HolidayCalendars] | None = None,
) -> Handle[QuoteTemplate]: ...
```

The ticket's bilateral example, seven fields:

| | A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|---|
| 1 | route | settlement_method | schedule_method | quantity_per | payment_day | payment_holiday_key | discount_curve_key | settlement_frequency | nearby |
| 2 | bilateral | financial | asian | calday | +5bd | NYFED+LON | SOFR | monthly | 1 |
| 3 | `=_CreateQuoteTemplate("fixed_float", A1:I1, A2:I2, B4)` | shows `30512:quote_template:41` | | | | | | | |
| 4 | | `=_CollectHolidayCalendars(K1:K2)` | the collection holding `NYFED` and `LON` | | | | | | |

`nearby`, since [nearby-selection.md](../../engineering-tickets/trade-valuation-pipeline/nearby-selection.md), is the contract each observation day is priced by, counted from the day's prompt, required of every quote template as `settlement_frequency` is; a quote, a quote by dates and a request for quote price it as a batch does, a number above 1 under `asian` on a futures index, financially settled, [quote.md](quote.md).

A cleared financial template has `route` cleared, no `discount_curve_key` and otherwise the same terms; a cleared physical one `settlement_method` physical, `schedule_method` lastday and no payment fields.

Four arguments, the first three required and none of them with a default, in [_CreateTradeTemplate](../trades/trade-template.md)'s forms, and since [payment-calendar-keys.md](../../engineering-tickets/trade-valuation-pipeline/payment-calendar-keys.md) the collection of holiday calendars the row's `payment_holiday_key` selects from, the cell showing [_CollectHolidayCalendars](../index-definitions/collect-holiday-calendars.md)'s result, given where the row holds a key and left out where it holds none: the instrument first, one exact name from `_ListInstruments`, `fixed_float`, the one instrument a quote prices; the fields one row of names as `_ShowInstrument` shows them, spelled exactly, case and all, in any order; the values one aligned row beneath them. One field takes the same path as seven, and a template carries at least one. The row crosses as `FieldRow[str]`, bound against the instrument named: the seam checks the name's type, the width, each header against the definition, unknown and repeated headers named, and each cell by its field's type, a code and `payment_holiday_key` as text, no field taking a handle since [payment-calendar-keys.md](../../engineering-tickets/trade-valuation-pipeline/payment-calendar-keys.md); more than one row of values is refused by its shape before any cell is looked at. The result is a handle, `30512:quote_template:41`, the kind and the count alone, since a quote template carries no index's name, [handles.md](../../seam/handles.md). An unchanged recalculation shares the live template; a changed cell under it, a value or the collection, which a changed calendar remakes, makes a new one and every quote over it anew, the old released when Excel disconnects its last creator.

## Excel help

| Item | Text |
|---|---|
| Function | Creates the static terms of a quote under an instrument and shows their handle, the text _Quote takes as the quote template. |
| instrument | One instrument name from _ListInstruments; fixed_float, the one a quote prices. |
| fields | The field-name cells in one row, such as A1:G1, using names _ShowInstrument marks quote_allowed. |
| values | The values in one row beneath those fields, such as A2:G2. |
| [holiday_calendars] | The collection payment_holiday_key selects from: the cell showing _CollectHolidayCalendars's result, such as B4. Leave it out where the row holds no payment_holiday_key. |

## The library checks

Which fields a quote template may hold is the definition's own metadata, the `quote_allowed` row of [_ShowInstrument](../instruments/show-instrument.md): the four codes, the curve key and the two payment fields, and no other. The checks come in this order, the first failure being the cell's text after `#ERROR _CreateQuoteTemplate: ValueError:`.

| Check | Refused as |
|---|---|
| the instrument is one a quote prices, `fixed_float`; the cashflow has no quote | `instrument is 'cashflow', expected one a quote prices: 'fixed_float'` |
| each header, in the sheet's order and before any value is read, is a field a quote template may hold: a booking fact, the identifiers, the dates, the quantity and its unit, the price, the labels and the reserve, is refused by name, and so is a period field, `contract_code`, `start_date` or `end_date`, whose cell may be blank for a trade template and is refused here whatever it holds, since the quote's own contract code argument owns the period | `quantity is a field of booking alone, expected one a quote template holds: schedule_method, route, settlement_method, discount_curve_key, quantity_per, payment_day, payment_holiday_key, settlement_frequency, nearby` |
| each value, read once for the rule intrinsic to its field by the trade template's readers, [trade-template.md](../trades/trade-template.md) the table of them: a code from its list, a payment day as the date it holds or as a rule read whole, a curve key with no whitespace around it, a payment holiday key for its form | `route is 'Cleared', expected cleared or bilateral`; `payment_day is '2bd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd`; `discount_curve_key is ' SOFR', expected a name with no whitespace around it` |
| a `payment_holiday_key` the row holds is bound to its calendar, once, by the step a batch of trades shares, [collect-holiday-calendars.md](../index-definitions/collect-holiday-calendars.md#binding-a-key): one name the collection's calendar itself, several joined by `+` the calendar closed on every day any of them is closed; a row holding a key needs the collection, and a row holding none binds nothing | `payment_holiday_key is 'TOK', expected names of the collection's calendars, 'NYFED' and 'LON'; it holds no 'TOK'`; `holiday_calendars is missing, expected a _CollectHolidayCalendars collection, which payment_holiday_key selects its payment calendar from` |
| a payment day held as a date, since [payment-day-date-or-rule.md](../../engineering-tickets/trade-valuation-pipeline/payment-day-date-or-rule.md), is kept as the day and serves any request whose last observation falls before it, every month then paying on the day; a month observing on or after it is refused by the quote, by the month, the comparison being with the observation day and not the period's end, so the template is not one deal's | `H27 pays on 2027-03-15, expected a day after its last observation, 2027-03-31, when its final price exists` |

Nothing is required of a template, which is a partial record. Which terms a completed quote needs, the five codes always, the payment fields with a financial settlement and the key on the bilateral route, as the `quote_required` and `quote_required_when` rows say, and whether the terms agree with one another and with the index and the market, are [_Quote](quote.md)'s checks, against the template, the contract code and the market together. So a key beside a cleared route, or a lag beside a physical settlement, is held here as typed and refused when a quote is made. Since [rfq-quoting.md](../../engineering-tickets/trade-valuation-pipeline/rfq-quoting.md) a request for quote's own payment dates stand in for the template's `payment_day`, [rfq.md](rfq.md), the payment calendar required still, and the template holds its default for every other quote.

## What it retains

```text
QuoteTemplate
    instrument   the library's fixed_float definition, by reference
    names        the fields the row named, in the sheet's order
    values       by field name, in the same order: route bilateral, settlement_method financial,
                 schedule_method asian, quantity_per calday, settlement_frequency monthly,
                 nearby 1, payment_day +5bd,
                 payment_holiday_key NYFED+LON, discount_curve_key SOFR
    payment_calendar   the calendar the key selected when the template was made, here the
                 one closed on every day NYFED or LON is closed; none where the row held no key
```

Each value is the one the row held: a code, a payment rule, the curve key and the payment holiday key as the text typed. The calendar the key selected is held beside them, bound once when the template is made and held by reference, so that a quote and a request for quote count their payment days on it and look no name up. The curve key is static text; the curves themselves reach `_Quote` as its own argument, so new rates make a new collection and never a new template. No index, no market, no period and no quantity: a template serves every compatible index, and the quote's own arguments supply the rest. The template is no selector of an instrument for booking: `_CreateTrades` and `_CreateCashflows` take a trade template and refuse this kind, `template is quote template handle '30512:quote_template:41', expected trade template handle`, and a consumer of a quote template refuses a trade template the same way.

## Reading it back

`util_ReadHandle` on the handle spills one row under two heading rows, as a trade template's does: `instrument` first, `fixed_float`, then each field the row named under its name in the sheet's order, text as typed, the payment holiday key among it; every cell holds a value, since no period field may stand in a quote template.

## Tests

| Case | Where |
|---|---|
| the ticket's bilateral example of seven fields, a cleared financial six and one field take one path; each value read once by the trade template's reader and kept as typed, the payment holiday key bound to the collection's calendar or to the union of several; a key beside a cleared route held, for the quote to refuse; the builder takes one row | `tests/unit/test_quote_template.py` |
| every booking field and the three period fields refused by name whatever the cell holds, a blank among them; the first refused header in the sheet's order named before any value is read; the cashflow refused as no instrument a quote prices | the same |
| the seam's refusals in order, then the library's for each of the seven fields' rules; the creator's handle, the kind and the count alone; the reader's spill; a quote template refused by its kind in `_CreateTrades` and `_CreateCashflows`, and a trade template where a quote template is taken; one handle per creation and none for a read | the same |
| one read per value and one publication; the peak within four times the seam's slack | `tests/performance/test_quote_budgets.py`, `test_seam_allocation.py` |

## Not here

The quote itself, what it requires of the template, how it prices and what it refuses: [quote.md](quote.md). Booking under a quote template. A quantity, a fixed price, a label, a reserve, an index or a market on the template; a second quote instrument; a reader of what a completed quote resolved.
