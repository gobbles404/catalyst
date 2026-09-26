# _CreateContractSpecifications

Built in #78; the one-contract form was #69; the lot sizes and the fees checked since #NN.

The contract specifications of one index: the name of each contract the index trades as, the quantity in one lot of it, and the brokerage and clearing charged per lot, one row per contract, each name once, each lot size whole and 1 or more, each fee 0 or more, the rest kept as given, and reached by handle. An index traded on more than one exchange, gas as NYMEX lots and as ICE lots, has a row for each. Since #107 the [index](index.md) holds the specifications. Two rules held from #78, each name once and each lot size whole, the rest noted at the builder for later; the [follow-ups](../follow-ups.md) pinned that rest on 26 September 2026, from #NN two more hold, a lot size of 1 or more and a fee of 0 or more, and that page marks the item resolved. A fee is a cost per lot in the index's settlement currency, the `currency_unit` of its [conventions](index-conventions.md): a decision this page states, and nothing here checks, since the specifications hold no conventions. The code is `src/goosedove/index_definitions/contract_specifications.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
class ContractSpecificationsTable(Table):
    name: TextColumn
    lot_size: NumberColumn
    brokerage_rate_per_lot: NumberColumn
    clearing_rate_per_lot: NumberColumn


def _CreateContractSpecifications(
    header_row: TextRow, table: ContractSpecificationsTable
) -> Handle[ContractSpecifications]: ...
```

| | A | B | C | D |
|---|---|---|---|---|
| 1 | name | lot_size | brokerage_rate_per_lot | clearing_rate_per_lot |
| 2 | NYMEX NG | 10000 | 3.00 | 2.00 |
| 3 | ICE NG | 2500 | 0.75 | 0.50 |
| 4 | `=_CreateContractSpecifications(A1:D1, A2:D3)` | shows `contract_specifications:3f9a1c:000009` |

The input is a table: a header row, then a body with one row per contract, its name, lot size and the two fees per lot. The owner changed the one-contract form of #69, four scalars, for this one after use: an index needs more than one contract's terms, and a table's header binding and one body range keep each row's four facts together. The name is text, any text with a character in it; the lot size is a number the library requires whole and 1 or more, so 10000 passes and 2.5 or 0 fails, in the library's words, while a whole double beyond 2^53, 1E16 say, passes and goes back out as it came, since the lot sizes stay the doubles the cells hold and the one-contract form's line at 2^53 ([inputs.md](../../seam/inputs.md) decision 41) belonged to a Python int; the two fees are numbers with any fraction, 0 or more. The headers bind in either order and capital letters do not matter; the spelling must match, and `brokerage` is not a header. Both arguments required, no defaults. The seam binds the headers and checks the columns; nothing here restates that. The result is a handle: text in the cell that stands for the specifications the seam keeps, declared `Handle[ContractSpecifications]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the specifications.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the contract specifications of one index, the name, lot size and fees per lot of each contract it trades as, and shows its handle, the text other formulas take as the specifications. |
| `header_row` | The header cells of your contract table, such as A1:D1, reading name, lot_size, brokerage_rate_per_lot and clearing_rate_per_lot in any order. |
| `table` | The rows under the headers, such as A2:D3: one contract per row, its name, a whole lot size of 1 or more and the two fees per lot, 0 or more, each name once. |

## The library checks

Five rules, in this order, the first failure being the message: the names, then the lot sizes, then the fees in the table's order. Rows count as the sheet counts them, the first row of the body being row 1.

| Rule | Message |
|---|---|
| each name once, because a trade's specification will pick its contract by this name, `nymex` or `icelots` as the desk likes, and a name twice would be two specifications for one contract | `name row 2 is 'NYMEX NG', already given at row 1` |
| each lot size whole, because a lot is a whole number of the contract's quantity unit | `lot_size row 1 is 2.5, expected a whole number` |
| each lot size 1 or more, because a lot of nothing, or of a negative quantity, is no contract | `lot_size row 2 is 0.0, expected 1 or more` |
| each brokerage rate 0 or more, because a fee is a charge, and zero is no charge | `brokerage_rate_per_lot row 2 is -0.75, expected 0 or more` |
| each clearing rate 0 or more, for the same reason | `clearing_rate_per_lot row 1 is -0.5, expected 0 or more` |

