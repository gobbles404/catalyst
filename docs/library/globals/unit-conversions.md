# UnitConversions

Built in #71; the category codes in capitals since #129.

The library's fixed unit definitions and the conversion between them: four categories, `VOLUME`, `MASS`, `ENERGY` and `USD`, each a reference unit and the size of every unit of it in that reference unit. Why these choices, and what they cost, are on this page. It has no worksheet surface and needs nothing from the seam. The code is `src/goosedove/globals/unit_conversions.py`: the records, the two builders that check the definitions once, the shipped definitions at its foot, and the collection they make, `UNITS`.

## Not a worksheet function

`UnitConversions` never crosses the seam. There is no Excel constructor, no handle, no
workbook table, no file path and no configuration override. Workbook users cannot create,
replace or override a definition.

Internal code that needs conversions receives one explicit Python reference to the
collection, `UNITS`, as a parameter, and never reads it for itself; the worksheet functions,
which import the library, are where the reference is passed in. Passing that reference shares
the existing collection; it does not copy the definitions and does not require four separate
category arguments.

Unit codes do reach the worksheet as arguments of *other* functions. They cross the seam
as ordinary text, unchanged, and their permitted meanings are checked here. Help for such
an argument belongs to that argument; `UnitConversions` has no Excel help entry of its own.

```python
UNITS: Final = unit_conversions(
    category(
        "VOLUME", "GAL", UnitDefinition("GAL", "GAL", 1.0), UnitDefinition("BBL", "GAL", 42.0), ...
    ),
    ...,
)


class UnitConversions:
    categories: Mapping[str, Category]

    def category(self, name: str) -> Category: ...
    def factor(self, category: str, from_unit: str, to_unit: str) -> float: ...
    def convert(
        self, quantities: NDArray[np.float64], category: str, from_unit: str, to_unit: str
    ) -> NDArray[np.float64]: ...


class Category:
    name: str
    reference_unit: str
    sizes: Mapping[str, float]

    def size_of(self, unit: str) -> float: ...
```

The collection is a frozen record of frozen records, plain Python and read-only: each category by name, and in each the size of each unit by code, in the order the tables below list them. Nothing is numpy until a conversion, which takes an array of quantities and returns a new one; a definition is a number looked up by key, not an array. Category names and unit codes are codes in capitals, as [conventions.md](../conventions.md) lists them; the category names were lowercase from #71 until #129 took them to capitals, and the desk types `VOLUME` in `_CreateIndexConventions` the same way.

## The library checks

Definition validation runs where the definitions are authored, once, when the module is
imported, and not on every conversion. Calculations consume the typed definitions without
repeating these checks.

**The shipped definitions**, checked by `category` and `unit_conversions` as they are built

| Rule | Message |
|---|---|
| unit codes unique within a category | `ENERGY defines BTU twice` |
| every row's reference unit is its category's | `MASS row LB references GAL, expected KG` |
| every size finite and strictly positive | `VOLUME row L has size 0, expected greater than 0` |
| the reference unit has a row of its own | `VOLUME reference GAL has no row, expected one with size 1` |
| the reference unit's own row has size exactly `1` | `VOLUME reference GAL has size 42, expected 1` |
| a category defined once in the collection, which keys them by name | `VOLUME is defined twice` |

The rows are checked in order, each against the three rules on a row, then the reference row, so the first row that fails is the one named. The last rule is the collection's own, from its layout: a second category of the same name would silently replace the first.

**A conversion request**, checked by `category`, `size_of` and `factor`

| Rule | Message |
|---|---|
| the category exists, matched exactly and case-sensitively | `unknown category 'Volume'; categories are VOLUME, MASS, ENERGY, USD` |
| both units exist in that category, the first that does not being named | `unknown unit 'GALLON' in VOLUME; units are GAL, BBL, L, M3` |
| both units are in the same category | `cannot convert MWH to BBL; ENERGY and VOLUME are different categories` |

A unit the category asked for does not have fails as unknown in it, unless the two units belong to two different categories, when the conversion is refused as one across categories, naming both: `MWH` to `KWH` asked for in `VOLUME` is an unknown unit in VOLUME, and `MWH` to `BBL` asked for in any category is energy to volume.

Codes are never trimmed or re-cased on the way in: a code is an identifier, not prose.
Category matching is case-sensitive and is a separate rule from worksheet header matching
([inputs.md](../../seam/inputs.md) decision 29), which is not.

## The definitions

One row means:

```text
1 unit = size_in_reference_unit reference_unit
```

| Field | Type | Meaning |
|---|---|---|
| `unit` | `str` | the unit being defined, exact code |
| `reference_unit` | `str` | the unit its size is expressed in |
| `size_in_reference_unit` | `float` | how many reference units equal one unit; finite and strictly positive |

A row is a `UnitDefinition`, and the code holds the tables below row for row, the decimal on the page being the literal in the code.

### VOLUME

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| GAL | GAL | 1 |
| BBL | GAL | 42 |
| L | GAL | 0.26417205235814845 |
| M3 | GAL | 264.17205235814845 |

