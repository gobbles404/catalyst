# _CreateTradeTemplate

Built in #139 as ticket I4 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_CreateTrades](create-trades.md); the seam's part, `FieldRow[str]` and the `FieldValues` it hands over, in #138 as [inputs.md](../../seam/inputs.md) decision 42.

Shared trade fields under a library-owned instrument definition, created once and taken by every batch whose ticket supplies the rest, so a ticket of many rows types each shared fact once. The template may be incomplete, has no market-state dependency, and retains no index: the index is the first argument of `_CreateTrades`, so one template serves a CL index and an NG index alike. The code is `src/catalyst/trades/template.py`, the record, its builder and the readers of each field's value, and `src/catalyst/excel/trades.py`, the worksheet function.

## Worksheet contract

```python
def _CreateTradeTemplate(
    instrument: str,
    fields: TextRow,
    values: FieldRow[str],
) -> Handle[TradeTemplate]: ...
```

The user's example, two fields:

| | A | B |
|---|---|---|
| 1 | quantity_unit | schedule_method |
| 2 | NYMEX NG | lastday |
| 3 | `=_CreateTradeTemplate("fixed_float", A1:B1, A2:B2)` | shows `30512:trade_template:40` |

The NG example's template, every field of the `fixed_float` the five ticket rows do not supply, in A1:G2 with the creator in B3: `quantity_unit` NYMEX NG, the specification the quantities count, `quantity_per` month, `schedule_method` lastday, `route` cleared, `settlement_method` physical, `clearing_house` CME Clearing and, since [onetime-averaging.md](../../engineering-tickets/trade-valuation-pipeline/onetime-averaging.md), `settlement_frequency` monthly.

Three arguments, all required, none with a default. The instrument is first: one exact name from `_ListInstruments`, `fixed_float`, which selects the definition the headers are checked against. The fields are one row of field names as `_ShowInstrument` shows them, spelled exactly, case and all, in any order; the values one aligned row beneath them. One field takes the same path as many, and a template carries at least one. Omit a field entirely when the template should not supply it; a listed field with a blank cell is an input error, not an instruction to inherit something, for every field but the three period fields, `contract_code`, `start_date` and `end_date`, whose cell may be blank or a formula's `""` since #172: the template then owns the header, so a ticket column of that name is still overlap, and supplies the value to no row, [contract-codes-and-dates.md](../../engineering-tickets/trade-valuation-pipeline/contract-codes-and-dates.md). The row crosses as `FieldRow[str]`, the seam's one-row form of decision 42, bound against the instrument named: the seam checks the name's type, the width, each header against the definition, unknown and repeated headers named, and each cell by its field's type, a date as a date, a number as a number and a code as text, no field taking a handle since [payment-calendar-keys.md](../../engineering-tickets/trade-valuation-pipeline/payment-calendar-keys.md), `payment_holiday_key` being text as any other; more than one row of values is refused as `values is 2x1 array, expected one row of field values`, by its shape before any cell is looked at since #151, so a range one row too tall is named for its rows and never for the blank in its extra row. The result is a handle, `30512:trade_template:40`, the kind and the count alone, since a template carries no index's name. Other formulas refer to the cell; a worksheet heading or an Excel name such as `ICE_Futs` or `NYMEX_Futs` says what the template is for, and the library object has no label field. An unchanged recalculation shares the live template; a changed cell under it makes a new one and every batch over it anew, the old released when Excel disconnects its last creator. A payment calendar's change is no change under a template, which holds the key, a word, and no calendar: the batch binds the key, and is the one remade.

`_CreateTradeTemplate("float_float", fields, values)` makes the template of a spread of two indexes, [float-float-spread.md](../../engineering-tickets/trade-valuation-pipeline/float-float-spread.md), under the same rules over the `float_float`'s fields, `spread_price` read as a finite price where the template holds it. Its two unit fields, `spread_price_currency_unit` and `spread_price_quantity_unit`, [float-float-units.md](../../engineering-tickets/trade-valuation-pipeline/float-float-units.md), are text a template keeps as typed: a template retains no index and so no measure to read a quantity unit against, and `_CreateTrades` reads both when it has the indexes. `_CreateTrades` takes a template of either instrument and refuses any other by name, `template is of instrument 'cashflow', expected fixed_float or float_float, the instruments whose trades are built`.

