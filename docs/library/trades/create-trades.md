# _CreateTrades

Built in #139 as ticket I4 of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), with [_CreateTradeTemplate](trade-template.md); the design is [CreateTrades: resolution, encoding and retained state](../../engineering-tickets/trade-valuation-pipeline/create-trade.md).

A batch of trades on one index: the deals a ticket's rows describe, one trade per row, completed with the shared fields a template supplies, resolved against the index and encoded into the static arrays the [kernel](kernel.md) prices. One row is a batch of one and a repeated row is a second trade; the batch is immutable, retains no history, price or valuation date, and is what `_PrepareTrades` takes. The code is `src/goosedove/trades/resolution.py`, the resolution child and the batch, `src/goosedove/trades/template.py`, the readers of each field's value, and `src/goosedove/excel/trades.py`, the worksheet function.

## Worksheet contract

```python
def _CreateTrades(
    index: Handle[Index],
    fields: TextRow,
    trade_rows: FieldRows[TradeTemplate],
    template: Handle[TradeTemplate],
) -> Handle[Trades]: ...
```

The NG example of the pipeline, its template in A1:G2 and `=_CreateTradeTemplate("future", A1:G1, A2:G2)` in B3 showing `30512:trade_template:40`, the index in B6:

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 4 | trade_id | trade_date | contract_code | quantity | fixed_price |
| 5 | NG-001 | 24-Sep-2026 | Z26 | 10 | 3.100 |
| 6 | NG-002 | 24-Sep-2026 | z26 | -4 | 3.150 |
| 7 | NG-003 | 25-Sep-2026 | F27 | 7 | 3.400 |
| 8 | NG-004 | 25-Sep-2026 | F27 | -12 | 3.350 |
| 9 | NG-001 | 24-Sep-2026 | Z26 | 10 | 3.100 |
| 10 | `=_CreateTrades(B6, A4:E4, A5:E9, B3)` | shows `30512:trades:Henry Hub NYMEX:41` | | | |

Four arguments, all required, none with a default. The index is the first: the cell showing `_CreateIndex`'s result, or a name for it, the one index every trade of the batch is on; it is no template field and no ticket column, so one template serves any compatible index, and the batch retains the index it was resolved against. The ticket is two arguments, as a table is: the header row, each header a field name shown by `_ShowInstrument` spelled exactly, case and all, in any order, and the rows under it, one trade each. The template is last: the cell showing `_CreateTradeTemplate`'s result, or a name for it. It selects the instrument the headers are checked against and supplies the fields the ticket does not; there is no path without one, so a batch that shares nothing still names one shared fact in its template. The ticket crosses as `FieldRows[TradeTemplate]`, the seam's row-or-rows form of [inputs.md](../../seam/inputs.md) decision 42, bound on the call against the template's instrument: the seam resolves the two handles, checks the width, the headers and each cell by its field's type, and hands the function typed columns; nothing here restates that. The result is a handle, text standing for the batch the seam keeps, `30512:trades:Henry Hub NYMEX:41`, the index's name between the kind and the count, as [handles.md](../../seam/handles.md) says. A successful call publishes a batch and changes neither input; a recalculation with the same arguments shares the live batch, and a changed cell anywhere under it, a ticket value, the template, the index, makes a new one, the old released when Excel disconnects its last creator.

## Excel help

| Item | Text |
|---|---|
| Function | Creates a batch of trades on one index from a template's shared fields and a ticket's rows, each contract code resolved against the index's schedule, and shows its handle, the text other formulas take as the trades. |
| index | The index handle: the cell showing _CreateIndex's result, such as B6, or a name for it, the one index every trade of the batch is on. |
| fields | The ticket's header cells in one row, such as A4:E4, using names shown by _ShowInstrument and none the template supplies. |
| trade_rows | The rows under the headers, such as A5:E9, one trade per row, a repeated row a second trade. |
| template | The trade-template handle: the cell showing _CreateTradeTemplate's result, such as B2, or a name for it, which selects the instrument and supplies the shared fields. |

## The library checks

After the seam, in this order, the first failure being the cell's text, each in the library's words after `#ERROR _CreateTrades: ValueError:`.

