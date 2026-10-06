# _CreateTradeTemplate

Built in #139 as ticket I4 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_CreateTrades](create-trades.md); the seam's part, `FieldRow[str]` and the `FieldValues` it hands over, in #138 as [inputs.md](../../seam/inputs.md) decision 42.

Shared trade fields under a library-owned instrument definition, created once and taken by every batch whose ticket supplies the rest, so a ticket of many rows types each shared fact once. The template may be incomplete, has no market-state dependency, and retains no index: the index is the first argument of `_CreateTrades`, so one template serves a CL index and an NG index alike. The code is `src/goosedove/trades/template.py`, the record, its builder and the readers of each field's value, and `src/goosedove/excel/trades.py`, the worksheet function.

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
| 3 | `=_CreateTradeTemplate("future", A1:B1, A2:B2)` | shows `30512:trade_template:40` |

The NG example's template, every field of the `future` the five ticket rows do not supply, in A1:F2 with the creator in B3: `quantity_unit` NYMEX NG, the specification the quantities count, `quantity_per` month, `schedule_method` lastday, `route` cleared, `settlement_method` physical, `clearing_house` CME Clearing.

Three arguments, all required, none with a default. The instrument is first: one exact name from `_ListInstruments`, `future`, which selects the definition the headers are checked against. The fields are one row of field names as `_ShowInstrument` shows them, spelled exactly, case and all, in any order; the values one aligned row beneath them. One field takes the same path as many, and a template carries at least one. Omit a field entirely when the template should not supply it; a listed field with a blank cell is an input error, not an instruction to inherit something. The row crosses as `FieldRow[str]`, the seam's one-row form of decision 42, bound against the instrument named: the seam checks the name's type, the width, each header against the definition, unknown and repeated headers named, and each cell by its field's type, a date as a date, a number as a number, a code as text and `payment_holiday_calendar` as a holiday calendar handle resolved to its object; more than one row of values is refused as `values is 2x1 array, expected one row of field values`. The result is a handle, `30512:trade_template:40`, the kind and the count alone, since a template carries no index's name. Other formulas refer to the cell; a worksheet heading or an Excel name such as `ICE_Futs` or `NYMEX_Futs` says what the template is for, and the library object has no label field. An unchanged recalculation shares the live template; a changed cell under it, a value or the holiday calendar's own creator, makes a new one and every batch over it anew, the old released when Excel disconnects its last creator.

## Excel help

| Item | Text |
|---|---|
| Function | Creates shared defaults for an instrument and shows their handle, the text other formulas take as the trade template. |
| instrument | One instrument name from _ListInstruments, such as future. |
| fields | The field-name cells in one row, such as A1:B1, using names shown by _ShowInstrument. |
| values | The values in one row beneath those fields, such as A2:B2. |

## The library checks

Each supplied value is read once for the rule intrinsic to its field, in the sheet's order, the first failure being the cell's text after `#ERROR _CreateTradeTemplate: ValueError:`; the same readers read a ticket's values when a batch is resolved, so a value fails here as it would there.

