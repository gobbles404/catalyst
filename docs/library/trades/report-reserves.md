# _ReportReserves

Built in #170 as the ticket [reserve-totals.md](../../engineering-tickets/trade-valuation-pipeline/reserve-totals.md) of the [trade-valuation pipeline](../../engineering-tickets/trade-valuation-pipeline/README.md), beside [_ReportValues](report-values.md), [_ReportRisk](report-risk.md) and [_ReportDelta](report-delta.md); the owner's direction is item 8 of the [UAT notes](../../engineering-tickets/trade-valuation-pipeline/surface-uat-notes.md#8-clearing-brokerage-and-marketing-reserves). Since #NN the marketing reserve is a field, [booking-fields-and-marketing-reserve.md](../../engineering-tickets/trade-valuation-pipeline/booking-fields-and-marketing-reserve.md), items 8 and 11.

The batch's booked reserves, from its results: the brokerage and the clearing the batch incurs, each trade's quantity in each month without its sign times its own specification's two rates per lot, summed; since #NN the marketing reserve, the amounts the rows booked under `marketing_reserve`, from the template or the ticket, each once per row whatever its months, summed, zero when neither supplied the field; and the currency they are in, the index's settlement currency. [_CreateTrades](create-trades.md) books them once, when the batch is made; the preparation and the evaluation carry the record by reference, and the report formats it, summing, pricing and reading nothing. Reserves are costs, not value: no mark, cash, delta or DV01 moves with them, and a fixing, a correction, a payment, a tick or a roll of the valuation date leaves them as booked. The code is `src/goosedove/excel/trades.py` and `src/goosedove/trades/reserves.py`.

## Worksheet contract

```python
def _ReportReserves(results: Handle[TradeResults]) -> MixedArray: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 25 | `=_ReportReserves(A12)` | | | |
| | brokerage_reserve | clearing_reserve | marketing_reserve | currency |
| | float64 | float64 | float64 | str |
| | 50 | 20 | 0 | USD |

One handle, required: the results, the cell showing `_EvaluateTrades`'s result or a name for it; a blank, a number or a handle of another kind fails in the seam's words, `results is blank, expected trade results handle`. The spill is three rows by four columns: the headers, the types and one row of the stored values. `brokerage_reserve` and `clearing_reserve` are positive costs in `currency`; `marketing_reserve` is 0 until the marketing reserve is built, with no field in a template or a ticket; `currency` is the index's settlement currency, the conventions' `currency_unit`, the one the specifications' rates are in.

The example is the ticket's, on an index whose specifications charge LOT, a thousand barrels, 10.00 of brokerage and 4.00 of clearing a lot, and BBL, one barrel, 0.01 and 0.004, settled in USD; four trades of one month each:

| Trade | Quantity | Specification | Brokerage | Clearing |
|---|---:|---|---:|---:|
| 101 | 2 | LOT | 20 | 8 |
| 102 | -2 | LOT | 20 | 8 |
| 103 | 1000 | BBL | 10 | 4 |
| 104 | 0 | LOT | 0 | 0 |
| **Batch** | | | **50** | **20** |

The first two net to no exposure and still reserve 40 of brokerage and 16 of clearing; one LOT and 1,000 BBL reserve the same here only because the rates agree on that basis. Each component's count is the quantity its basis gives it, the entered quantity in each month under `month`, a partial month's included, and the entered quantity times the month's covered days under `calday`: 2 BBL a calendar day over X26 and Z26 counts 2 × (30 + 31) = 122 BBL, 1.22 of brokerage and 0.488 of clearing, and a partial-month `asian` of 1,000 BBL on the month basis reserves the month's 10 and 4. The rates are the row's own, as given: a row named BBL with a lot size of one charges per barrel and a row named LOT of a thousand barrels per thousand, and nothing is multiplied by a lot size again or converted through the reporting lot, a price coefficient or the quote currency. Every occurrence counts, a repeated trade ID again, a strip once per month and a zero quantity nothing; changing only the reporting lot or the schedule method, and so the pricing days, changes no reserve.

**The marketing reserve, since #NN.** The ticket's rows on the same index, LOT each, 2 and -2 of Z26, 1 of the strip Z26-F27 and 0 of Z26, booking 15, 20, 25 and 5 under `marketing_reserve`:

| Row | Quantity | Period | Marketing | Brokerage | Clearing |
|---|---:|---|---:|---:|---:|
| 1001 | 2 | Z26 | 15 | 20 | 8 |
| 1002 | -2 | Z26 | 20 | 20 | 8 |
| 1003 | 1 | Z26-F27, two components | 25 | 20 | 8 |
| 1004 | 0 | Z26 | 5 | 0 | 0 |
| **Batch** | | | **65** | **60** | **24** |

The strip books its 25 once though it makes two components, the zero-quantity row its 5 in full, and the opposing trades both; a duplicate of the first row books 80, a template's 7 books 28 on the four plain rows, and no field in either books nought. The amounts enter no value: the mark, the cash and the lots are the same with the column and without, and a tick, a fixing, a correction and a payment leave them as booked.

## Excel help

| Item | Text |
|---|---|
| Function | Reports the batch's reserves from its results, as creation stored them: brokerage and clearing, each trade's quantity without its sign times its specification's rates per lot, summed; marketing, the amounts the rows booked, summed once each; and their currency. |
| results | The results handle: the cell showing _EvaluateTrades's result, such as A12, or a name for it. |

## The library checks

The reserves are checked when the batch is made, by [_CreateTrades](create-trades.md), before any handle is published, in its words after `#ERROR _CreateTrades: ValueError:`; brokerage before clearing.

