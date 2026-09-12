# CreateValuationDate: draft specification

For review, before implementation. The owner confirmed that dates are calendar
dates, including weekends, and the fraction runs from zero through one inclusive
within the supplied date. That date is preserved. The remaining design choices
below are proposals for review.

## Purpose and worksheet contract

`ValuationDate` records the date and progress through that date at which a
calculation is evaluated. `CreateValuationDate` creates that record.

Worksheet function:

```python
def CreateValuationDate(as_of: Date, day_fraction_elapsed: float) -> ValuationDate: ...
```

`Date` is the existing seam type backed by `np.datetime64` with day precision.
The function returns a `ValuationDate` object; the seam stores it and returns its
text handle to Excel. The return annotation therefore names the object type.
Consumers use a reference to that creator cell or a defined name referring to it,
following the [handle worksheet contract](../handles/README.md).

Both inputs are scalars: one date and one number per call. Both arguments are
required initially. A missing or blank argument fails. A single-cell reference is
accepted as a scalar; an actual array, even 1x1, fails under the existing seam rules.

| Input | Contract |
|---|---|
| `as_of` | One scalar whole Excel date serial in `[61, 2958465]`, inclusive, converted by the existing seam into a NumPy calendar date. Those bounds are 1900-03-01 and 9999-12-31, using Excel's 1900 date system. Fractional serials fail. |
| `day_fraction_elapsed` | One scalar finite number in the inclusive interval `[0, 1]`. Zero is start of the supplied date; one is end of that same date. Values outside that interval fail without rounding, clipping, or advancing the date. |

The seam checks input types and converts the date once. The library builder checks
the fraction's meaning. The object is a small immutable record containing the
calendar date and the fraction, rather than a DataFrame. The pricing library does
not import the Excel bridge to define that record.

The date bounds are the existing `FIRST_SERIAL` and `LAST_SERIAL` constants in
[bridge.py](../../../src/goosedove/excel/bridge.py), enforced by its `Date` accept rule.
The builder receives the converted date and does not repeat those checks. Excel
sends numbers as doubles, so `46276.0` is a whole serial and is accepted;
`46276.5` is not. The lower bound excludes Excel's fictitious 1900-02-29 and the
earlier serials. The seam does not support the 1904 workbook date system and has
no signal with which to detect it; the builder cannot infer that setting.

## Python representation and shape

The input shapes stay scalar, as agreed. The current seam supplies:

| Input | Python representation | Shape |
|---|---|---|
| `as_of` | `np.datetime64` scalar with day precision | Scalar; not an ndarray |
| `day_fraction_elapsed` | Python `float` | Scalar; not an ndarray |

