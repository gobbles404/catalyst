# CreateContractSpec

Built in #69.

A contract spec: the name of one contract, the quantity in one lot of it, and the brokerage and clearing charged per lot, four facts kept as given and reached by handle. Nothing reads the spec yet, and nothing checks the facts yet; that check is a task for later, noted at the builder rather than on a backlog. The code is `src/goosedove/market_definitions/contract_spec.py`, the record and its builder, and `src/goosedove/excel/market_definitions.py`, the worksheet function.

## Worksheet contract

```python
def CreateContractSpec(
    name: str, lot_size: int, brokerage_rate_per_lot: float, clearing_rate_per_lot: float
) -> Handle[ContractSpec]: ...
```

| | A | B |
|---|---|---|
| 1 | name | WTI |
| 2 | lot_size | 1000 |
| 3 | brokerage_rate_per_lot | 3.00 |
| 4 | clearing_rate_per_lot | 2.00 |
| 5 | `=CreateContractSpec(B1, B2, B3, B4)` | shows `contract_spec:3f9a1c:000009` |

Four scalars, all required, in this order, which is fixed: the sheet passes them by position, and the code downstream takes the record's fields by name. The name is text, any text with a character in it; the lot size is a whole number a cell holds exactly, so 1000 passes, 2.5 fails and 1E16 fails, in the words the way out uses for the same line ([inputs.md](../../seam/inputs.md) decision 41); the two fees are numbers with any fraction. A single-cell reference is a scalar; an array is not, even a 1×1 one. The seam checks each argument alone, left to right, against its declared type and hands over a text, a Python int and two floats; nothing here restates that. The result is a handle: text in the cell that stands for the spec the seam keeps, declared `Handle[ContractSpec]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the spec.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a contract spec, the name, lot size and fees per lot of one contract, and shows its handle, the text other formulas take as the spec. |
| `name` | The contract's name as the desk calls it, such as WTI. |
| `lot_size` | The quantity in one lot, a whole number such as 1000. |
| `brokerage_rate_per_lot` | The brokerage charged per lot, such as 3.00. |
| `clearing_rate_per_lot` | The clearing fee charged per lot, such as 2.00. |

## The library checks

None yet. The four facts are kept as given: the name as typed, the lot size as the whole number it arrived as, the fees as the numbers they are. Whether a lot size must be at least one, whether a fee may be negative, a rebate, and which unit the fees are in, the currency unit of the market conventions or another, are a task for later, noted at the builder so it is not lost and built when the first consumer needs the facts to mean something. A failed call publishes nothing, and an argument the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_contract_spec.py`; the seam's texts and the handle are `tests/unit/test_market_definitions.py`, whose hidden reader proves the handle resolves to the spec, typed; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample above: every fact kept, in its own field | example |
| a lot size of zero, a negative fee, a fee with a fraction and a name with spaces: kept as given, since nothing is checked yet | example |
| for any text, any whole number a cell holds exactly and any two finite numbers, each is kept in its own field, in order | property |
| the four facts read back through the handle: the name as text, the lot size as a whole number, the fees as numbers | example, through the seam |
| a lot size with a fraction, a boolean lot size, a blank name, text where a fee is expected, a fee left out, a one-cell range, and two wrong at once: the seam's words, the earlier argument named | example, through the seam |
| a handle of another kind is not a contract spec | example, with handles |
| for any lot size from −2^53 to 2^53, the spec is created and `ReadHandle` shows the lot size as it was; 1E16, 1E20 and the first double past 2^53 are refused on creation, never on reading | property and example, through the seam |
| the creator's handle over four cells, read back through `ReadHandle`, with a lot size with a fraction and one beyond what a cell holds exactly, text where a fee is expected and a fee left out, in a real workbook | Excel smoke |

## Not here

What the fees mean to a trade, how and in which unit they are charged, and what a lot converts to in the market's quantity unit: the first consumer's job, with the market conventions beside it. How a contract's spec, expiry schedule, holiday calendar and market conventions, four handles today, are tied together into one market: not decided, and a later page's question. A reader of its own: [ReadHandle](../utilities/read-handle.md) spills any spec as one row. Market data, pricing.
