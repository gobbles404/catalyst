# _CreateIndexConventions

Built in #68.

The index conventions of one index: the currency unit and the quantity unit its price is quoted in, the currency unit it settles in, and what its quantity measures with the unit it is stated in, five codes kept as typed and reached by handle. Since #NN the [index](index.md) holds the conventions, and nothing checks the codes yet; that check is a task for later, noted at the builder rather than on a backlog. The code is `src/goosedove/index_definitions/index_conventions.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function.

## Worksheet contract

```python
def _CreateIndexConventions(
    quote_currency_unit: str,
    quote_quantity_unit: str,
    currency_unit: str,
    quantity_type: str,
    quantity_unit: str,
) -> Handle[IndexConventions]: ...
```

| | A | B |
|---|---|---|
| 1 | quote_currency_unit | USD |
| 2 | quote_quantity_unit | BBL |
| 3 | currency_unit | USD |
| 4 | quantity_type | volume |
| 5 | quantity_unit | BBL |
| 6 | `=_CreateIndexConventions(B1, B2, B3, B4, B5)` | shows `index_conventions:3f9a1c:000008` |

Five text scalars, all required, in this order, which is fixed: the sheet passes them by position, and the code downstream takes the record's fields by name. A single-cell reference is a scalar; an array is not, even a 1×1 one, and empty text is not text. The seam checks each argument alone, left to right, against its declared type and hands over five texts; nothing here restates that. The result is a handle: text in the cell that stands for the conventions the seam keeps, declared `Handle[IndexConventions]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the conventions.

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the index conventions of one index, the units it is quoted, settled and measured in, and shows its handle, the text other formulas take as the conventions. |
| `quote_currency_unit` | The currency unit a price of the index is quoted in, such as USD. |
| `quote_quantity_unit` | The quantity unit a price of the index is quoted per, such as BBL for USD per barrel. |
| `currency_unit` | The currency unit the index settles in, such as USD. |
| `quantity_type` | What a quantity of the index measures, such as volume. |
| `quantity_unit` | The unit a quantity of the index is stated in, such as BBL. |

## The library checks

None yet. The five codes are kept as typed, never trimmed or re-cased: `volume` and `VOLUME` are two different texts, and only the first is a category of [unit-conversions.md](../globals/unit-conversions.md), which since #71 holds the categories and unit codes the check will allow. That check, that each code is one the collection defines and that a quantity unit belongs to its quantity type, is a task for later, noted at the builder so it is not lost. A failed call publishes nothing, and an argument the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_index_conventions.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the conventions; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample above: every code kept as typed, in its own field | example |
| codes in another case, a code nobody defined, a trailing space and words with a space: kept as typed, since nothing is checked yet | example |
| for any five texts, each is kept in its own field, in order | property |
| the five codes read back through the handle, in order | example, through the seam |
| a blank, a number, empty text, a one-cell range, a code left out, and two wrong at once: the seam's words, the earlier argument named | example, through the seam |
| a handle of another kind is not index conventions | example, with handles |
| the creator's handle over five cells, read back through `util_ReadHandle`, with a blank, a number and a code left out, in a real workbook | Excel smoke |

## Not here

The allowed codes: the categories and unit codes of [unit-conversions.md](../globals/unit-conversions.md), lowercase categories and uppercase units as [conventions.md](../conventions.md) lists them, which the sample above has spelt since #71; the check that the five codes are among them is its own pull request. What the conventions mean to a price or a quantity: how a price in `quote_currency_unit` per `quote_quantity_unit` becomes a settlement in `currency_unit`, the conversion between `quote_quantity_unit` and `quantity_unit`, and whether the two currency units may differ, are the first consumer's job, with [unit-conversions.md](../globals/unit-conversions.md) for the conversion. The index's name, its exchange, its futures schedule and its holiday calendar, which are handles of their own. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any conventions as one row. Market data, pricing.
