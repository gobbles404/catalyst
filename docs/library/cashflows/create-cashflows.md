# _CreateCashflows

A batch of cashflows: known signed amounts in one currency, each on its own explicit payment day, booked from a template of the `cashflow` instrument and a ticket's rows as a batch of trades is booked from its template and ticket, with no index, schedule, quantity, market or preparation. A row is one payment: an unwind or termination payment, a fee, a broker's or an exchange's rebate, positive received and negative paid. Each row names the curve it discounts on by `discount_curve_key`, since [cashflow-curve-keys.md](../../engineering-tickets/trade-valuation-pipeline/cashflow-curve-keys.md), text alone here, the curve found when the batch is valued. The batch retains the rows as booked and sums the amounts once per payment group, a distinct payment day and key, and [_EvaluateCashflows](evaluate-cashflows.md) values it. The instrument's fields are [show-instrument.md](../instruments/show-instrument.md)'s and the template [trade-template.md](../trades/trade-template.md)'s. The code is `src/catalyst/cashflows/booking.py`, the record and its builder, `src/catalyst/cashflows/rules.py`, the two rules of its own fields, and `src/catalyst/excel/cashflows.py`, the worksheet function. [The ticket](../../engineering-tickets/trade-valuation-pipeline/cashflow-instrument.md) has the instrument's decisions and [cashflow-curve-keys.md](../../engineering-tickets/trade-valuation-pipeline/cashflow-curve-keys.md) the keys'.

## Worksheet contract

```python
def _CreateCashflows(
    fields: TextRow, cashflow_rows: FieldRows[TradeTemplate], template: Handle[TradeTemplate]
) -> Handle[Cashflows]: ...
```

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | currency | counterparty | discount_curve_key | | |
| 2 | USD | Firm A | SOFR | | |
| 3 | `=_CreateTradeTemplate("cashflow",A1:C1,A2:C2)` | shows `30512:trade_template:2` | | | |
| 4 | trade_id | trade_date | amount | payment_date | description |
| 5 | 1 | 4-Jan-2027 | 10000 | 4-Jan-2028 | Receivable |
| 6 | 2 | 4-Jan-2027 | -10000 | 3-Jan-2029 | Payable |
| 7 | 3 | 4-Jan-2027 | 250 | 3-Jan-2027 | Earlier rebate |
| 8 | `=_CreateCashflows(A4:E4,A5:E7,A3)` | shows `30512:cashflows:USD:3` | | | |