| Rule | Refused as |
|---|---|
| No field is supplied by both, even to the same value: remove the column or the template field | `quantity_unit is supplied by the template and by the ticket, expected by one of them` |
| Every field the definition always requires is present in one of them | `fixed_price is missing, expected a value in the template or a column in the ticket` |
| The batch fields are one each: `contract_specification`, `schedule_method`, `route`, `settlement_method`, `quantity_unit`, `quantity_per`, the template's value or a ticket column every row agrees on | `route row 3 is 'bilateral', expected 'cleared' as at row 1; a batch has one route` |
| The specification is named among the index's | `contract_specification is 'ICE NG', expected one of the index's specifications: 'NYMEX NG'` |
| The method, the route, the settlement and the basis are read from their lists, a choice the definition shows but the library has not built failing by name | `schedule_method is 'asian', expected lastday, the one method built`; `route is 'Cleared', expected cleared or bilateral`; `quantity_per is 'day', expected month, the one basis built` |
| A conditional field is present exactly when its condition holds: `clearing_house` with `route = cleared`, `payment_time_lag` and `payment_holiday_calendar` with `settlement_method = financial`, and absent otherwise | `clearing_house is missing, expected it when route = cleared`; `payment_time_lag is '+1bd', expected none unless settlement_method = financial` |
| The index is a futures index | `index is a Gas Daily index, expected a futures index for a future` |
| Every code of the index's schedule reads as a contract code, the rows the ticket does not use included, and no two rows are one month | `index schedule row 2 is 'c1', expected a contract code, a month letter and a two-digit year such as F26`; `index schedule rows 2 and 3 are 'Z26' and 'z26', both 2026-12, expected one contract per month` |
| Each `contract_code` reads through the period grammar, in either case, `Z26`, `z26`, `CAL27`, `Z27-X28`, and every month of it has a contract in the schedule | `contract_code row 2 is 'Z2026', expected a contract or strip with two-digit years, such as F26, 1Q27, CAL28, W29, S28 or F26-Z28`; `contract_code row 4 is 'CAL27', expected months the index's schedule has a contract for; it has none for 2027-02` |
| Each `payment_time_lag` is a positive whole number of business days | `payment_time_lag is '+0bd', expected a positive whole number of business days, such as +1bd` |
| Then the kernel's rules, [kernel.md](kernel.md): `LOT`, whole nonzero lots, finite prices, one payment day per contract, each named by its trade's row | `quantity_unit is 'MMBTU', expected LOT, the one quantity unit built`; `lots of trade 'NG-003' at row 3 is 7.5, expected a whole number of lots`; `payment_date of trade 'NG-002' at row 2 is 2026-12-01, expected 2026-11-30, the one day Z26 pays` |

A field the ticket supplies is named with its row, `contract_code row 4`, since each row has its own value; a field the template supplies is named alone, `contract_code is 'G27'`, since every row has the same. A strip's component is no row of the sheet, so a lot count or a price is named by the trade it belongs to, `trade 'S2' at row 2`, whichever month of a strip before it the kernel reached first.

## What resolution does

Codes become schedule rows by month. Every code of the index's schedule is read once for its month, `(year - 1970) * 12 + month - 1` as numpy counts months, through the one reader of a contract code, `contract_codes.month_and_year`; each distinct text of the ticket's `contract_code` column is read once through `periods.period_months`, the grammar behind `util_StartDate`, for its first month and the month after its last, so `CAL27` is twelve months and `Z27-X28` twelve from December 2027; then one pass of array arithmetic makes the components, one per month of each row in order, all on that row's occurrence, and looks each month up in the schedule's months, a month without a contract refused by the row and the month. The mapping from component to schedule row is made here once and retained in the terms; preparation and ticks never redo it, and the schedule's codes stay the labels the desk typed, `u26` on the spill where the ticket typed `U26`. A template's `contract_code` puts every row on the same contracts.

Lots and prices are the row's, repeated over the months of a strip; `quantity_per` is `month`, the one basis built, the entered lots in every constituent month. `trade_id`, `clearing_house` and `broker` are labels kept as typed, one per row, the template's repeated, read for nothing. `trade_date` is the row's or the template's.

For a financial settlement each component pays its row's lag in business days strictly after its contract's expiry, the schedule's `future_expiry`, counted on its row's payment calendar with Monday to Friday eligible less the calendar's holidays, through `numpy.busday_offset` with the expiry rolled back to the last eligible day on or before it first, so that an expiry the payment calendar closes is not itself counted: a Friday expiry with the Monday closed pays Tuesday at `+1bd` and Wednesday at `+2bd`, and Thanksgiving Thursday pays Friday at `+1bd`. The toy of the NG example, `+2bd` on a calendar closed on 26 November and 25 December 2026, pays Z26 on 30 November and F27 on 31 December, the page's dates. Each distinct lag text is read once; each distinct calendar object, by identity, takes one offset over the components on it. A physical settlement pays on no day and supplies neither field. The anchor is the contract's expiry and nothing else: no field is added to the schedule for it, and whether ICE's last trading day stands in that relation to the NYMEX penultimate pricing date is ticket R1's.

Then the kernel: `resolved_trades` checks the first profile's rules and freezes the columns, `encoded` turns them into quantities, coefficients, offsets and the inputs the batch consumes, as [kernel.md](kernel.md) says, and the batch holds both, the encoding holding the terms by reference as well. Nothing is read of a history, a market, a price or a valuation date.

## What it retains

