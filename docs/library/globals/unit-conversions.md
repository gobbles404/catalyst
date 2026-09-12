# UnitConversions: library specification draft

Agreed: unit definitions belong in the Python library. Workbook users cannot
create, replace, or override them. `UnitConversions` is one internal collection;
there is no worksheet constructor or Excel handle for it.

The categories are `volume`, `mass`, `energy`, and `usd`; `contract` is excluded.
Quantities remain part of conversion. The supplied factors are retained, with the
energy meanings and lowercase `reference_unit` field agreed below. This document
captures the definitions, ownership, and math before implementation.
See the proposed [function conventions](../function-conventions.md).

## Library ownership and implementation approach

Keep one reviewed set of definitions in a small internal Python module shipped
with the library. Use typed, immutable records for the category, unit code,
reference unit, and size. The tables below specify the initial data. The supplied
CSVs are source material for that data, not files read from a user's Downloads
folder or workbook at runtime.

Library calculations share the fixed definitions through `UnitConversions`.
Do not rebuild the collection for each workbook or recalculation, or expose
mutable references to its contents. Use NumPy for numerical conversion; the
concrete storage layout and helper signatures will be chosen during implementation.
No new worksheet functions are specified.

Apply the [shared NumPy convention](../function-conventions.md#numpy-default-and-input-shapes)
to numerical conversion data: numerical quantity and factor arrays use NumPy,
with `float64` as the default numeric dtype. Their exact shapes belong to the
operations that will consume them and are not new input contracts in this draft.
Unit and category codes remain strings, and the definition rows remain typed
records; do not put mixed text and numeric records into an object-dtype array
just to make the collection a NumPy object. Individual definition factors may
remain scalar floats. `UnitConversions` has no worksheet inputs to reshape.

Changes to codes, factors, or conventions require a reviewed library change and
the corresponding validation before shipping. There is no workbook table, file
path, or configuration override for changing the definitions. This keeps the
meaning of a unit consistent across workbooks using the same library version.

## One collection for the four categories

Agreed: `UnitConversions` groups `volume`, `mass`, `energy`, and `usd` in one
immutable collection. Each category retains its own definitions and reference
unit. Grouping them does not permit conversion between categories.

Internal code that needs unit conversions receives one explicit Python object
reference to this collection. It can select the required category and unit within
it. Passing the reference shares the existing collection; it does not copy the
definitions or require four separate category arguments. Immutability covers both
the collection and its contained definitions.

Python can pass objects directly. Neither the collection nor its categories need
text handles, handle lookup, or worksheet construction steps. The library supplies
the combined collection from its shipped definitions. This grouping specifies no
additional constructor functions.

## Meaning of one row

```text
1 unit = size_in_reference_unit reference_unit
```

| Field | Type | Meaning |
|---|---|---|
| `unit` | `str` | The unit being defined, using its exact code. |
| `reference_unit` | `str` | The unit in which its size is expressed. |
| `size_in_reference_unit` | `float` | How many reference units equal one unit; finite and strictly positive. |

## Definitions from the supplied CSVs

The four files supply 16 definitions. Their common source header is
`unit,Reference_unit,size_in_reference_unit`. The tables below use the agreed
lowercase `reference_unit` spelling; the original CSVs have not been edited.
These names describe the library's data fields, not worksheet input headers.
All supplied rows are reproduced here so a reviewer does not need the original
files from the owner's Downloads folder.

### Volume

Source: owner-supplied `volume.csv`.

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| GAL | GAL | 1 |
| BBL | GAL | 42 |
| L | GAL | 0.26417205235814845 |
| M3 | GAL | 264.17205235814845 |

The factors correspond to `GAL` as the U.S. liquid gallon, `BBL` as the petroleum
barrel, `L` as the litre, and `M3` as the cubic metre. EIA defines that barrel as
[42 U.S. gallons](https://www.eia.gov/tools/glossary/index.php?id=barrel).
[NIST Handbook 130](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=936069)
gives 3.785411784 litres per U.S. gallon. The supplied litre and cubic-metre factors
agree with that definition at floating-point precision.

### Mass

Source: owner-supplied `mass.csv`.

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| KG | KG | 1 |
| LB | KG | 0.45359237 |
| MT | KG | 1000 |
| ST | KG | 907.18474 |
| LT | KG | 1016.0469088 |

These correspond to kilogram, international avoirdupois pound, metric tonne,
short ton (2000 pounds), and long ton (2240 pounds), respectively. The supplied
factors agree with 0.45359237 kg per pound and those ton definitions, within
floating-point arithmetic. Sources: [NIST conversion factors](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication1038.pdf)
and [NIST ton definitions](https://www.nist.gov/document/appendb-07-hb44-finalpdf).
Those full names must accompany the codes in library documentation.

### Energy

Source: owner-supplied `energy.csv`.

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| MMBTU | MMBTU | 1 |
| BTU | MMBTU | 1e-06 |
| THERM | MMBTU | 0.1 |
| GJ | MMBTU | 0.9478171203133172 |
| MWH | MMBTU | 3.4121416331279417 |

Agreed: `BTU` means International Table Btu (`Btu_IT`), for which one Btu is exactly
1055.05585262 joules. `MMBTU` is one million of those Btu; `GJ` is gigajoule and
`MWH` is megawatt-hour. One GJ is 1e9 joules and one MWh is 3.6e9 joules. The two
supplied factors match conversion using that Btu definition.
Source: [NIST exact Btu definition, footnote 9](https://www.nist.gov/pml/special-publication-811/nist-guide-si-footnotes).

Agreed: `THERM` means exactly 100,000 Btu_IT, or 105505585.262 joules. Therefore
`1 THERM = 0.1 MMBTU` and `10 THERM = 1 MMBTU`. Retain the supplied factor.
Document these exact meanings of `BTU`, `MMBTU`, and `THERM` in the library so the
unit codes identify the selected definitions.

### USD

Source: owner-supplied `usd.csv`.

| unit | reference_unit | size_in_reference_unit |
|---|---|---:|
| USD | USD | 1 |
| CENT | USD | 0.01 |

These match the owner's earlier definitions. This category scales U.S.-dollar
amounts, with `USD` as the reference and `CENT` as one hundredth of a dollar.

### Review findings

All four files have three fields per row, nonempty unit/reference codes, unique
unit codes within each category, and finite positive factors. Each file uses one
reference unit and includes its self-reference row with factor one. No numerical
correction is indicated under the definitions above.

These are library unit codes with exact spellings, such as `MWH` and `MT`.
They are not an instruction to capitalize arbitrary SI symbols. Keep their full
meanings in the definitions and documentation. Where a worksheet argument uses
a unit code, its help must explain the accepted codes and their meanings. This
guidance belongs to that argument; `UnitConversions` has no separate Excel help
entry. Preserve factor precision; display rounding must not change a stored factor.

## Conversion rule

Propose one reference unit per category, with every definition expressed directly
in that reference unit. Its own row has size one. This is enough for the initial
table and does not require following chains of references. Unit codes are unique
within a category. All rows in a category use its declared reference unit.

For quantities in two units from the same category and reference basis:

```text
quantity_to = quantity_from * size_from / size_to
```

Thus 2 BBL becomes 84 GAL, and 84 GAL becomes 2 BBL. Quantity amounts may be zero
or negative; the conversion factors remain positive. Changing the denominator
unit of a price uses the reciprocal factor direction. Scaling its currency
numerator, such as dollars to cents, uses the ordinary amount-conversion direction.
These statements explain the factors; they do not specify an additional worksheet
function.

Category matching remains case-sensitive: `volume` is different from `Volume`.
Conversions stay within a category. Cross-category relationships that need
additional assumptions are not inferred from the definitions.

## Draft validation examples

These are proposed acceptance cases for the definitions and the mathematical
relationships they encode. Python tests inspect the library-owned definitions
and verify their mathematical relationships. Definition checks belong with the
shipped data; they are not worksheet table-validation cases.

| Case | Expected |
|---|---|
| Combined collection | Contains `volume`, `mass`, `energy`, and `usd`, each with its own definitions and reference unit |
| 2 BBL to GAL | 84 GAL |
| 84 GAL to BBL | 2 BBL |
| GAL to GAL | Quantity unchanged |
| 1 GAL to L | 3.785411784 L |
| 1 M3 to L | 1000 L |
| 1 MT to KG | 1000 KG |
| 1 ST to LB | 2000 LB |
| 1 LT to LB | 2240 LB |
| 1 MWH to GJ | 3.6 GJ |
| 1 MMBTU to BTU | 1000000 BTU |
| 1 MMBTU to THERM | 10 THERM |
| 1 USD to CENT | 100 CENT |
| 100 CENT to USD | 1 USD |
| 250 CENT to USD | 2.5 USD |
| Zero quantity | Zero result |
| Negative quantity | Same conversion factor, sign preserved |
| Convert there and back | Original quantity within stated floating-point tolerance |
| Missing or duplicate unit code in the definitions | Fail definition validation |
| Zero, negative, or non-finite size in reference units | Fail definition validation |
| Inconsistent reference unit, or reference row whose size is not one | Fail definition validation |
| Unknown category or unit, including incorrect case | Reject |
| Units outside the selected category/reference basis | Reject |

The numeric examples describe their mathematical targets; floating-point results
use an agreed tolerance, rather than requiring exact equality for every ratio.
Validate the definitions in Python tests when they are authored or changed.
Calculations consume the typed definitions without repeating those checks on
every call. Check numerical conversion against hand-worked examples and general
properties, and verify that calculations leave the shared collection and all
contained definitions unchanged.
Follow the repository's work-count requirements when implementing conversion.

## Current scope

Library ownership, the combined `UnitConversions` collection, and the absence of
workbook overrides are settled. This draft covers the four categories, their
definitions, shared use through one Python object reference, conversion math,
and proposed validation. It does not introduce an Excel constructor, handle, or
companion function. No library implementation or tests are added by this specification.
