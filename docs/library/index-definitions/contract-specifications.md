# _CreateContractSpecifications

Built in #78; the one-contract form was #69; the lot sizes and the fees checked since #110; the lot's unit since #115.

The contract specifications of one index: the desk's words for a quantity of it, each defined once. A word is a contract, NYMEX lots of gas say, or a bare unit, MMBTU; each row gives the word's name, the quantity in one lot of it, the unit that quantity is in, and the brokerage and clearing charged per lot, each name once, each lot size whole and 1 or more, each lot unit a quantity unit of the unit tables, each fee 0 or more, the rest kept as given, and reached by handle. A trade then says a word and a count, `lots, 10` or `mmbtu, 100000`, and never spells out what the word means: the specifications did, once. Since #107 the [index](index.md) holds the specifications, and since #115 it checks that every lot unit is a unit of its conventions' quantity type, the one fact that lives across two of the definitions, so barrels and gallons stand together under a volume index and MMBTU does not. Two rules held from #78, each name once and each lot size whole; #110 added a lot size of 1 or more and a fee of 0 or more; #115 the unit. A fee is a cost per lot in the index's settlement currency, the `currency_unit` of its [conventions](index-conventions.md): a decision this page states, and nothing here checks, since the specifications hold no conventions. The code is `src/goosedove/index_definitions/contract_specifications.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function. Since #NN a batch of trades books its reserves from the two fees, each row's count of its specification times the row's rates, [_ReportReserves](../trades/report-reserves.md).

## Worksheet contract

```python
class ContractSpecificationsTable(Table):
    name: TextColumn
    lot_size: NumberColumn
    lot_unit: TextColumn
    brokerage_rate_per_lot: NumberColumn
    clearing_rate_per_lot: NumberColumn


def _CreateContractSpecifications(
    header_row: TextRow, table: ContractSpecificationsTable
) -> Handle[ContractSpecifications]: ...
```

| | A | B | C | D | E |
|---|---|---|---|---|---|
| 1 | name | lot_size | lot_unit | brokerage_rate_per_lot | clearing_rate_per_lot |
| 2 | lots | 10000 | MMBTU | 3.00 | 2.00 |
| 3 | ice_lots | 2500 | MMBTU | 0.75 | 0.50 |
| 4 | mmbtu | 1 | MMBTU | 0 | 0 |
| 5 | `=_CreateContractSpecifications(A1:E1, A2:E4)` | shows `30512:contract_specifications:9` |

The input is a table: a header row, then a body with one row per word, its name, lot size, lot unit and the two fees per lot. The owner changed the one-contract form of #69, four scalars, for this one after use: an index needs more than one word's terms, and a table's header binding and one body range keep each row's five facts together. The name is text, any text with a character in it; the lot size is a number the library requires whole and 1 or more, so 10000 passes and 2.5 or 0 fails, in the library's words, while a whole double beyond 2^53, 1E16 say, passes and goes back out as it came, since the lot sizes stay the doubles the cells hold and the one-contract form's line at 2^53 ([inputs.md](../../seam/inputs.md) decision 41) belonged to a Python int; the lot unit is text the library requires to be a code of the unit tables' quantity categories, `BBL`, `GAL` or `MMBTU`, matched exactly; the two fees are numbers with any fraction, 0 or more. A bare unit is a row like any other, its lot size 1 and its unit itself. The headers bind in any order and capital letters do not matter; the spelling must match, and `brokerage` is not a header. Both arguments required, no defaults. The seam binds the headers and checks the columns; nothing here restates that. The result is a handle: text in the cell that stands for the specifications the seam keeps, declared `Handle[ContractSpecifications]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the specifications.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the contract specifications of one index, the desk's words for a quantity of it, each with its lot size, the lot's unit and the fees per lot, and shows its handle, the text other formulas take as the specifications. |
| `header_row` | The header cells of your specifications table, such as A1:E1, reading name, lot_size, lot_unit, brokerage_rate_per_lot and clearing_rate_per_lot in any order. |
| `table` | The rows under the headers, such as A2:E4: one row per word for a quantity of the index, a contract or a bare unit, its name, a whole lot size of 1 or more, the unit that lot size is in and the two fees per lot, 0 or more, each name once. |

## The library checks

Six rules, in this order, the first failure being the message: the names, then the lot sizes, then the lot units, then the fees in the table's order. Rows count as the sheet counts them, the first row of the body being row 1.

| Rule | Message |
|---|---|
| each name once, because a trade will pick its word by this name, `lots` or `mmbtu` as the desk likes, and a name twice would be two meanings for one word | `name row 2 is 'lots', already given at row 1` |
| each lot size whole, because a lot is a whole number of its unit | `lot_size row 1 is 2.5, expected a whole number` |
| each lot size 1 or more, because a lot of nothing, or of a negative quantity, is no lot | `lot_size row 2 is 0.0, expected 1 or more` |
| each lot unit a quantity unit of the unit tables, a unit of volume, mass or energy and never a currency unit, matched exactly, because a lot size without its unit is a number and not a fact | `lot_unit row 2 is 'usd', expected a VOLUME, MASS or ENERGY unit` |
| each brokerage rate 0 or more, because a fee is a charge, and zero is no charge | `brokerage_rate_per_lot row 2 is -0.75, expected 0 or more` |
| each clearing rate 0 or more, for the same reason | `clearing_rate_per_lot row 1 is -0.5, expected 0 or more` |