| Field | Rule | Refused as |
|---|---|---|
| `schedule_method` | `lastday` and `penultimate`, the two methods built; `asian` and `last3day` fail by name until they are | `schedule_method is 'asian', expected lastday or penultimate, the two methods built` |
| `route` | `cleared` or `bilateral`, exactly | `route is 'Cleared', expected cleared or bilateral` |
| `settlement_method` | `physical` or `financial` | `settlement_method is 'cash', expected physical or financial` |
| `quantity_unit` | any nonempty text, held as typed: it names one of the index's specifications, and the template has no index to ask, so `_CreateTrades` checks the name against the index it is given | nothing here; `quantity_unit is 'ICE PHH', expected one of the index's specifications: 'NYMEX NG'` at `_CreateTrades` |
| `quantity_per` | `month`, the one basis built | `quantity_per is 'day', expected month, the one basis built` |
| `payment_time_lag` | `+1bd`, `+2bd`, a positive whole number of business days, nothing else | `payment_time_lag is '+0bd', expected a positive whole number of business days, such as +1bd` |
| `contract_code` | a contract or strip the period grammar reads, in either case | `contract_code is 'Z2026', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28` |
| `quantity` | a whole count of the quantity unit, zero included since #146, a row kept ready, the kernel's own rule | `quantity is 1.5, expected a whole number` |
| `fixed_price` | a finite number, the kernel's own rule | `fixed_price is inf, expected a finite price` |

Nothing is required of a template: not `trade_date`, `contract_code`, `quantity` or `fixed_price`, which a ticket supplies, and not the payment fields of a financial settlement. The conditions, which fields are required and which present, whether the template and the ticket overlap, whether a specification is the index's, whether a code is a contract of the schedule, need the ticket and the index, and `_CreateTrades` checks them against the completed batch, so there is no second validator here anticipating every ticket. The seam owns shape, type and the reference's resolution; the library reads meaning and never parses a handle or coerces a number from text.

## What it retains

```text
TradeTemplate
    instrument   the library's future definition, by reference
    defaults     by field name, in the sheet's order: quantity_unit NYMEX NG, schedule_method lastday
```

Each default is the one value the row held, owned: a number as a float, a date as a day, text and a code as text, and a holiday calendar as the object its handle stood for, the same object the calendar's own cell publishes, held by reference so that a batch resolved under the template counts its payment days on it. No duplicate instrument schema is authored by the workbook, no per-field permission list exists, and no trade encoding, history binding or evaluation is performed. The template is the one kind whose handle selects an instrument for the seam, through `goosedove.instruments.fields.selected`, so `_CreateTrades` binds its ticket against the template's definition.

## Template plus ticket

The same template supplies its fields to one or many ticket rows. Template fields and ticket columns must be disjoint: a template supplying `quantity_unit` and a ticket with a `quantity_unit` column fail before anything combines, `quantity_unit is supplied by the template and by the ticket, expected by one of them`, equal values or not. Remove the column or remove the field; there is no override, equality exception or fallback. To vary a field between rows, leave it out of the template and supply it in the ticket, where the batch fields, `route` among them, must still agree across rows. Duplicate field names within either input fail at the seam. Duplicate trade rows remain distinct trades; rejecting duplicate field sources deduplicates nothing. [create-trades.md](create-trades.md) holds the order of these checks and the messages.

## Reading it back

`util_ReadHandle` on the handle spills one row under two heading rows: `instrument` first, `future`, then each default under its field name in the sheet's order, a number and a date as they are, text as typed and a holiday calendar as `a holiday calendar`, the words of its kind. The spill shows what the template holds and is no round trip of a handle.

## Tests

| Case | Where |
|---|---|
| NYMEX NG and lastday make the page's template; one field and the NG template's six take one path; each value the scalar its type names and a calendar the object itself; a unit held as typed, the index asked later | `tests/unit/test_trade_template.py` |
| A template selects its instrument for a ticket; a field the ticket must supply is not required | the same |
| Fourteen values against their fields' rules refused naming the field, a fraction of a quantity and an infinite price among them; a quantity of zero, negative zero too, held as a row kept ready; a template's numbers passing the kernel's rules; the builder takes one row | the same |
| The creator's handle, the seam's refusals in order before the library's, the reader's spill | the same, 26 in all |
| One read per value and one publication, 2,331 bytes | `tests/performance/test_trade_creation_budgets.py`, `test_seam_allocation.py` |
| A typed holiday calendar survives through the template into a batch's payment days; the calendar's change republishes the template and the batch; the template's cell cleared fails the batch and releases both | `tools/excel_lifetime.ps1 -Groups trades` |
| The creator, its spill and its refusals on a sheet | `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `workbooks/handles.xlsx` B1273 and B1289 |

## Not here

Trade construction, complete-trade validation, static encoding, market binding and valuation: [create-trades.md](create-trades.md) and the [kernel](kernel.md). Template inheritance, a permission system, a label argument or label field, a template that carries an index. A value read for meaning beyond its own field: a specification name, a code's month, a lag's day wait for the index and the ticket.
