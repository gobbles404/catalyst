# CreateDiscountCurve: draft specification

For review, before implementation. Agreed: the worksheet supplies a separate
text header row and one numeric table containing dates and discount factors.
Worksheet headers are documented in lowercase snake_case and matched without
regard to case. The curve begins at `as_of` with discount factor one and includes
every subsequent calendar day through its final date. That final date is the
library's hard upper date bound. Factors are finite, in `(0, 1]`, and
non-increasing. Details still requiring a decision are marked below.

## Purpose and worksheet contract

`CreateDiscountCurve` creates a `DiscountCurve` from supplied date/discount-factor
pairs. The intended result in Excel is a text handle to the retained object.

```python
def CreateDiscountCurve(
    header_row: TextRow,
    values: NumberArray,
) -> DiscountCurve: ...
```

The signature describes the agreed worksheet layout. `TextRow` and `NumberArray`
are existing seam declarations; `DiscountCurve` and its handle output are not
implemented. The return annotation names the Python object. Consumers refer to
the creator cell directly or through an Excel defined name referring to that
cell, as specified in the [handle worksheet contract](../handles/README.md).
The handle mechanism and detailed lifetime remain open.

Both shown inputs are required, with no defaults. Agreed: the first table date
defines the curve's own `as_of`, which is retained with the curve. There is no
separate `as_of` or valuation-date argument. How the curve's starting date relates
to a `ValuationDate` used in a calculation remains to be agreed.

| Input | Shape and meaning |
|---|---|
| `header_row` | One row of two text column names, identifying the date and discount-factor columns. |
| `values` | A nonempty, two-dimensional numeric body with two columns and the corresponding date/factor pairs in its rows. It excludes the header row. |

The owner's supplied example, using the agreed header names `date` and `df`:

| date | df |
|---|---:|
| 2026-05-22 | 1 |
| 2026-05-23 | 0.9999 |
| 2026-05-24 | 0.9998 |
| 2026-05-25 | 0.999697979 |
| 2026-05-26 | 0.999595969 |
| 2026-05-27 | 0.999493969 |
| 2026-05-28 | 0.999391979 |
| 2026-05-29 | 0.99929 |
| 2026-05-30 | 0.999188541 |
| 2026-05-31 | 0.999087091 |
| 2026-06-01 | 0.998985652 |
| 2026-06-02 | 0.998884224 |
| 2026-06-03 | 0.998782806 |
| 2026-06-04 | 0.998681398 |

If the headers occupy `A1:B1` and the data occupy `A2:B15`:

```excel
=CreateDiscountCurve(A1:B1, A2:B15)
```

The dates above are actual Excel dates, stored as serials `46164` through `46177`,
not text containing formatted dates. Display formatting does not cross the seam.
This curve has `as_of = 2026-05-22` and
`max_date = 2026-06-04`, covering 14 consecutive calendar dates. Preserve the
supplied factors as input examples; they are not independently validated pricing
reference outputs.

Using one body keeps each date paired with its factor and gives both columns the
same row count. Separate date and factor arguments are not part of this worksheet
contract. Supplied rows must already be in consecutive calendar-date order.

## Daily coverage and discount factors

For a body of `N` rows, the required dates are `as_of`, `as_of + 1 day`, through
`as_of + (N - 1) days`, inclusive. The first date is `as_of`; each following date
must be exactly one calendar day later. Weekends, holidays, and other nontrading
days all require their own supplied factor. Missing, duplicate, reversed, or
otherwise nonsequential dates fail. Do not sort the data, fill gaps, or generate
factors to repair the table.

The factor at `as_of` must be exactly `1`. Reject another value rather than
overwriting it or rescaling the table. Subsequent factors may also equal `1`.
Agreed: every factor must be finite and in `(0, 1]`. Zero, negative values, and
values greater than `1` fail. Do not clip factors into the interval.