Nothing else is checked. The names and the lot units are kept as typed, the lot sizes as the whole numbers they arrived as, doubles still, the fees as the numbers they are. A whole lot size below one fails the third rule and not the second, so `-3` reads `expected 1 or more`. Units of two measures may stand in one table here, barrels and MMBTU say, since nothing here knows which measure the index is; whether each lot unit is a unit of the index's quantity type is the [index](index.md)'s rule, checked where the conventions and the specifications meet, `specifications row 2 lot_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3`. A rebate is not a fee: a desk that is paid per lot records that where the payment is, on the consumer's side, never as a fee below zero, so a negative rate is refused as the mistyped charge it most often is. The two fee columns are costs per lot in the index's settlement currency, the `currency_unit` of its [conventions](index-conventions.md): that is what the numbers mean, decided here, and nothing here checks it, since the specifications hold no conventions; the consumer that charges a fee reads the currency off the index. One word is a set of specifications. A failed call publishes nothing, and a cell the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_contract_specifications.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the specifications, typed; the spill is `tests/unit/test_utilities.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`: the two looks over the lot sizes and one over each fee column, vectorized, no loop, and the lot units looked up in one set of the tables' quantity units, built once per call.

| Case | Kind |
|---|---|
| the sample above: every word kept, aligned, in its own columns | example |
| one word accepted as a set of specifications | example |
| a lot size of one, a fee of zero, a fee with a fraction, a name with spaces and units of two measures in one table: kept as given, since nothing else is checked here | example |
| every quantity unit of the tables accepted as a lot unit | example |
| a name given twice, in a row or apart: rejected, naming both rows; a lot size with a fraction: rejected, naming the row; the names checked before the lot sizes; a whole double beyond 2^53 kept | example |
| a lot size of zero, of negative zero and one below zero, first, last and between: rejected, naming the row and the lot size; a negative fraction named as a fraction, a negative whole as below one | example |
| a currency unit, a unit in another case, one with a space and one nobody defined as a lot unit: rejected, naming the row and the unit, the first of two named | example |
| a negative brokerage rate and a negative clearing rate, first, last and between: rejected, naming the column, the row and the rate | example |
| the rules in order: names, lot sizes, lot units, fees, the earlier failure named | example |
| for any distinct names, any whole numbers of 1 or more, any quantity units and any two columns of finite numbers 0 or more, everything is kept and aligned | property |
| for any column with one lot size below one, one lot unit that is no quantity unit or one fee below zero, the row is named | property |
| an input changed after construction leaves the specifications unchanged, and their arrays refuse writes | example |
| the specifications read back through the handle, typed, the lot units among them; the headers bind in any order and any case; one row is a table | example, through the seam |
| an unknown header, a boolean lot size, text where a fee is expected, a number where a name or a lot unit is expected, a body narrower than its headers, a blank or missing body: the seam's words; a lot size with a fraction, a lot size of zero, a negative fee, a name given twice and a currency unit as a lot unit: the library's | example, through the seam |
| a failed construction publishes no object and no handle; a handle of another kind is not contract specifications | example, with handles |
| for any lot size from 1 to 2^53, the specifications are created and `util_ReadHandle` shows the lot size as it was; 1E16 and 1E20, whole doubles, are kept and read back as they are | property and example, through the seam |
| the specifications' spill: five headers, five types, then one row per word, the name and the lot unit as text and the numbers as numbers | example |
| the creator's handle over a table of a thousand-barrel lot and the bare gallon read back through `util_ReadHandle`, a lot size with a fraction, a lot size of zero, a negative fee, text where a fee is expected, a name given twice and a unit that is no quantity unit, and an MMBTU word refused at the index under volume conventions, in a real workbook | Excel smoke |

## Not here

Whether a lot unit is the index's measure: the [index](index.md)'s rule since #115, where the conventions and the specifications meet; nothing here holds the conventions. The fee's currency checked against the index's [conventions](index-conventions.md): likewise, the page above states the currency and the consumer that charges the fee reads it off the index. A rebate, a payment per lot to the desk: not a fee, and no negative fee stands for it; the consumer that receives one records it on its own side, when one arrives. What the fees mean to a trade and how they are charged, and what a lot converts to in the index's quantity unit through the [unit tables](../globals/unit-conversions.md): the first consumer's job, with the conventions beside it. Whether a trade's count of a word is for a period or per day: the trade's convention, on its page, never on a row. Which word a trade is in: by name, the consumer's lookup. How the specifications, the schedule, the holiday calendar and the conventions are tied together: the [index](index.md), since #107. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any specifications as one row per word. Market data, pricing.