| Rule | Refused as |
|---|---|
| Each component's amount is finite: a product past the largest number, or a rate held as NaN or an infinity, a zero quantity included, since nought times an infinite rate is not a number | `brokerage reserve of trade 101 at row 1 is inf, expected a finite amount of USD; 2.0 of 'LOT' at 9e+307 a lot` |
| Each total is finite: amounts each finite can sum past the largest number | `the batch has inf of brokerage reserve in all, expected a finite amount of USD; the components' reserves, each finite, sum past the largest number` |
| Since #NN each marketing reserve is a finite amount of zero or more, the first bad row named by the field and the row, or the field alone in a template | `marketing_reserve row 2 is -5.0, expected a finite amount of zero or more`; `marketing_reserve is -5.0, expected a finite amount of zero or more` |
| The marketing sum is finite, held as the two totals are | `the batch has inf of marketing reserve in all, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number` |

The specifications' own rule, each rate 0 or more, is [contract-specifications.md](../index-definitions/contract-specifications.md)'s and unchanged. The report checks nothing: the record is complete when the batch is published.

## Reading it back

`util_ReadHandle` on the results ends with the same four columns, `brokerage_reserve`, `clearing_reserve`, `marketing_reserve` and `currency`: the values on the first slot row, and a dash, `-`, in all four on every later row, since the totals are the batch's and no slot's, a total repeated on every slot would read as each slot's, and the seam's way out has no blank cell. The batch's own readback carries no reserve: the UAT notes moved the reserve view off the trade handle and onto the evaluated results.

## Tests

| Where | What |
|---|---|
| `tests/unit/test_trades.py` | the ticket's four trades, 50 and 20 and nought in USD, the results holding the encoding's record itself and nothing reserved again, free rates moving no offset; the singletons summing to the batch, the rows reversed, a duplicate twice; the 122 BBL strip through evaluation under either reporting lot; a NaN rate, a zero quantity at an infinite rate and a sum past the largest number refused |
| `tests/unit/test_trade_valuation.py` | the worked example through the seam, the report cell for cell and the results readback's first row; the four methods, one, one, three and 22 slots, the same reserves and a dash on every later row; one batch through a tick, a fixing, a correction and its payment, the mark moving and the reserves not; doubled quantities 100 and 40, dearer rates 68 and 25, a barrel reporting lot the same 50 and 20; the 124 BBL strip and the partial asian; the overflow publishing nothing; a blank, a prepared handle and a text naming nothing refused; and every results readback pinned elsewhere ending with the four, once |
| `tests/unit/test_help.py` | the help above |
| `tests/performance/test_trade_creation_budgets.py`, `tests/performance/test_trade_budgets.py` | `reserves` once in the creator's and the encoding's ledgers, `reserved_components` one per component, nothing at preparation or evaluation |
| `tests/performance/test_trade_valuation_budgets.py` | one handle resolved and one row laid out, three number columns and no day, nothing published; its allocation within the reports' ceiling |
| `tools/excel_smoke.ps1`, the host's `CallTests.cs`, `workbooks/handles.xlsx` | the worked example in the smoke's OR1:OW30 with the readback's four columns and the 9E+307 refusals, the ethane asian's readback a dash below its first row; the host's fact with a tick and the overflow; the kept workbook's rows 1848 to 1881, three states of one batch with the reserves beside the mark |
| since #NN, the same files and `tests/performance/test_trade_creation_budgets.py` | the ticket's four marketing rows, 65 once per row, the strip once and the zero row's five, a duplicate 80, a template's 7 booking 28, no field nought, value and risk the same either way; the rule by row, by template and the sum past the largest number; `reserved_occurrences` per row in the counter; the smoke's OR32:OW62, the host's fact extended and the workbook's rows 1976 to 2016 |

## Not here

No reserve release schedule, no fee payment lifecycle, no reserve discounting, no rate lookup by broker or clearing-house name, no per-trade report and no aggregation across indices: the ticket's boundaries. The marketing reserve, since #NN, is a booked amount like the other two: never released, accrued, discounted or moved to cash, and never a contribution to value.
