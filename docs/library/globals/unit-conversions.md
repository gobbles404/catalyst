# UnitConversions

**Normative.** The library's fixed unit definitions and the conversion between them. Why
these choices, and what they cost, is in [decisions.md](../decisions.md#units) — D13 to D17.

Not implemented. **Buildable today** — it has no worksheet surface and needs nothing from
the seam.

## Not a worksheet function

`UnitConversions` never crosses the seam. There is no Excel constructor, no handle, no
workbook table, no file path and no configuration override. Workbook users cannot create,
replace or override a definition.

Internal code that needs conversions receives one explicit Python reference to the
collection. Passing that reference shares the existing collection; it does not copy the
definitions and does not require four separate category arguments.

Unit codes do reach the worksheet as arguments of *other* functions. They cross the seam
as ordinary text, unchanged, and their permitted meanings are checked here. Help for such
an argument belongs to that argument; `UnitConversions` has no Excel help entry of its own.

## The library checks

Definition validation runs where the definitions are authored or changed, not on every
conversion. Calculations consume the typed definitions without repeating these checks.

**The shipped definitions**

| Rule | Message |
|---|---|
| unit codes unique within a category | `energy defines BTU twice` |
| every row's reference unit is its category's | `mass row LB references GAL, expected KG` |
| the reference unit's own row has size exactly `1` | `volume reference GAL has size 42, expected 1` |
| every size finite and strictly positive | `volume row L has size 0, expected greater than 0` |

**A conversion request**

| Rule | Message |
|---|---|
| the category exists, matched exactly and case-sensitively | `unknown category 'Volume'; categories are volume, mass, energy, usd` |
| both units exist in that category | `unknown unit 'GALLON' in volume; units are GAL, BBL, L, M3` |
| both units are in the same category | `cannot convert MWH to BBL; energy and volume are different categories` |

Codes are never trimmed or re-cased on the way in (D17). Category matching is
case-sensitive and is a separate rule from worksheet header matching (D19), which is not.

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

### volume

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

### mass

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| KG | KG | 1 |
| LB | KG | 0.45359237 |
| MT | KG | 1000 |
| ST | KG | 907.18474 |
| LT | KG | 1016.0469088 |

Kilogram, international avoirdupois pound, metric tonne, short ton (2000 lb), long ton
(2240 lb). Sources: [NIST conversion factors](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1038.pdf),
[NIST ton definitions](https://www.nist.gov/document/appendb-07-hb44-finalpdf). The full
names must accompany the codes in library documentation.

### energy

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| MMBTU | MMBTU | 1 |
| BTU | MMBTU | 1e-06 |
| THERM | MMBTU | 0.1 |
| GJ | MMBTU | 0.9478171203133172 |
| MWH | MMBTU | 3.4121416331279417 |

`BTU` is the International Table Btu, exactly 1055.05585262 joules. `MMBTU` is one million
of them. `THERM` is exactly 100,000 Btu_IT. `GJ` is 1e9 joules, `MWH` is 3.6e9 joules (D16).
These exact meanings must stay written down beside the codes.

### usd

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
Grouping the four categories in one collection does not permit conversion between them
(D14).

## In memory

| Thing | Representation |
|---|---|
| a definition | a typed frozen record: `str`, `str`, `float` |
| a category | its definitions and its reference unit |
| the collection | all four categories, frozen, built once |
| quantities and factors under conversion | NumPy, `float64` |

Immutability covers the collection and every definition in it. The collection is not
rebuilt per workbook or per recalculation, and no mutable reference to its contents is
handed out. Mixed text-and-numeric records stay as records; they are not packed into an
object-dtype array to make the collection "a NumPy thing" (D20).

## Counted work

Conversion is numeric work over arrays and counts. Names and expected values are not yet
fixed; D27 is open on how a counter reaches library code.

Building the collection happens once and should be observable as such — a test that
converts twice and sees one build is worth having.

## Tests

| Case | Kind | Where |
|---|---|---|
| the collection holds `volume`, `mass`, `energy`, `usd`, each with its own reference unit | example | new |
| 2 BBL → 84 GAL; 84 GAL → 2 BBL; GAL → GAL unchanged | example | new |
| 1 GAL → 3.785411784 L; 1 M3 → 1000 L | example | new |
| 1 MT → 1000 KG; 1 ST → 2000 LB; 1 LT → 2240 LB | example | new |
| 1 MWH → 3.6 GJ; 1 MMBTU → 1000000 BTU; 1 MMBTU → 10 THERM | example | new |
| 1 USD → 100 CENT; 100 CENT → 1 USD; 250 CENT → 2.5 USD | example | new |
| zero converts to zero; a negative quantity keeps its sign | example | new |
| for any quantity and any pair in a category, there and back returns the original within tolerance | property | new |
| duplicate or missing unit code fails definition validation | example | new |
| zero, negative or non-finite size fails definition validation | example | new |
| inconsistent reference unit, or a reference row whose size is not 1, fails | example | new |
| unknown category or unit, including wrong case, is rejected | example | new |
| units from different categories are rejected | example | new |
| a conversion leaves the collection and every definition unchanged | example | new |

All new; nothing here touches the seam.

The numeric rows state mathematical targets. Compare with a stated tolerance, not equality:
the relations are exact in decimal and not in binary, and the error is about one unit in the
last place (D15). Display rounding must never change a stored factor.

## Open

| | |
|---|---|
| Cross-category conversion, which needs a density or heat content the tables do not carry | D14 |
| Prices — USD/BBL, cents/gal — which are pairs of units, and have no type here | D14 |
| The `contract` category, excluded for now | D14 |
| The concrete storage layout and helper signatures, chosen at implementation | — |
| How a work counter reaches this code | D27 |

Not covered by this specification: an Excel constructor, a handle, a companion worksheet
function, FX.