## Excel help

| Item | Text |
|---|---|
| Function | Creates shared defaults for an instrument and shows their handle, the text other formulas take as the trade template. |
| instrument | One instrument name from _ListInstruments, such as fixed_float. |
| fields | The field-name cells in one row, such as A1:B1, using names shown by _ShowInstrument. |
| values | The values in one row beneath those fields, such as A2:B2. |

## The library checks

Each supplied value is read once for the rule intrinsic to its field, in the sheet's order, the first failure being the cell's text after `#ERROR _CreateTradeTemplate: ValueError:`; the same readers read a ticket's values when a batch is resolved, so a value fails here as it would there.

| Field | Rule | Refused as |
|---|---|---|
| `schedule_method` | `lastday`, `penultimate`, `last3day` or `asian`, the four methods of the definition, all built; any other word fails by name | `schedule_method is 'Asian', expected lastday, penultimate, last3day or asian` |
| `route` | `cleared` or `bilateral`, exactly | `route is 'Cleared', expected cleared or bilateral` |
| `settlement_method` | `physical` or `financial` | `settlement_method is 'cash', expected physical or financial` |
| `quantity_unit` | any nonempty text, held as typed: it names one of the index's specifications, and the template has no index to ask, so `_CreateTrades` checks the name against the index it is given | nothing here; `quantity_unit is 'ICE PHH', expected one of the index's specifications: 'NYMEX NG'` at `_CreateTrades` |
| `quantity_per` | `month`, `calday` or `period`, the third the total of a onetime period since [onetime-averaging.md](../../engineering-tickets/trade-valuation-pipeline/onetime-averaging.md), held here as typed and refused by `_CreateTrades` under `monthly` | `quantity_per is 'day', expected month, calday or period` |
| `settlement_frequency` | `monthly` or `onetime`, since [onetime-averaging.md](../../engineering-tickets/trade-valuation-pipeline/onetime-averaging.md): how many calculation periods a row's days make, held as typed: `monthly` one per calendar month, `onetime` one across the row's two dates, priced by `_CreateTrades` under `asian` on one futures index, or on a `float_float`'s two with both methods `asian`, financially settled, with `quantity_per` `period` or `calday`, and refused by name on a `fixed_float`'s two indexes, on a published index and under a physical settlement | `settlement_frequency is 'yearly', expected monthly or onetime` |
| `nearby` | a whole number of 1 or more, since [nearby-selection.md](../../engineering-tickets/trade-valuation-pipeline/nearby-selection.md): which listed contract prices each observation day, counted from the day's prompt, `1` the prompt and `2` the next the schedule lists, held as the whole number it is; whether a number above 1 is priced, and whether the schedule lists a contract that far on, is `_CreateTrades`' to say | `nearby is 0, expected a whole number of 1 or more, of at most 15 digits: 1 the prompt contract, 2 the next the schedule lists` |
| `payment_day` | a date, kept as the day the row entered and the batch's to hold after the row's last observation, since [payment-day-date-or-rule.md](../../engineering-tickets/trade-valuation-pipeline/payment-day-date-or-rule.md), or `+1bd`, `+3cd`, `+0em` or a chain such as `+3em+25cd-1bd+1bd`, one or more of a sign, a whole count of at most seven significant digits and `bd`, `cd` or `em` in either case, read whole as [util_ShiftDate](../utilities/shift-date.md) reads an offset since #181, zero and negative counts steps like any other; the day it makes is the batch's to check | `payment_day is '2bd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd`; `payment_day has a count of 20 digits, expected at most 7; the sheet's calendar runs 1900-03-01 to 9999-12-31` |
| `payment_holiday_key` | one calendar's name, or several joined by `+`, read for its form alone, [collect-holiday-calendars.md](../index-definitions/collect-holiday-calendars.md#binding-a-key): no name missing, none with whitespace around it, none twice; held as typed. A template is given no collection, so whether the names are calendars is `_CreateTrades`' to say | `payment_holiday_key is 'NYFED+', expected a calendar's name, or several joined by '+'; a name is missing`; `payment_holiday_key is 'NYFED+TOK', expected names of the collection's calendars, 'NYFED' and 'LON'; it holds no 'TOK'` at `_CreateTrades` |
| `contract_code` | text, held as typed since #172: the period grammar reads it at `_CreateTrades` for the rows that book by it, a row with both dates keeping it as entered text, so a label the grammar refuses is refused there and only when a row books by it | nothing here; `contract_code is 'Z2026', expected a contract or strip with two-digit years, such as F26, 1Q27, 1H27, CAL28, W29, S28 or F26-Z28` at `_CreateTrades` |
| `quantity` | a count of the quantity unit, zero included since #146, a row kept ready, by the kernel's rule for the settlement the row names, since [fractional-quantities.md](../../engineering-tickets/trade-valuation-pipeline/fractional-quantities.md): with `settlement_method` `financial` any finite number, 1.5 a lot and a half, held as entered; with `physical` a whole number; with no `settlement_method` in the row any finite number, the rule waiting for the method the ticket supplies, which `_CreateTrades` then applies, naming the trade | `quantity is 1.5, expected a whole number`, where the row settles physically; `quantity is inf, expected a finite quantity` |
| `fixed_price` | a finite number, the kernel's own rule | `fixed_price is inf, expected a finite price` |
| `fixed_price_currency_unit`, `fixed_price_quantity_unit` | the unit of the fixed price, [#273](https://github.com/gobbles404/catalyst/issues/273), two codes in two fields, `DOLLAR` and `MT`, each held as typed and read for nothing here, each the one code of every row of a batch made under the template. A template has no index and no unit tables, so what a code means is `_CreateTrades`' to say; and so is whether both are there, since a template may hold one, `DOLLAR`, and leave the other to the ticket's column | nothing here; `fixed_price_quantity_unit of trade 1 at row 1 is 'BBL', expected a MASS unit, KG, LB, MT, ST, LT, G, OZT or CWT_US` and `fixed_price_quantity_unit is missing, expected a value in the template or a column in the ticket beside fixed_price_currency_unit; a fixed price's unit is both fields, or neither for the index's quote units` at `_CreateTrades` |
| `marketing_reserve` | a finite amount of zero or more since #175, the reserves' rule, the one amount booked once by every row of a batch made under the template | `marketing_reserve is -5.0, expected a finite amount of zero or more` |
| `cva_reserve` | a finite amount of either sign since [cva-reserve.md](../../engineering-tickets/trade-valuation-pipeline/cva-reserve.md), the reserves' rule in the cashflow amount's words, the one signed amount booked once by every row of a batch made under the template | `cva_reserve is inf, expected a finite amount` |

Nothing is required of a template: not `trade_date`, `contract_code` or the two dates in its place, `start_date` and `end_date`, `quantity` or `fixed_price`, which a ticket supplies, and not the payment fields of a financial settlement. The conditions, which fields are required and which present, whether the template and the ticket overlap, whether a specification is the index's, whether a code is a contract of the schedule, need the ticket and the index, and `_CreateTrades` checks them against the completed batch, so there is no second validator here anticipating every ticket. The seam owns shape, type and the reference's resolution; the library reads meaning and never parses a handle or coerces a number from text.

## What it retains

```text
TradeTemplate
    instrument   the library's fixed_float definition, by reference
    names        the fields the row named, in the sheet's order, each owned for every batch under it
    defaults     by field name, in the same order: quantity_unit NYMEX NG, schedule_method lastday;
                 since #172 a period field may stand in names with no default, its cell having held nothing
