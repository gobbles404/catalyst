# CreateMarketConventions

Built in #68.

The market conventions of one index: the currency unit and the quantity unit its price is quoted in, the currency unit it settles in, and what its quantity measures with the unit it is stated in, five codes kept as typed and reached by handle. Nothing reads the conventions yet, and nothing checks the codes yet; that check is a task for later, noted at the builder rather than on a backlog. The code is `src/goosedove/market_definitions/market_conventions.py`, the record and its builder, and `src/goosedove/excel/market_definitions.py`, the worksheet function.

## Worksheet contract

```python
def CreateMarketConventions(
    quote_currency_unit: str,
    quote_quantity_unit: str,
    currency_unit: str,
    quantity_type: str,
    quantity_unit: str,
) -> Handle[MarketConventions]: ...
```

| | A | B |
|---|---|---|
| 1 | quote_currency_unit | USD |
| 2 | quote_quantity_unit | BBL |
| 3 | currency_unit | USD |
| 4 | quantity_type | VOLUME |
| 5 | quantity_unit | BBL |
| 6 | `=CreateMarketConventions(B1, B2, B3, B4, B5)` | shows `market_conventions:3f9a1c:000008` |

Five text scalars, all required, in this order, which is fixed: the sheet passes them by position, and the code downstream takes the record's fields by name. A single-cell reference is a scalar; an array is not, even a 1×1 one, and empty text is not text. The seam checks each argument alone, left to right, against its declared type and hands over five texts; nothing here restates that. The result is a handle: text in the cell that stands for the conventions the seam keeps, declared `Handle[MarketConventions]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the conventions.

## Excel help

Quoted from the declaration in `src/goosedove/excel/market_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates the market conventions of one index, the units it is quoted, settled and measured in, and shows its handle, the text other formulas take as the conventions. |
| `quote_currency_unit` | The currency unit a price of the index is quoted in, such as USD. |
| `quote_quantity_unit` | The quantity unit a price of the index is quoted per, such as BBL for USD per barrel. |
| `currency_unit` | The currency unit the index settles in, such as USD. |
| `quantity_type` | What a quantity of the index measures, such as VOLUME. |
| `quantity_unit` | The unit a quantity of the index is stated in, such as BBL. |

## The library checks

None yet. The five codes are kept as typed, never trimmed or re-cased: `VOLUME` and `volume` are two different texts. Which codes are allowed, the unit codes and the categories of [unit-conversions.md](../globals/unit-conversions.md), and that a quantity unit belongs to its quantity type, is a task for later, noted at the builder so it is not lost and built when the first consumer needs the codes to mean something; a list guessed at today would refuse codes nobody has decided on. A failed call publishes nothing, and an argument the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_market_conventions.py`; the seam's texts and the handle are `tests/unit/test_market_definitions.py`, whose hidden reader proves the handle resolves to the conventions; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`.

| Case | Kind |
|---|---|
| the sample above: every code kept as typed, in its own field | example |
| codes in another case, a code nobody defined, a trailing space and words with a space: kept as typed, since nothing is checked yet | example |
| for any five texts, each is kept in its own field, in order | property |
| the five codes read back through the handle, in order | example, through the seam |
| a blank, a number, empty text, a one-cell range, a code left out, and two wrong at once: the seam's words, the earlier argument named | example, through the seam |
| a handle of another kind is not market conventions | example, with handles |
| the creator's handle over five cells, read back through `ReadHandle`, with a blank, a number and a code left out, in a real workbook | Excel smoke |

## Not here

The allowed codes and their spelling: [conventions.md](../conventions.md) lists category values as exact lowercase codes, `volume`, while the desk types `VOLUME`; the later check decides which, and the sample above moves with it. What the conventions mean to a price or a quantity: how a price in `quote_currency_unit` per `quote_quantity_unit` becomes a settlement in `currency_unit`, the conversion between `quote_quantity_unit` and `quantity_unit`, and whether the two currency units may differ, are the first consumer's job, with [unit-conversions.md](../globals/unit-conversions.md) for the conversion. The index's name, its exchange, its expiry schedule and its holiday calendar, which are handles of their own. A reader of its own: [ReadHandle](../utilities/read-handle.md) spills any conventions as one row. Market data, pricing.
