# Conventions

**Normative.** Rules every specification in this directory follows. Why these choices, and
what they cost, is in [decisions.md](decisions.md#worksheet-surface) — D18 to D21.

## Names

| Item | Convention | Example |
|---|---|---|
| Worksheet functions | PascalCase | `CreateValuationDate`, `CreateDiscountCurve` |
| Parameters | snake_case, matching the wording used in Excel help | `as_of`, `day_fraction_elapsed`, `header_row`, `values` |
| Data fields | snake_case | `unit`, `reference_unit`, `size_in_reference_unit` |
| Object and seam types | PascalCase, reusing the seam's spelling where one exists | `ValuationDate`, `DiscountCurve`, `Date`, `NumberArray` |
| Worksheet headers | lowercase snake_case as documented; matched without regard to case | `date`, `df` |
| Category values | exact lowercase codes, matched case-sensitively | `volume`, `mass`, `energy`, `usd` |
| Unit codes | one documented spelling each, matched case-sensitively | `GAL`, `BBL`, `MWH` |

The bridge exports the declared function name verbatim, so the Python name *is* the
worksheet name.

`util_` on the interpolation utility is a working name, not a convention (D18).

## Worksheet headers

Header text crosses the seam unchanged; the library interprets it.

- Each field has exactly one canonical name. There are no aliases.
- Matching ignores case: `date`, `Date` and `DATE` are the same header.
- `Maturity` and `Mid` are different names and fail. Rename source data.
- Unknown names fail.
- Duplicates fail after case-insensitive matching — `date, DATE` is one header twice.
- Which names a function accepts belongs to that function's specification.

This rule covers worksheet column names only. It does not change unit or category codes,
which are matched exactly, case included.

**Open:** leading and trailing whitespace, and whether columns may be reordered when their
headers move with them (D19).

## Shapes, and what Python receives

Every specification states each input's shape, and for arrays its dtype and dimensions.
Keep the worksheet declaration distinct from the representation Python receives — the
declaration is what registration reads to choose its validation, so replacing `NumberArray`
with a bare `np.ndarray` annotation would not preserve the contract.

| Declared | Python receives | Shape |
|---|---|---|
| `Date` | `np.datetime64`, day precision | scalar |
| `float` | Python `float` | scalar |
| `NumberArray` | `NDArray[np.float64]` | two-dimensional, as supplied by Excel |
| `NumberColumn`, `NumberRow` | `NDArray[np.float64]` | one-dimensional `(N,)`, after the declared orientation is checked |
| `DateColumn`, `DateRow` | `NDArray[np.datetime64]`, `datetime64[D]` | one-dimensional `(N,)` |
| `TextRow`, `TextColumn` | `tuple[str, ...]` | `N` strings |

These are existing seam types ([inputs.md](../seam/inputs.md)), not proposals. Inside the
library use NumPy directly; do not import the bridge.

NumPy is the default for numerical arrays and calculations, `float64` the default dtype.
Scalars keep their scalar shapes — a single date is a NumPy scalar, a single fraction is a
Python float. Nothing is wrapped in a zero-dimensional or one-element array to make it
uniform (D20).

## Errors

A library rejection reaches the cell as `#ERROR {function}: {ExceptionType}: {message}`.
The exception type is part of what the user sees, so it is chosen, not defaulted.

Match the seam's message grammar:

```text
{argument} is {what arrived}, expected {what was wanted}
{argument} cell (row, col) is {what arrived}, expected {what was wanted}
```

Cells and rows count the way `INDEX` does — from 1, within the range that was passed —
because no sheet address crosses the seam. One numbering scheme, not two.

Do not import `describe` from the bridge to build a message. The pricing library does not
depend on the Excel-facing code.

A failed call publishes nothing: no partial result, no object, no handle.

## Excel help

Every worksheet function explains itself while the user types the formula: the signature,
the active argument, and that argument's description. The same wording appears in the
Function Arguments dialog.

- One maintained source. Capture the wording with the function declaration and pass it
  through registration.
- Each argument description fits about 255 characters. Longer text is truncated by Excel.
- Say the meaning, the shape, the allowed values, and whether it is required.
- Where an argument takes a unit code, its help lists the accepted codes.

**Not yet possible.** `function_specs()` exports a function description and parameter
names; the host registers those names and supplies no parameter descriptions. Both sides
have to move together.

## What a specification contains

In this order. An engineer reads to the end of Tests; a reviewer follows the links into
[decisions.md](decisions.md).

| Section | Holds |
|---|---|
| Worksheet contract | the typed signature and the formula a user types |
| The seam checks | one row per argument. Write no code and no test for any of it |
| The library checks | one row per rule of meaning, each with its exact message |
| In memory | what is received and what is retained |
| Counted work | the counters and their expected values, or "none" and why |
| Excel help | one row per item, each inside the length limit |
| Tests | case, kind, and whether it already passes |
| Open | what is not decided, pointing at the decision |

Two rules keep it honest:

**Every library check says why the seam cannot do it.** If that cannot be answered, the
check is in the wrong place — either the seam already does it, or it is meaning that does
not belong at the boundary.

**Cite the seam; never restate it.** The serial bounds, the 1904 policy, blank versus
missing and the rest live in [inputs.md](../seam/inputs.md) and
[outputs.md](../seam/outputs.md). Restating them means four documents drift when one rule
moves.