Agreed: the upper limit of `1` is an intentional, artificial restriction suitable
for this library's use case, not a universal property of discount factors. The
owner is aware of and accepts the exclusion of above-one factors. For example, the
[ECB's discount-factor formula](https://www.ecb.europa.eu/pub/pdf/other/mb200812_focus04.en.pdf)
(page 41, footnote 5) implies a factor above one for a negative zero-coupon yield
over a positive maturity. Such above-one factors are excluded by this contract.

Agreed: factors must be non-increasing in date order. For each adjacent pair,
`df[i + 1] <= df[i]`. Equal consecutive factors are allowed, including a flat
curve of all ones. Reject any increase, even if both factors lie in `(0, 1]`.
Do not smooth, round, or otherwise repair an increasing sequence.

No minimum row count beyond a nonempty table has been established; confirm
whether a one-row curve containing only `as_of` is sufficient.

Every covered whole date has an explicit factor, so there is no need to
interpolate missing daily values. Intraday interpretation remains outside this
draft, including any use of `day_fraction_elapsed` from a valuation-date object.
The separately specified [interpolation utility](../utilities/interpolate-discount-factors.md)
can prepare a daily numeric table from sparse source points before this
constructor is called. The constructor itself continues to reject missing days.

## Hard upper date bound throughout the library

`max_date` is the final date in the validated table, not the largest factor.
It is inclusive: that date is covered, and any later date is out of bounds.
The owner's requirement applies to all library processes that use dates, not
only to operations that request a discount factor.
Confirmed: a process cannot opt out of the bound because its own calculation
does not technically require discounting.

A process using a date after `max_date` must fail before publishing an affected
result. The error must name the calling operation, the requested date, and the
curve's maximum allowed date, and identify the request as out of bounds. For
example, with the table above, a request for 2026-06-05 exceeds the maximum
2026-06-04. Do not extrapolate, extend the curve, substitute its final factor,
or clamp the requested date.

The implementation must make the authoritative curve and its bound available to
every relevant process, including ones that do not access a factor. The rule
applies to dates generated during processing as well as supplied dates. How that
bound is supplied, and which curve governs if several curves exist, remain to be
discussed. Do not infer a mutable "last curve created" setting. The existing
Excel-calendar type bounds remain distinct from this stricter curve-dependent
limit; the standalone valuation-date constructor currently has no curve input.

For example, a process may receive the allowed date 2026-06-04 and derive
2026-06-05 while applying a rule. If it needs to use that derived date, it must
reject it against the same curve's `max_date`, even if it never requests a
discount factor. Checking only the original input would miss the violation.
This example illustrates enforcement and does not specify a new date-adjustment
rule. Creating another curve elsewhere must not silently change the bound for
an existing calculation; the governing curve must be an explicit dependency.

Behavior for dates before `as_of` also remains open. This upper-bound requirement
does not establish a blanket prohibition on historical dates elsewhere in the
library.

## Header names and matching

Agreed: the headers are `date` and `df`. Names such as `discount_factor`,
`Maturity`, and `Mid` are not aliases. Rename source headings to the agreed names.

Header matching:

- `date`, `Date`, and `DATE` identify the same header.
- `df`, `Df`, and `DF` identify the same header.
- Unknown headers fail.
- Duplicate names fail after case-insensitive matching. For example, `date, DATE`
  is a duplicate date header, not two different columns.
- Both required names must be present, with one header per body column.

The header rule applies to worksheet column names. It does not change the exact,
case-sensitive unit and category codes in [UnitConversions](unit-conversions.md).
The seam transports header text unchanged; interpreting it belongs to the library.

The example order is `date, df`. Whether the columns may be reversed when their
headers move with them remains open. Treatment of leading/trailing whitespace
also remains open; agreeing case-insensitive matching does not decide trimming.

## Dates and the existing seam

The date column uses the same calendar rules as `CreateValuationDate`: whole
Excel serials in `[61, 2958465]` inclusive, representing 1900-03-01 through
9999-12-31 in the 1900 date system. Fractional serials fail without truncation.
Text dates, blanks, and booleans do not become dates or numbers. The unsupported
1904 workbook date system remains subject to the existing seam convention.

There is an implementation gap to resolve before building this function.
[`NumberArray`](../../../src/goosedove/excel/bridge.py) accepts numeric cells and leaves
date serials as floating-point numbers. It does not perform the validation or
conversion provided by `DateColumn`.

The existing seam checks arguments independently, and
[header-to-column matching belongs to the library](../../seam/inputs.md). Input
preparation therefore needs a deliberate design that connects column
identification with the existing date-validation and conversion rules. The
pricing code should receive typed NumPy calendar dates and numeric factors, with
each check and conversion performed once. This draft does not move raw Excel-date
parsing into pricing code or claim that the current prepared path already handles
this table. The date rules must remain consistent with the existing `Date` path.

## NumPy representation

Specify the representation explicitly so worksheet input and retained curve data
are not confused. NumPy is the numerical representation for this implementation.
This follows the [shared NumPy convention](../function-conventions.md#numpy-default-and-input-shapes).

| Stage or field | Representation |
|---|---|
| `header_row` at the seam | `TextRow`, backed by `tuple[str, ...]`, with two entries. Headers are text, not a numeric array. |
| `values` at the seam | `NumberArray`, backed by `NDArray[np.float64]`, with shape `(N, 2)`. Date cells are still Excel serials at this point. |
| Prepared and retained dates | A one-dimensional NumPy array with dtype `datetime64[D]` and shape `(N,)`. |
| Prepared and retained discount factors | A one-dimensional NumPy array with dtype `float64` and shape `(N,)`. |

The two retained arrays align by position: `dates[i]` and `df[i]` describe the
same calendar day. Retained arrays and curve metadata are immutable after
construction; later changes to input buffers must not change an existing curve.
Use vectorized NumPy operations for numeric validation and calculations, with no
per-row numeric Python loops. This representation does not resolve the separate
date-preparation or handle-lifetime design.

## Guidance visible in Excel

Follow the [shared Excel guidance requirement](valuation-date.md#guidance-visible-in-excel):
show the function signature, active-argument descriptions, and the same guidance
in the Function Arguments dialog. Draft wording uses the agreed header names:

| Help item | Text |
|---|---|
| Function | Creates a daily discount-curve handle. Its final date is the library's maximum allowed date. |
| `header_row` | One row containing date and df. Header matching ignores case; duplicate or unknown names fail. Required. |
| `values` | Two numeric columns matching the headers. Start at as_of with factor 1; include every calendar day without gaps. Dates must be whole Excel serials from 61 to 2958465 inclusive. Factors must be greater than 0, at most 1, and non-increasing; equal values are allowed. Exclude headers. Required. |

Finalize the help alongside the remaining whitespace and column-order choices.
No additional function arguments or defaults are implied by this wording.

## Draft acceptance coverage

These are proposed tests for the captured input contract, not implemented tests
or a complete curve-validation suite.

| Case | Expected behavior |
|---|---|
| Valid header row and matching two-column body | Input preparation preserves each date/factor pair. |
| Change only header casing | Same interpreted columns and date/factor pairs. |
| Unknown, missing, duplicate, or extra header | Reject with a useful header error. |
| Duplicate headers differing only in case | Reject as duplicates. |
| Header count and body width disagree | Reject; do not drop a column. |
| Header cells included in `values` | Reject through numeric-cell validation. |
| Missing argument, blank cell, boolean, or text in the numeric body | Reject through the existing seam rules. |
| Date serial `61`, `2958465`, or `46276.0` | Pass date validation and convert to the corresponding calendar date. |
| Date serial `60`, `2958466`, or `46276.5` | Reject date validation; do not clamp or truncate. |
| A fractional numeric factor such as `0.995` | Do not apply whole-date validation to the factor column. |
| First date and subsequent dates | Start at `as_of` and advance exactly one calendar day per row. |
| Consecutive dates spanning weekends, holidays, leap days, or year ends | Pass the daily-coverage rule when every calendar day is present. |
| Missing day, duplicate date, reversed rows, or another nonsequential date | Reject; do not sort or fill gaps. |
| Factor at `as_of` equals `1` | Pass the anchor rule. |
| Factor at `as_of` differs from `1` | Reject; do not rescale or replace it. |
| Zero or negative factor, factor greater than `1`, NaN, or infinity | Reject factor validation; non-finite cases can be exercised directly in Python. |
| Consecutive factors `1, 0.9999, 0.9999` | Pass the factor-ordering rule; equal values are allowed. |
| All factors equal `1` | Pass the factor-range, anchor, and ordering rules. |
| Consecutive factors `1, 0.9998, 0.9999` | Reject the increase, although all factors are within `(0, 1]`. |
| Request on `max_date` | Pass the upper-bound check. |
| Request after `max_date` | Reject as out of bounds and report the requested and maximum dates. |
| A library process uses a date after `max_date` without requesting a factor | Reject under the same library-wide bound. |
| Original date is within the bound but a derived date to be used is later than `max_date` | Reject the derived date and report the same governing curve's bound. |
| Prepared date and factor arrays | One-dimensional `datetime64[D]` and `float64` arrays of equal length, preserving date/factor pairing. |
| An input buffer changes after construction | The retained curve remains unchanged. |
| Validation fails | Publish no curve object or handle. |

Reuse the existing seam tests for generic type and shape rejection. Integration
coverage must establish that date rules reach the identified date column once;
Python tests inspect the prepared and retained data directly. Test the daily
coverage and anchor rules independently of generic date-type acceptance. Tests
for the library-wide ceiling must exercise its propagation beyond factor access
once that design is agreed. Add an Excel smoke case for constructor handle output
and representative validation failures. Verify the argument guidance in Excel itself.

Use NumPy for numerical work and follow the repository's work-count requirements
when implementing preparation and construction.

## Remaining scope

Resolve the outstanding whitespace and column-order choices and the
input-preparation design before implementation. The source and propagation
of the authoritative upper bound, behavior before `as_of`, and minimum curve
length also need discussion. Daily continuity, the intentional factor range
`(0, 1]`, the initial factor of `1`, non-increasing factors with equality allowed,
NumPy arrays, and rejection beyond the final date are established.
This draft selects no extra parameters or companion worksheet functions for the
remaining decisions.

This remains a specification; no curve implementation, handle infrastructure,
or executable tests are added here.