Three arguments, every one required and none with a default. The header row and the rows beneath it are the ticket, bound against the template's instrument through the field path of [inputs.md](../../seam/inputs.md), decision 42: each header a field of `cashflow` exactly, each cell typed by its field, a number, a date, text or the currency code, a blank or a wrong kind refused by its cell, and a header the template also supplies refused by name; a header that is a field of another instrument is refused as no field of this one, so a `fixed_float` template under a cashflow ticket is refused at its first cashflow header, and a ticket of the two fields the instruments share reaches the library, which refuses the template by name. The template is a handle, the cell showing `_CreateTradeTemplate`'s result with `cashflow` as its instrument, resolved as any handle is. The result is a handle, text in the cell that stands for the batch the seam keeps, declared `Handle[Cashflows]` as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says, carrying the batch's currency where a batch of trades carries its index's name, `30512:cashflows:USD:3`; equal calls share one batch while any is live and it is released when Excel disconnects the last, [handles.md](../../seam/handles.md#publication-and-release). The batch is immutable: a curve or a valuation day changes nothing of it, and `_EvaluateCashflows` makes new results over it.

## Excel help

Quoted from the declaration in `src/catalyst/excel/cashflows.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a batch of cashflows, known signed amounts in one currency each on its own payment date, from a template's shared fields and a ticket's rows, and shows its handle, the text _EvaluateCashflows takes as the cashflows. |
| `fields` | The ticket's header cells in one row, such as A4:E4, using names shown by _ShowInstrument for cashflow and none the template supplies. |
| `cashflow_rows` | The rows under the headers, such as A5:E9, one payment per row, a repeated row a second payment. |
| `template` | The trade-template handle: the cell showing _CreateTradeTemplate's result for the cashflow instrument, such as B3, or a name for it, which supplies the shared fields. |

## The library checks

In this order, the first failure being the message, after the seam has typed every cell; a rule on a ticket's column names the first bad row, and on a template's value the field alone, since every row shares it.

| Rule | Refused as |
|---|---|
| the template is of the cashflow instrument | `template is of instrument 'fixed_float', expected cashflow, the one instrument whose cashflows are built` |
| no field is supplied by both the template and the ticket, even to the same value | `currency is supplied by the template and by the ticket, expected by one of them` |
| `trade_date`, `amount`, `currency`, `payment_date` and `discount_curve_key` are each in one of them; `trade_id`, `counterparty` and `description` may be left out of both | `amount is missing, expected a value in the template or a column in the ticket` |
| the currency is `USD` exactly, one per batch, read when the template is made or once per distinct text of the column; `CENT` is a scale of the dollar and no currency, and an amount is never read as cents | `currency row 2 is 'CAD', expected USD, the one currency this version books` |
| each trade ID, where supplied, is a whole number of at most 15 digits, the trades' rule and words | as [create-trades.md](../trades/create-trades.md) says |
| each amount is finite, zero and fractions included, the whole payment in whole units of the currency | `amount row 2 is inf, expected a finite amount` |
| each key is a curve's name by the curve's own rule, [discount-curve.md](../globals/discount-curve.md), exact, case and all, with no whitespace around it: the template's one key read when the template is made and named by the field, a ticket column's each distinct text read once and named with its first row; no curve is looked for | `discount_curve_key row 2 is ' SOFR', expected a name with no whitespace around it` |
| the rows' amounts in one payment group, a payment day and a key, sum to a finite amount, under numpy's flags down | `the payments on 2028-01-04 on SOFR sum to inf, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number` |

A payment date is used as entered, past, present or future, never rolled and never held to the trade date; a repeated row is a second payment; a zero amount is a row kept. Nothing is read from a counterparty or a description.

## What it retains

Per row, in the ticket's order: the trade ID where the batch has it, the trade date, the amount, the payment date, the counterparty and the description where the batch has them, and the key, the template's value on every row; the one currency; and the distinct keys in the order the rows first name them. Then the payment groups, the distinct pairs of payment day and key, in day order and within a day in key order, with the rows' amounts summed in each and each row's group, the group's amount the one amount `_EvaluateCashflows` discounts, so that two payments on one day under one key are one amount, and two on different days, or on one day under two keys, stay apart whatever they net to, a group netting to zero kept as any other; a batch on one key has a group a day. And the distinct payment days, increasing, with the payment months and years they fall in, the axes every curve's DV01 is summed onto, made once here and shared by the keys. The batch reads the template and the ticket and keeps none of either.

## Reading it back

`util_ReadHandle` on the handle spills one row per payment booked, in the ticket's order, under the definition's field names in its order: `trade_id` where the batch has it, `trade_date`, `amount`, `currency`, `payment_date`, `counterparty` and `description` where it has them, and `discount_curve_key` last, after every column a sheet already read by its place, the template's value on every row; [read-handle.md](../utilities/read-handle.md). The summing by day and key is the results' to show.

## Tests

The worked example, the rules in order, the summing by day and by key, the key from the template and from the ticket, and the seam's handle, readback and refusals are `tests/unit/test_cashflows.py`; the instrument's grid is `tests/unit/test_instruments.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`; the handle's life is the `cashflows` group of `tools/excel_lifetime.ps1`. What a call costs is `tests/performance/test_cashflow_budgets.py`, the rows booked, the days mapped and the groups formed, the same functions at three rows and at two thousand, a batch on several keys one more unique, the peaks by rows and days and the columns kept.

## Not here

Any other currency, FX valuation or FX risk; a recurring schedule, a floating or contingent amount; a link to the deal a payment unwinds or the reserve it settles; counterparty netting, credit or legal treatment; a payment date held to the trade date; a curve held by the batch or looked for at booking, the key being text until the batch is valued; and the valuation itself, which [_EvaluateCashflows](evaluate-cashflows.md) owns. More rows are more payments; no schedule instrument is needed for that.
