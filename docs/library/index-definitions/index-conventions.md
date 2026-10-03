# _CreateIndexConventions

Built in #68; the codes checked since #110; the quantity type in capitals since #129.

The index conventions of one index: the currency unit and the quantity unit its price is quoted in, the currency unit it settles in, and what its quantity measures with the unit it is stated in, five codes kept as typed and reached by handle, and from #110 checked against the library's unit tables. Since #107 the [index](index.md) holds the conventions. The codes were kept unchecked from #68, the check noted at the builder for the first consumer's arrival; the [follow-ups](../follow-ups.md) pinned it on 26 September 2026, this build does it once, in the creator, so that pricing reads codes that mean something, and that page marks the item resolved. The code is `src/goosedove/index_definitions/index_conventions.py`, the record and its builder, and `src/goosedove/excel/index_definitions.py`, the worksheet function, which hands the builder the library's unit collection, `UNITS`, as [unit-conversions.md](../globals/unit-conversions.md) says a reader receives it.

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

The signature does not change, and neither do the record and its read-back. Two indices, WTI quoted and settled in dollars per barrel, and a gasoline index quoted in cents per gallon and settled in dollars per barrel:

| | A | B | C |
|---|---|---|---|
| 1 | quote_currency_unit | USD | CENT |
| 2 | quote_quantity_unit | BBL | GAL |
| 3 | currency_unit | USD | USD |
| 4 | quantity_type | VOLUME | VOLUME |
| 5 | quantity_unit | BBL | BBL |
| 6 | `=_CreateIndexConventions(B1, B2, B3, B4, B5)` | shows `30512:index_conventions:8` | |
| 7 | `=_CreateIndexConventions(C1, C2, C3, C4, C5)` | shows `30512:index_conventions:9`, cents and dollars two units of one currency, gallons and barrels two units of one measure | |

Five text scalars, all required, in this order, which is fixed: the sheet passes them by position, and the code downstream takes the record's fields by name. A single-cell reference is a scalar; an array is not, even a 1×1 one, and empty text is not text. The seam checks each argument alone, left to right, against its declared type and hands over five texts; nothing here restates that. Each code is one the [unit tables](../globals/unit-conversions.md) define, spelt as they spell it: a currency unit is `USD` or `CENT`, the units of the tables' one currency; a quantity type is `VOLUME`, `MASS` or `ENERGY`, the categories a quantity can measure; and the two quantity units are units of that category, GAL, BBL, L or M3 for a volume, so that a price quoted per gallon and a quantity stated in barrels are two units of one measure, and the conversion between them is one factor. The result is a handle: text in the cell that stands for the conventions the seam keeps, declared `Handle[IndexConventions]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the conventions, the five codes.

`=util_ReadHandle(A6)` shows the five codes as they went in, one row under the two heading rows, as it did before: the spill does not change.

| quote_currency_unit | quote_quantity_unit | currency_unit | quantity_type | quantity_unit |
|---|---|---|---|---|
| str | str | str | str | str |
| USD | BBL | USD | VOLUME | BBL |

## Excel help

Quoted from the declaration in `src/goosedove/excel/index_definitions.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog. Where an argument takes a code, its help lists the codes, as [conventions.md](../conventions.md) asks.

| Item | Text |
|---|---|
| Function | Creates the index conventions of one index, the units it is quoted, settled and measured in, checked against the library's unit tables, and shows its handle, the text other formulas take as the conventions. |
| `quote_currency_unit` | The currency unit a price of the index is quoted in: USD or CENT. |
| `quote_quantity_unit` | The quantity unit a price of the index is quoted per, a unit of the quantity type: GAL, BBL, L or M3 for VOLUME; KG, LB, MT, ST, LT, G, OZT or CWT_US for MASS; MMBTU, BTU, THERM, GJ, MWH or KWH for ENERGY. |
| `currency_unit` | The currency unit the index settles in: USD or CENT. |
| `quantity_type` | What a quantity of the index measures: VOLUME, MASS or ENERGY. |
| `quantity_unit` | The unit a quantity of the index is stated in, a unit of the quantity type: GAL, BBL, L or M3 for VOLUME; KG, LB, MT, ST, LT, G, OZT or CWT_US for MASS; MMBTU, BTU, THERM, GJ, MWH or KWH for ENERGY. |

## The library checks

Five rules, in this order, the first failure being the message: the two currency units, which depend on nothing else, then the quantity type, then the two quantity units, which are judged by it. Each code is matched exactly, spelling and case as typed, never trimmed or re-cased, since a code is an identifier and not prose: `VOLUME` is a category and `Volume` is not, nor is `volume`, the spelling before #129, as [unit-conversions.md](../globals/unit-conversions.md) decided. The quantity type is in capitals since #129, as every other code the desk types here is, the owner having found one word in small letters odd beside four codes in capitals. A message names the argument, what arrived and the codes that would have done, the tables' units in the tables' order.