Nothing else is checked. The names are kept as typed, the lot sizes as the whole numbers they arrived as, doubles still, the fees as the numbers they are. A whole lot size below one fails the third rule and not the second, so `-3` reads `expected 1 or more`. A rebate is not a fee: a desk that is paid per lot records that where the payment is, on the consumer's side, never as a fee below zero, so a negative rate is refused as the mistyped charge it most often is. The two fee columns are costs per lot in the index's settlement currency, the `currency_unit` of its [conventions](index-conventions.md): that is what the numbers mean, decided here, and nothing here checks it, since the specifications hold no conventions; the consumer that charges a fee reads the currency off the index. One contract is a set of specifications. A failed call publishes nothing, and a cell the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_contract_specifications.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the specifications, typed; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`: the two looks over the lot sizes and one over each fee column, vectorized, no loop.

| Case | Kind |
|---|---|
| the sample above: every contract kept, aligned, in its own columns | example |
| one contract accepted as a set of specifications | example |
| a lot size of one, a fee of zero, a fee with a fraction and a name with spaces: kept as given, since nothing else is checked | example |
| a name given twice, in a row or apart: rejected, naming both rows; a lot size with a fraction: rejected, naming the row; the names checked before the lot sizes; a whole double beyond 2^53 kept | example |
| a lot size of zero, of negative zero and one below zero, first, last and between: rejected, naming the row and the lot size; a negative fraction named as a fraction, a negative whole as below one | example |
| a negative brokerage rate and a negative clearing rate, first, last and between: rejected, naming the column, the row and the rate; the lot sizes checked before the fees, and brokerage before clearing | example |
| for any distinct names, any whole numbers of 1 or more and any two columns of finite numbers 0 or more, everything is kept and aligned | property |
| for any column with one lot size below one or one fee below zero, the row is named | property |
| an input changed after construction leaves the specifications unchanged, and their arrays refuse writes | example |
| the specifications read back through the handle, typed; the headers bind in any order and any case; one row is a table | example, through the seam |
| an unknown header, a boolean lot size, text where a fee is expected, a number where a name is expected, a body narrower than its headers, a blank or missing body: the seam's words; a lot size with a fraction, a lot size of zero, a negative fee and a name given twice: the library's | example, through the seam |
| a failed construction publishes no object and no handle; a handle of another kind is not contract specifications | example, with handles |
| for any lot size from 1 to 2^53, the specifications are created and `util_ReadHandle` shows the lot size as it was; 1E16 and 1E20, whole doubles, are kept and read back as they are | property and example, through the seam |
| the specifications' spill: four headers, four types, then one row per contract, the name as text and the numbers as numbers | example |
| the creator's handle over a table of two contracts read back through `util_ReadHandle`, a lot size with a fraction, a lot size of zero, a negative fee, text where a fee is expected and a name given twice, in a real workbook | Excel smoke |

## Not here

The fee's currency checked against the index's [conventions](index-conventions.md): nothing here holds them, so the page above states the currency and the consumer that charges the fee reads it off the index. A rebate, a payment per lot to the desk: not a fee, and no negative fee stands for it; the consumer that receives one records it on its own side, when one arrives. What the fees mean to a trade and how they are charged, and what a lot converts to in the index's quantity unit: the first consumer's job, with the conventions beside it. Which contract a trade is in: by name, the consumer's lookup. How the specifications, the schedule, the holiday calendar and the conventions are tied together: the [index](index.md), since #107. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any specifications as one row per contract. Market data, pricing.