`GAL` is the U.S. liquid gallon, `BBL` the petroleum barrel, `L` the litre, `M3` the cubic
metre. EIA defines the barrel as [42 U.S. gallons](https://www.eia.gov/tools/glossary/index.php?id=barrel);
[NIST Handbook 130](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=936069) gives
3.785411784 litres per U.S. gallon.

### MASS

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| KG | KG | 1 |
| LB | KG | 0.45359237 |
| MT | KG | 1000 |
| ST | KG | 907.18474 |
| LT | KG | 1016.0469088 |
| G | KG | 0.001 |
| OZT | KG | 0.0311034768 |
| CWT_US | KG | 45.359237 |

Kilogram, international avoirdupois pound, metric tonne, short ton (2000 lb), long ton
(2240 lb). Sources: [NIST conversion factors](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1038.pdf),
[NIST ton definitions](https://www.nist.gov/document/appendb-07-hb44-finalpdf). Then, since #71: `G` the gram, for precious-metal contracts and quotations expressed in grams; `OZT` the troy ounce, exactly 31.1034768 grams, for gold, silver, platinum and palladium, and explicitly not the avoirdupois ounce, which has no code here; `CWT_US` the U.S. hundredweight, 100 pounds, used in rice and dairy, its name saying which, since the imperial hundredweight is 112 pounds and has no code here. The full
names must accompany the codes in library documentation.

### ENERGY

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| MMBTU | MMBTU | 1 |
| BTU | MMBTU | 1e-06 |
| THERM | MMBTU | 0.1 |
| GJ | MMBTU | 0.9478171203133172 |
| MWH | MMBTU | 3.4121416331279417 |
| KWH | MMBTU | 0.0034121416331279417 |

`BTU` is the International Table Btu, exactly 1055.05585262 joules. `MMBTU` is one million
of them. `THERM` is exactly 100,000 Btu_IT. `GJ` is 1e9 joules, `MWH` is 3.6e9 joules, and `KWH`, since #71, is 3.6e6 joules, one thousandth of a megawatt hour, completing the common electricity scales.
These exact meanings must stay written down beside the codes.

### USD

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| USD | USD | 1 |
| CENT | USD | 0.01 |

Scales U.S.-dollar amounts. Not a currency conversion; no FX rate is involved.

## Conversion

For two units in the same category:

```text
quantity_to = quantity_from * size_from / size_to
```

Quantities may be zero or negative; the factors stay positive and the sign is preserved.
Grouping the four categories in one collection does not permit conversion between them. `factor` is `size_from / size_to`, the multiplier alone, and `convert` forms it once and multiplies the array once: in decimal that is the formula above, and in binary it rounds once more or less than dividing every quantity in turn, within the tolerance the tests state.

## Tests

| Case | Kind | Where |
|---|---|---|
| the collection holds `VOLUME`, `MASS`, `ENERGY`, `USD`, each with its own reference unit, and the units of each as listed above | example | `tests/unit/test_unit_conversions.py` |
| 2 BBL → 84 GAL; 84 GAL → 2 BBL; GAL → GAL unchanged | example | `tests/unit/test_unit_conversions.py` |
| 1 GAL → 3.785411784 L; 1 M3 → 1000 L | example | `tests/unit/test_unit_conversions.py` |
| 1 MT → 1000 KG; 1 ST → 2000 LB; 1 LT → 2240 LB; 1 OZT → 31.1034768 G; 1 CWT_US → 100 LB | example | `tests/unit/test_unit_conversions.py` |
| 1 MWH → 3.6 GJ; 1 MMBTU → 1000000 BTU; 1 MMBTU → 10 THERM; 1 MWH → 1000 KWH | example | `tests/unit/test_unit_conversions.py` |
| 1 USD → 100 CENT; 100 CENT → 1 USD; 250 CENT → 2.5 USD | example | `tests/unit/test_unit_conversions.py` |
| zero converts to zero; a negative quantity keeps its sign; a column converts in one go and is left as it was | example | `tests/unit/test_unit_conversions.py` |
| for any quantity and any pair in a category, there and back returns the original within tolerance, and the factor one way is the reciprocal of the other | property | `tests/unit/test_unit_conversions.py` |
| duplicate or missing unit code fails definition validation | example | `tests/unit/test_unit_conversions.py` |
| zero, negative or non-finite size fails definition validation | example | `tests/unit/test_unit_conversions.py` |
| inconsistent reference unit, or a reference row whose size is not 1, fails; a category defined twice fails | example | `tests/unit/test_unit_conversions.py` |
| unknown category or unit, including wrong case, is rejected, the first unknown unit named | example | `tests/unit/test_unit_conversions.py` |
| units from different categories are rejected; two units of one other category are unknown in the one asked for | example | `tests/unit/test_unit_conversions.py` |
| a conversion leaves the collection and every definition unchanged, and neither can be written to | example | `tests/unit/test_unit_conversions.py` |
| a conversion looks its factor up once, checks no definition, and allocates its result and nothing else | ledger and ceiling | `tests/performance/test_library_budgets.py` |

Nothing here touches the seam, so the pins are the library's own, in a file for code called directly.

The numeric rows state mathematical targets. Compare with a stated tolerance, not equality:
the relations are exact in decimal and not in binary, and the error is about one unit in the
last place, the tests allowing 1e-15 relative. Display rounding must never change a stored factor.

## Not here

An Excel constructor, a handle, a companion worksheet function, FX. Cross-category
conversion, which needs a density or heat content the tables do not carry; prices such as
USD/BBL or cents/gal, which are pairs of units and have no type here; and the `contract`
category, all excluded above. The check that `_CreateIndexConventions`' five codes are among these categories and units: that builder's since #110, reading this collection by key, `USD` the currency category and the other three the measures a quantity type may name. A work counter: library code takes none yet, parked with the measurement session as [README.md](../README.md) says, and a conversion's work is pinned directly instead.
