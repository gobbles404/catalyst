# _CreateContractSpecifications

Built in #78; the one-contract form was #69.

The contract specifications of one index: the name of each contract the index trades as, the quantity in one lot of it, and the brokerage and clearing charged per lot, one row per contract, each name once and each lot size whole, the rest kept as given, and reached by handle. An index traded on more than one exchange, gas as NYMEX lots and as ICE lots, has a row for each. Since #NN the [index](index.md) holds the specifications, and nothing checks the facts beyond those two rules; the rest is a task for later, noted at the builder rather than on a backlog. The code is `src/goosedove/index_definitions/contract_specifications.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

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

The input is a table: a header row, then a body with one row per contract, its name, lot size and the two fees per lot. The owner changed the one-contract form of #69, four scalars, for this one after use: an index needs more than one contract's terms, and a table's header binding and one body range keep each row's four facts together. The name is text, any text with a character in it; the lot size is a number the library requires whole, so 10000 passes and 2.5 fails, in the library's words, while a whole double beyond 2^53, 1E16 say, passes and goes back out as it came, since the lot sizes stay the doubles the cells hold and the one-contract form's line at 2^53 ([inputs.md](../../seam/inputs.md) decision 41) belonged to a Python int; the two fees are numbers with any fraction. The headers bind in either order and capital letters do not matter; the spelling must match, and `brokerage` is not a header. Both arguments required, no defaults. The seam binds the headers and checks the columns; nothing here restates that. The result is a handle: text in the cell that stands for the specifications the seam keeps, declared `Handle[ContractSpecifications]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the specifications.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the contract specifications of one index, the name, lot size and fees per lot of each contract it trades as, and shows its handle, the text other formulas take as the specifications. |
| `header_row` | The header cells of your contract table, such as A1:D1, reading name, lot_size, brokerage_rate_per_lot and clearing_rate_per_lot in any order. |
| `table` | The rows under the headers, such as A2:D3: one contract per row, its name, lot size and the two fees per lot, each name once. |

## The library checks

Two rules, in this order, the first failure being the message. Rows count as the sheet counts them, the first row of the body being row 1.

| Rule | Message |
|---|---|
| each name once, because a trade's specification will pick its contract by this name, `nymex` or `icelots` as the desk likes, and a name twice would be two specifications for one contract | `name row 2 is 'NYMEX NG', already given at row 1` |
| each lot size whole, because a lot is a whole number of the contract's quantity unit | `lot_size row 1 is 2.5, expected a whole number` |

Nothing else is checked. The names are kept as typed, the lot sizes as the whole numbers they arrived as, doubles still, the fees as the numbers they are. Whether a lot size must be at least one, whether a fee may be negative, a rebate, and which unit the fees are in, the currency unit of the index conventions or another, are a task for later, noted at the builder so it is not lost and built when the first consumer needs the facts to mean something. One contract is a set of specifications. A failed call publishes nothing, and a cell the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_contract_specifications.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the specifications, typed; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample above: every contract kept, aligned, in its own columns | example |
| one contract accepted as a set of specifications | example |
| a lot size of zero or below, a negative fee, a fee with a fraction and a name with spaces: kept as given, since nothing else is checked yet | example |
| a name given twice, in a row or apart: rejected, naming both rows; a lot size with a fraction: rejected, naming the row; the names checked before the lot sizes; a whole double beyond 2^53 kept | example |
| for any distinct names, any whole numbers and any two columns of finite numbers, everything is kept and aligned | property |
| an input changed after construction leaves the specifications unchanged, and their arrays refuse writes | example |
| the specifications read back through the handle, typed; the headers bind in any order and any case; one row is a table | example, through the seam |
| an unknown header, a boolean lot size, text where a fee is expected, a number where a name is expected, a body narrower than its headers, a blank or missing body: the seam's words; a lot size with a fraction and a name given twice: the library's | example, through the seam |
| a failed construction publishes no object and no handle; a handle of another kind is not contract specifications | example, with handles |
| for any lot size from −2^53 to 2^53, the specifications are created and `util_ReadHandle` shows the lot size as it was; 1E16 and 1E20, whole doubles, are kept and read back as they are | property and example, through the seam |
| the specifications' spill: four headers, four types, then one row per contract, the name as text and the numbers as numbers | example |
| the creator's handle over a table of two contracts read back through `util_ReadHandle`, a lot size with a fraction, text where a fee is expected and a name given twice, in a real workbook | Excel smoke |

## Not here

What the fees mean to a trade, how and in which unit they are charged, and what a lot converts to in the index's quantity unit: the first consumer's job, with the index conventions beside it. Which contract a trade is in: by name, the consumer's lookup. How the specifications, the futures schedule, the holiday calendars and the index conventions, handles today, are tied together into one index definition: the owner's next creator, its page not yet written. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any specifications as one row per contract. Market data, pricing.
