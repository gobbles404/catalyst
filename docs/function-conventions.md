# Function conventions: discussion draft

The current Globals discussion captures two worksheet functions,
[`CreateValuationDate`](valuation-date.md) and
[`CreateDiscountCurve`](discount-curve.md), and the internal library collection
[`UnitConversions`](unit-converter.md). The collection groups `volume`, `mass`,
`energy`, and `usd` and is passed within Python as one explicit object reference.
Unit definitions are owned by the library; `UnitConversions` has no Excel
constructor, handle, or workbook overrides.

The Utilities discussion now captures
[`util_InterpolateDiscountFactors`](interpolate-discount-factors.md), using the
owner's working name. Its purpose is to prepare daily discount-factor data for
the curve constructor. The `util_` prefix is not yet a general naming convention.

Capture and clarify the concepts the owner introduces. Additional function
proposals wait until the owner asks to discuss them. This scope applies to the
Globals and Utilities drafts; existing seam documentation continues to describe
the built seam and its probes.

The `CreateValuationDate`, `CreateDiscountCurve`, and `UnitConversions` names,
lowercase `reference_unit` field, `date`/`df` curve headers, and worksheet-header
casing and no-alias rules below are agreed. The remaining general naming conventions are
proposals for review.

| Item | Convention | Example |
|---|---|---|
| Worksheet functions | PascalCase: capitalize each word. | `CreateValuationDate`, `CreateDiscountCurve` |
| Parameters | snake_case, matching the wording used in Excel help. | `as_of`, `day_fraction_elapsed`, `header_row`, `values` |
| Data fields | snake_case. | `unit`, `reference_unit`, `size_in_reference_unit` |
| Worksheet headers | Agreed: document lowercase snake_case; match without regard to case. | Curve names: `date`, `df` |
| Object and seam type names | PascalCase; use the existing seam spelling where available. | `ValuationDate`, `DiscountCurve`, `UnitConversions`, `Date` |
| Category values | Exact lowercase codes, with case-sensitive matching. | `volume`, `mass`, `energy` |
| Unit codes | One documented, case-sensitive spelling per unit. | `GAL`, `BBL` |

PascalCase worksheet functions and snake_case parameters match current
code. The bridge exports the declared function name verbatim. Category and unit
codes have exact spellings in the library's definitions. Where unit codes are
used as worksheet inputs, they cross the seam unchanged; their permitted meanings
are checked in the library. Do not silently trim or change their case.

Worksheet header matching is a separate rule: header text crosses the seam
unchanged, and the library interprets it case-insensitively. Unknown names fail;
duplicates fail even if their spellings differ only in case. Each field has one
canonical name, with no aliases; `DF` is a capitalization variant of `df`, while
`Mid` is a different name and fails. Accepted field names belong to each
function's specification. Whitespace handling and column order remain open.
This header rule does not alter unit/category matching.
The curve constructor and interpolation utility use `date` and `df` only;
source names such as `Maturity` and `Mid` must be renamed, not treated as aliases.

`CreateValuationDate` retains the agreed date-and-fraction meaning: the function
name does not remove the within-day input. `UnitConversions` names the internal
combined collection, not a worksheet function or a declared seam type.

Every worksheet specification shows a typed signature and explicitly states
whether each input is scalar, row, column, or array. Worksheet help describes
meaning, units, allowed values, defaults, and shape in plain language. The
[CreateValuationDate help requirement](valuation-date.md#guidance-visible-in-excel)
is the first example.

## NumPy default and input shapes

Agreed: NumPy is the library's default for numerical arrays and calculations.
Every function specification states its inputs' scalar or array shape and, for
arrays, dtype and dimensions. Keep the worksheet declaration distinct from the
representation Python receives.

The current seam already supplies these representations:

| Worksheet declaration | Python representation | Shape |
|---|---|---|
| `Date` | `np.datetime64` scalar with day precision | Scalar |
| `float` | Python `float` | Scalar |
| `NumberArray` | NumPy `ndarray` with dtype `float64` | Two-dimensional, as supplied by Excel; `(N, 2)` for the discount-curve body |
| `NumberColumn` or `NumberRow` | NumPy `ndarray` with dtype `float64` | One-dimensional `(N,)`, after validating the declared worksheet orientation |
| `DateColumn` or `DateRow` | NumPy `ndarray` with dtype `datetime64[D]` | One-dimensional `(N,)`, after date and orientation validation |
| `TextRow` or `TextColumn` | `tuple[str, ...]` | A sequence of `N` strings, after validating the declared worksheet orientation |

These are existing types from [the seam](seam/inputs.md), not additional function
proposals. Retain these declarations in worksheet signatures: registration uses
them to select its validation and conversion rules. Replacing `NumberArray` with
an unregistered raw `np.ndarray` annotation would not preserve that contract.
Inside the library, use NumPy types directly without importing the Excel bridge.

Preserve the agreed scalar inputs to `CreateValuationDate`. NumPy by default does
not require wrapping scalar record fields in zero-dimensional or one-element
arrays. Its date is already a NumPy scalar; its fraction remains the Python float
provided by the current seam. Numeric collections use arrays; headers and unit
codes remain text, and retained objects remain typed records or collections.

The [discount-curve representation](discount-curve.md#numpy-representation)
specifies its input table and aligned internal arrays. `UnitConversions` remains
an internal collection with NumPy numerical work; no additional callable inputs
or array dimensions are introduced before those operations are specified.