| Rule | Message |
|---|---|
| the quoted currency unit is a currency unit, `USD` or `CENT` | `quote_currency_unit is 'usd', expected USD or CENT` |
| the settlement currency unit is a currency unit | `currency_unit is 'EUR', expected USD or CENT` |
| the quantity type is a category a quantity can measure: `VOLUME`, `MASS` or `ENERGY`, and not `USD`, which scales money | `quantity_type is 'Volume', expected VOLUME, MASS or ENERGY` |
| the quoted quantity unit is a unit of the quantity type | `quote_quantity_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3` |
| the stated quantity unit is a unit of the quantity type | `quantity_unit is 'bbl', expected a VOLUME unit, GAL, BBL, L or M3` |

The two quantity units may differ, as may the two currency units, so long as each pair is of one category: cents per gallon quoted and dollars per barrel settled is accepted, dollars per pound quoted and a quantity in tonnes is accepted, and dollars per barrel quoted with a quantity in tonnes is refused at the quoted unit, a barrel being no mass unit. That is what the tables convert, a scale within one category and never a rate between two, so an index quoted in one currency and settled in another waits for a currency category the tables do not hold. Nothing else is checked, and nothing is converted or computed here: the codes are kept as typed, and the factor between two units, the one that turns a price quoted in `quote_currency_unit` per `quote_quantity_unit` into a price in `currency_unit` per `quantity_unit`, is the instrument's to look up once when it is made, from [unit-conversions.md](../globals/unit-conversions.md). Membership is five lookups in the tables, and not one numpy call. A failed call publishes nothing, and an argument the seam rejects never reaches the function.

## Tests

The examples and properties below are `tests/unit/test_index_conventions.py`; the seam's texts and the handle are `tests/unit/test_index_definitions.py`, whose hidden reader proves the handle resolves to the conventions; the spill is `tests/unit/test_utilities.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`. What a call costs is pinned in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py`: the five lookups, and not one numpy call.

| Case | Kind |
|---|---|
| the sample above: every code kept as typed, in its own field | example |
| the gasoline index, cents per gallon settled in dollars per barrel; gas, dollars per MMBTU settled in dollars per MMBTU; a metal quoted per pound and stated in tonnes: accepted, each pair two units of one category | example |
| every unit of each category accepted as the stated and as the quoted quantity unit, and every pair of USD and CENT in the two currency slots | example |
| a currency unit in another case, a unit nobody defined, one with a space and a quantity unit where a currency unit should be, in either currency slot: refused, naming USD and CENT | example |
| a category in another case, in small letters as it was once typed, a category nobody defined, one with a space and `USD` where the quantity type should be: refused, naming the three categories | example |
| a quantity unit of another category, one in another case, one with a space and one nobody defined, in either quantity slot: refused, naming the type's units in the tables' order; the same under `MASS` and under `ENERGY` | example |
| the two currency units checked before the quantity type, and the type before the quantity units, two wrong at once naming the earlier | example |
| for any category, any two of its units and any two currency units, the conventions are made and keep the five codes as typed | property |
| for any five texts none of which is a code, the quoted currency unit is the rule named | property |
| the five codes read back through the handle, in order, as before | example, through the seam |
| a code nobody defined, one in another case and a unit of another category, the library's words; a blank, a number, empty text, a one-cell range, a code left out, and two wrong at once: the seam's words, the earlier argument named | example, through the seam |
| a failed construction publishes no object and no handle; a handle of another kind is not index conventions | example, with handles |
| the spill: five headers, five types, one row, as before | example |
| the creator's handle over five cells and over the gasoline index read back through `util_ReadHandle`, a code in another case and a unit of another category, the library's words, with a blank, a number and a code left out, the seam's, in a real workbook | Excel smoke |

## Not here

A currency other than the dollar, and a rate between two currencies: the unit tables hold one currency category, `USD`, and convert no FX; when another currency arrives it is a category of its own there, and the rule that both currency units of one index are of one category is already written above. The price scale, the factor that turns a price quoted in `quote_currency_unit` per `quote_quantity_unit` into one in `currency_unit` per `quantity_unit`, and the conversion of a quantity between the two quantity units: the instrument's, looked up once from [unit-conversions.md](../globals/unit-conversions.md) when the instrument is made; nothing is computed or converted here, and the record holds the five codes and nothing derived. A trailing space or another case accepted as the code meant: never; a code is typed as the tables spell it, and the message lists them. New units or categories: the tables' own page. The index's name, its exchange, its schedule and its holiday calendar, which are handles of their own, bound in the [index](index.md). The fees, which the [specifications](contract-specifications.md) page states are in the settlement currency named here, read off the index by their consumer. A reader of its own: [util_ReadHandle](../utilities/read-handle.md) spills any conventions as one row of five. Market data, pricing.