```text
Trades
    resolved   ResolvedTrades: the instrument, the index, its schedule and the specification row;
               route, settlement, schedule method, quantity unit and basis; per row its trade date
               and, where given, trade_id, clearing_house and broker; per component its row, its
               schedule row, its lots, its fixed price and, for a financial settlement, its day
    encoded    Encoded: the terms by reference; per component its quantity, coefficient and
               offset; the inputs, one per contract held, and the sums by input
```

Every array is owned and read-only; the index, the schedule, the holiday calendars and the instrument definition are held by reference, never copied. The fees on the specification are read by nothing: reserves, never a contribution to value. The handle's text names the index, `30512:trades:Henry Hub NYMEX:41`, and the batch retains it as an object.

## Reading it back

`util_ReadHandle` on a trades handle spills one row per component: `row`, the ticket's row the component belongs to, as the sheet counts rows; `trade_id`, `clearing_house` and `broker` where the batch has them; `trade_date`; `contract_code`, the schedule's spelling; `lots`; `quantity`, in the index's quote quantity unit; `fixed_price`; `coefficient` and `offset`, in the settlement currency; and `payment_date` for a financial settlement. The NG example spills seven rows by ten columns, the five components after the two heading rows, `100000` and `-310000` on the first; the toy's strip `Z26-F27` spills two components on row 1 with their two payment days. The batch's own facts, the route, the settlement, the method and the specification, are the template's to show, [trade-template.md](trade-template.md). On a template handle the reader spills one row, the instrument first and each default under its field name, a holiday calendar as the words of its kind. Neither spill is a round trip of a handle.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_create_trades.py`, 37 | the NG rows resolve to the terms the kernel tests supply, every number of the page, codes in either case against a schedule in either case; a strip's components on one occurrence with their payment days, a whole year against a long schedule; a template's field for every row and a ticket's varying; a batch field in the ticket taken when every row agrees; payment days strictly after the expiry, a closed expiry rolled back first, calendars and lags in the ticket applying row by row; nineteen refusals in the order above, a lot count named by its row though a strip sits before it, two lags for one contract, the index's kind and its schedule's codes; the conditions tied to the definition's own `required_when` texts; the ticket and the template of one instrument; any ticket of single months resolving row by row, a property; the creator's handle, the order of the seam's refusals before the library's, and the two spills |
| `tests/unit/test_trade_template.py`, 21 | the template's record and the creator, [trade-template.md](trade-template.md) |
| `tests/unit/test_trades.py` | the kernel's record with the instrument and the two attribution tuples, and its messages naming the trade |
| `tests/performance/test_trade_creation_budgets.py`, 7 | the counter, `resolved_occurrences` and `resolved_components` one per row and per component, `schedule_codes_read` the schedule's 25 whatever the ticket, with the encoding's two; the resolution's ledger at five rows and at two thousand, the same functions but for four counts that follow the distinct codes, `months_of`, `period_months`, `_label_months` once each and `_Fields.where` once more for the lag, nothing per row, and the numpy ledger, two conversions per distinct code; the creator's ledger through the seam at five rows and at 2,500, the two handles resolved once each, one look per column and one publication; the template creator's, one read per value |
| `tests/performance/test_seam_allocation.py` | a template of nine fields 2,412 bytes; a batch of 2,500 rows 268,717, about 107 a row, the ten retained columns and the components' temporaries, the ticket's columns the seam's views |
| `tools/excel_smoke.ps1`, 29 rows | the two creators over the smoke's WTI-like index, the spills read with INDEX, a code typed in either case, a strip paying two business days after each expiry on the calendar in AM1, and nine refusals |
| `tools/excel_lifetime.ps1 -Groups trades`, 14 checks | a template holding a payment calendar and a batch on the chain's index: the calendar's input changed republishes the calendar, the template and the batch and moves the payment day, the chain untouched; the template's cell cleared fails the batch as its consumer and releases both; typed back, both live again |
| `host/Goosedove.Host.Tests/CallTests.cs`, 7 rows and a fact | the NG batch from the host's side, its spill, three refusals and the toy's strip |
| `workbooks/handles.xlsx` | B1273 and B1281 at the foot of the handles sheet, the template and the batch on the sample futures index, B1289 and B1292 the financial template and its strip, each read back in F, with a note in D1270 |

## Not here

No preparation, evaluation or report: `_PrepareTrades`, `_EvaluateTrades`, `_ReportValues` and `_ReportRisk` are ticket I5, over this batch. No schedule method but `lastday`, no basis but `month`, no quantity unit but `LOT`, no instrument but the `future`, no conversion of a quantity in MMBTU or barrels. No PHH payment date from ICE's own last trading day, ticket R1; no cash instrument; no bilateral valuation, which the kernel refuses at evaluation while creation accepts the route. A template field and a ticket column of one field never combine, equal or not; no override, fallback or inheritance. Nothing of a market, a history or a valuation date, and no work counter on the sheet: the creator makes its own and passes it with the unit tables, as `_CreateIndex` passes the tables.