```

Each default is the one value the row held, owned: a number as a float, a date as a day, text and a code as text, a payment day as the day or the rule text it held, and a payment holiday key as the text typed, a word the batch binds to a calendar and the template reads for its form alone. No duplicate instrument schema is authored by the workbook, no per-field permission list exists, and no trade encoding, history binding or evaluation is performed. The template is the one kind whose handle selects an instrument for the seam, through `catalyst.instruments.fields.selected`, so `_CreateTrades` binds its ticket against the template's definition.

## Template plus ticket

The same template supplies its fields to one or many ticket rows. Template fields and ticket columns must be disjoint: a template supplying `quantity_unit` and a ticket with a `quantity_unit` column fail before anything combines, `quantity_unit is supplied by the template and by the ticket, expected by one of them`, equal values or not. Remove the column or remove the field; there is no override, equality exception or fallback. To vary a field between rows, leave it out of the template and supply it in the ticket, where `route` and `settlement_method` must still agree across rows while `schedule_method`, `quantity_unit` and `quantity_per` are each row's own since #163, the template's value the uniform case of the same path. Duplicate field names within either input fail at the seam. Duplicate trade rows remain distinct trades; rejecting duplicate field sources deduplicates nothing. Since #172 a template's `contract_code` may stand beside a ticket's `start_date` and `end_date` columns, three different fields: a row with both dates books them and keeps the code as entered text, a row without books the code, and a template's start with a ticket's end column is a pair on the rows that give an end, [contract-codes-and-dates.md](../../engineering-tickets/trade-valuation-pipeline/contract-codes-and-dates.md). [create-trades.md](create-trades.md) holds the order of these checks and the messages.

## Reading it back

`util_ReadHandle` on the handle spills one row under two heading rows: `instrument` first, `fixed_float`, then each field the row named under its name in the sheet's order, a number and a date as they are, text as typed, the payment holiday key among it, and since #172 `(not supplied)`, text under `str`, where a period field's cell held nothing. The spill shows what the template holds and is no round trip of a handle.

## Tests

| Case | Where |
|---|---|
| NYMEX NG and lastday make the page's template; one field and the NG template's six take one path; each value the scalar its type names and a calendar the object itself; a unit held as typed, the index asked later | `tests/unit/test_trade_template.py` |
| A template selects its instrument for a ticket; a field the ticket must supply is not required | the same |
| Values against their fields' rules refused naming the field, a fraction of a quantity under a physical settlement, a quantity that is not finite under any, an infinite price, a lag beyond the sheet's calendar and one of 4,301 digits among them; the two days the lag is held to the seam's own, pinned; a quantity of zero, negative zero too, held as a row kept ready; a template's numbers passing the kernel's rules; the builder takes one row | the same |
| The creator's handle, the seam's refusals in order before the library's, a range one row too tall refused by its shape whatever its extra row holds, the reader's spill | the same, 29 in all |
| since #172, a period cell left blank or formula-empty: the field named and owned with no default, every other field's blank or empty cell refused in its field's words, the spill showing `(not supplied)`; a code the grammar refuses held as typed, read at `_CreateTrades` for the rows that book by it | the same, 2 more |
| One read per value and one publication, 2,331 bytes | `tests/performance/test_trade_creation_budgets.py`, `test_seam_allocation.py` |
| A key in the template selects the batch's payment calendar from the collection; the calendar's change republishes the calendar, its collection and the batch while the template stands; the template's cell cleared fails the batch and releases both | `tools/excel_lifetime.ps1 -Groups trades` |
| The creator, its spill and its refusals on a sheet | `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `workbooks/handles.xlsx` B1273 and B1289, read back in F1273 and F1289, and B1296, the headers taken into the values and refused by the shape, since #154 |

## Not here

Trade construction, complete-trade validation, static encoding, market binding and valuation: [create-trades.md](create-trades.md) and the [kernel](kernel.md). Template inheritance, a permission system, a label argument or label field, a template that carries an index. A value read for meaning beyond its own field: a specification name, a code's month, a lag's day wait for the index and the ticket. The static terms of a quote are a kind of their own, [quote-template.md](../quoting/quote-template.md), which `_CreateTrades` refuses as it refuses any other kind.