The retained record keeps those two scalar fields. There is no array allocation
just to hold one date or one fraction, and the constructor does not become a
batch input function. This follows the
[shared NumPy convention](../function-conventions.md#numpy-default-and-input-shapes):
numerical collections and calculations use NumPy arrays, while scalar metadata
keeps its declared shape. These annotations describe the existing seam's output;
the library does not repeat its type checks or import the bridge types.

## Guidance visible in Excel

Each Globals function should explain its use while the user enters the formula,
following the supplied screenshot: show the signature, highlight the active
argument, and show that argument's description. Include the meaning, expected
type or shape, allowed bounds, and any default in concise worksheet language.
The same descriptions should be available in Excel's Function Arguments dialog.

Draft wording for this function:

| Help item | Text |
|---|---|
| Function | Creates a valuation-date handle from a date and the fraction of that day elapsed. |
| `as_of` | One date: whole Excel date serial from 61 to 2958465 inclusive (1-Mar-1900 to 31-Dec-9999). Scalar; required. |
| `day_fraction_elapsed` | One number from 0 to 1 inclusive: 0 = start of as_of; 1 = EOD of as_of. The date is preserved. Scalar; required. |

The current bridge exports a function description and parameter names. The host
registers those names but does not yet supply parameter descriptions. Capture
argument guidance with the worksheet function declaration and pass it through
registration, so its wording has one maintained source.
[Excel-DNA IntelliSense](https://excel-dna.net/docs/guides-basic/Intellisense/)
provides the in-sheet help mechanism to investigate when implementing this
requirement; it is not currently referenced by the host project.

## Date and fraction semantics

The two fields remain separate. `as_of` identifies the valuation date, and
`day_fraction_elapsed` records progress within that date. Both fields belong to
the object's identity. The constructor preserves the supplied date at every
accepted fraction, including exactly one.

| `as_of` | Fraction | Interpretation | Stored date |
|---|---:|---|---|
| 2026-09-11 | 0 | Start of Friday | 2026-09-11 |
| 2026-09-11 | 0.5 | Halfway through Friday | 2026-09-11 |
| 2026-09-11 | 1 | End of Friday | 2026-09-11 |
| 2026-09-12 | 0 | Start of Saturday | 2026-09-12 |

`(2026-09-11, 1)` is EOD Friday. It is not normalized to Saturday, relabeled, or
merged with `(2026-09-12, 0)`. No business-day adjustment is performed.

EOD Friday and start of Saturday describe the same calendar-time boundary: no
additional calendar time passes between them. They remain different
date-and-fraction records because they describe progress through different named
dates. This distinction is agreed; recognizing the shared boundary does not
require adding the fields together or changing the supplied date.

This slice does not add the date and fraction into a timestamp or define elapsed
time between two records. Mapping fractions to hours, time zones, exchange
sessions, day-count arithmetic, and fixing or payment cutoffs will be specified
when the corresponding calculations are introduced. The fraction is retained
now so those later specifications can use it.

## Draft test coverage

This is a coverage proposal for review, not implemented tests. Start with the
input contract and preservation of the two fields. Reuse the seam's existing
type, shape, and date validation; test new meaning in the library builder.

### Date input: existing seam rules

The boundary examples below are already covered for `Date` in
[test_range_validation.py](../../../tests/unit/test_range_validation.py). A constructor
integration test should establish that its `as_of: Date` declaration uses that
same conversion and rejection path, without duplicating the full seam matrix.

| Input | Expected behavior |
|---|---|
| `61` | Accept; stored date is 1900-03-01. |
| `2958465` | Accept; stored date is 9999-12-31. |
| `46276` or `46276.0` | Accept; stored date is 2026-09-11. |
| `60` or `2958466` | Reject: outside the allowed date range. |
| `46276.5` | Reject: date serial is not whole; do not truncate. |

Inherited seam rules also reject text, booleans, blanks, missing required
arguments, and arrays in either scalar input. Cover representative constructor
wiring, such as text in `as_of` and a boolean in `day_fraction_elapsed`, and rely
on existing seam tests for the complete combinations. An Excel error is returned
unchanged by the host before the builder runs.

### Fraction input: new library rules

Use a valid converted date for these builder tests, so a date failure cannot
hide a fraction failure.

| Fraction | Expected behavior |
|---|---|
| `0` | Accept; start of the supplied date. |
| `0.5` | Accept; preserve the supplied fraction. |
| `1` | Accept; EOD of the supplied date, with that date preserved. |
| A representable number just below `0` | Reject; do not clamp to zero. |
| A representable number just above `1` | Reject; do not clamp to one or roll the date. |
| `-1` or `2` | Reject: outside `[0, 1]`. |
| NaN, positive infinity, or negative infinity | Reject: fraction must be finite. |

For Python boundary tests, use `np.nextafter(0.0, -np.inf)` and
`np.nextafter(1.0, np.inf)` for the immediate outside neighbors. Non-finite values
are Python-side tests, not claims that ordinary Excel cells can supply them.
Failures should identify the function, the argument, and the allowed values
through the existing error path, and publish no object or handle.

### Record behavior and general properties

- For valid dates and finite fractions in `[0, 1]`, construction preserves both
  values. Python tests inspect the created record and generate dates and fractions
  to cover this general rule.
- For finite fractions outside `[0, 1]`, construction fails. Generate values on
  both sides; keep the explicit endpoint and non-finite examples above.
- The created records match the example table in Date and fraction semantics.
  In particular, Friday at `1` and Saturday at `0` remain distinct records.
- Fraction `1` preserves weekends, leap days, year ends, and the maximum supported
  date, 9999-12-31. No following date is required to represent EOD.

An Excel smoke test should call `CreateValuationDate` for Friday at fractions `0`
and `1` and verify that each call returns a handle, then exercise an invalid date
and an invalid fraction. Python tests verify the fields of the stored objects.
Existing seam tests remain responsible for generic transport behavior.

Verify in Excel that typing the function shows its signature and that advancing
between arguments displays the appropriate descriptions above, including the
inclusive fraction bounds and EOD meaning. Check the Function Arguments dialog
as well. Metadata tests alone do not establish that the user can see the guidance.

These tests establish input and record behavior. Elapsed-time arithmetic, hourly
mapping, and pricing reference values will receive their own coverage when those
calculations are specified.

The [handle worksheet contract](../handles/README.md) captures the agreed Excel
use case and favored unchanged-input reuse direction. The mechanism, precise
reuse/equality rules, and detailed lifetime remain open; the
[Excel-DNA research](../handles/excel-dna-research.md) supports that discussion.

## Current scope

This spec captures `CreateValuationDate` within Globals: the record, its two scalar
inputs, validation, handle output, and guidance visible in Excel. The current
function scope is recorded in [function conventions](../function-conventions.md).

Use the draft coverage above to agree the acceptance cases before implementation.
Run the existing checks, Excel smoke tests, and applicable work budgets. Reviewed
pricing reference outputs come separately from changes to pricing code, under the
repository's golden-output rule.

This draft does not implement curves, conversion rules, instruments, market
calendars, pricing, hourly resolution, elapsed-time arithmetic, or general handle
reclamation.
