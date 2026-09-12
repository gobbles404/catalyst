# util_InterpolateDiscountFactors: draft specification

The first worksheet utility: turn sparse date/discount-factor points into an
explicit daily table using linear interpolation. This captures the owner's
requested behavior before implementation. `util_InterpolateDiscountFactors` is
the working name supplied by the owner; the utility naming convention remains
to be finalized.

## Worksheet contract

```python
def util_InterpolateDiscountFactors(
    header_row: TextRow,
    values: NumberArray,
) -> NumberArray: ...
```

Both arguments are required. Use the same input layout as
[`CreateDiscountCurve`](../globals/discount-curve.md): a separate text header row and a
two-column numeric body. Agreed headers are `date` and `df`, matched without
regard to case. Rename source headers such as `Maturity` and `Mid`; they are not
accepted aliases. Unknown and duplicate headers fail, including duplicates that
differ only in case. Whitespace and column-reordering choices follow the shared
curve specification and remain open. Examples use `date` followed by `df`.

Unlike the curve constructor, this utility accepts gaps between source dates.
The first supplied date defines `as_of`; the final supplied date defines the end
of the generated table. No separate start date, end date, or valuation-date handle
is an input.

Proposed worksheet output: a numeric array that spills in two columns, `date`
then `df`, with no header row. The first column contains whole Excel date serials;
format those cells as dates in Excel. The utility returns data, not a curve handle.
The output can become the numeric body passed to `CreateDiscountCurve` with the
corresponding `date`/`df` header row. Creating the curve remains a separate call.

## Input validation

Apply the existing [date and numeric seam rules](../../seam/inputs.md), including whole
Excel date serials in `[61, 2958465]`, using the supported 1900 date system. The
[combined-table date-preparation gap](../globals/discount-curve.md#dates-and-the-existing-seam)
also applies here: `NumberArray` alone does not turn the date column into typed
dates. Reuse that preparation design rather than introducing a second parser.

The source dates must be unique and strictly increasing. Gaps are expected;
duplicate, reversed, or otherwise unordered dates fail. Do not sort the input.

Agreed: reject increasing discount factors in this utility. Source factors must
be finite, in `(0, 1]`, begin at exactly `1`, and be non-increasing in date order.
Equal factors are allowed. These are the same factor constraints as the curve
constructor, including its intentional upper limit of `1`. Do not repair,
rescale, smooth, or discard an invalid source point.

Validation failures identify the argument and offending source row or adjacent
pair. For an increase, report both dates and factors. A failure returns no partial
daily table. Whether a single supplied point returns one unchanged row remains
an edge-case decision; ordinary interpolation examples use at least two points.

## Linear interpolation on calendar days

For adjacent supplied points `(date_left, df_left)` and `(date_right, df_right)`,
and each whole date `d` between them:

```text
weight = calendar_days(d - date_left) / calendar_days(date_right - date_left)
df(d) = df_left + weight * (df_right - df_left)
```

Interpolate the discount factors directly. The weights count calendar days,
including weekends, holidays, and leap days. Every original point retains its
supplied factor. There is one output row per calendar day from `as_of` through
the final source date, including both endpoints:

```text
output_rows = calendar_days(last_source_date - first_source_date) + 1
```

Generate no dates before the first source date or after the last. There is no
endpoint extension or extrapolation. Filling gaps is explicit work performed by
this utility; `CreateDiscountCurve` continues to reject a sparse table passed
directly to it. This utility does not establish an exception to the agreed
library-wide date-bound rule; propagation of an authoritative bound remains the
shared integration question recorded in the curve specification.

## NumPy representation and implementation direction

| Stage | Representation |
|---|---|
| Headers | `TextRow`, backed by a tuple of two strings |
| Source numeric body | `NumberArray`: NumPy `float64`, shape `(K, 2)` |
| Prepared source data | Aligned one-dimensional `datetime64[D]` dates and `float64` factors, each shape `(K,)` |
| Interpolation coordinates | Calendar-day offsets from the first source date, as numeric arrays |
| Generated daily data | Aligned daily date and factor arrays, each shape `(N,)` |
| Worksheet result | `NumberArray`: NumPy `float64`, shape `(N, 2)`, containing Excel serial dates and factors |

Use vectorized NumPy operations. [`np.interp`](https://numpy.org/doc/stable/reference/generated/numpy.interp.html)
provides piecewise-linear interpolation and is the initial implementation choice.
It does not enforce increasing source coordinates, and its default behavior
outside the source range repeats endpoint factors. Validate the source order and
generate only the specified inclusive date range; do not adopt those endpoint
defaults as permission to use out-of-range dates.

The [output seam](../../seam/outputs.md) already supports numeric two-column arrays.
Combining date serials and factors for the worksheet result must use the same
date-serialization convention as the rest of the seam. Keep Excel parsing and
serialization out of the numerical interpolation code. No mixed text/numeric
output type is required because headers are not included in the returned body.

## Supplied source example and validation finding

The owner supplied these 34 points under the headings `Maturity` and `Mid`.
The table below uses the agreed `date` and `df` headers and preserves every
supplied date and factor. The date span is 3,631 calendar days, from 2026-05-22
through 2036-04-29 inclusive; a valid source over that span would produce 3,631
rows.

**This full sample must fail validation:** the factor increases from `0.91318`
on 2028-08-09 to `0.92254` on 2028-11-07. The owner confirmed this is bad input
data and that increases must be rejected. No replacement values have been
supplied; do not infer a correction.

| date | df |
|---|---:|
| 2026-05-22 | 1 |
| 2026-05-23 | 0.9999 |
| 2026-05-24 | 0.9998 |
| 2026-05-29 | 0.99929 |
| 2026-06-05 | 0.99858 |
| 2026-06-21 | 0.99685 |
| 2026-08-20 | 0.99374 |
| 2026-09-19 | 0.99049 |
| 2026-10-19 | 0.9873 |
| 2026-11-18 | 0.98063 |
| 2026-12-18 | 0.97761 |
| 2027-01-17 | 0.97424 |
| 2027-02-16 | 0.97098 |
| 2027-03-18 | 0.9676 |
| 2027-04-17 | 0.96433 |
| 2027-05-17 | 0.96098 |
| 2027-08-15 | 0.9511 |
| 2027-11-13 | 0.94133 |
| 2028-02-11 | 0.93199 |
| 2028-05-11 | 0.92254 |
| 2028-08-09 | 0.91318 |
| 2028-11-07 | 0.92254 |
| 2029-02-05 | 0.91318 |
| 2029-05-06 | 0.90393 |
| 2029-08-04 | 0.89506 |
| 2029-11-02 | 0.88598 |
| 2030-01-31 | 0.87694 |
| 2030-05-01 | 0.86799 |
| 2031-05-01 | 0.85942 |
| 2032-04-30 | 0.85064 |
| 2033-04-30 | 0.81612 |
| 2034-04-30 | 0.78196 |
| 2035-04-30 | 0.74854 |
| 2036-04-29 | 0.71587 |

## Worked valid segment

Use just the first four source rows, through 2026-05-29. With headers in `A1:B1`
and those rows in `A2:B5`, the working worksheet call is:

```excel
=util_InterpolateDiscountFactors(A1:B1, A2:B5)
```

The output has eight rows, 2026-05-22 through 2026-05-29. The gap from May 24 to
May 29 covers five calendar-day intervals. Its factor change is
`0.99929 - 0.9998 = -0.00051`, or `-0.000102` per day.

| date | df |
|---|---:|
| 2026-05-22 | 1 |
| 2026-05-23 | 0.9999 |
| 2026-05-24 | 0.9998 |
| 2026-05-25 | 0.999698 |
| 2026-05-26 | 0.999596 |
| 2026-05-27 | 0.999494 |
| 2026-05-28 | 0.999392 |
| 2026-05-29 | 0.99929 |

These are mathematical targets for direct linear interpolation; compare generated
values with a stated float64 tolerance. Preserve supplied knot values exactly as
received. The earlier daily input example in the curve specification is separate
source data and is not an expected output for this utility.

## Draft acceptance coverage and Excel guidance

Test the worked segment; inclusion of first/last dates; preservation of all source
points; one-day spacing throughout; and the exact output row count. Include
weekend and leap-day gaps, equal adjacent factors, already-daily input, and
general properties that interpolated values stay within their bracketing factors
and that the result remains non-increasing. Input arrays remain unchanged.

Rejection cases cover unknown/duplicate headers, `Maturity`/`Mid` headers,
invalid date serials, repeated or unordered dates, invalid factor ranges, a first
factor other than `1`, and any factor increase. Retain the supplied 2028 increase
as a concrete rejection case. Verify no partial result is returned on failure.
Reuse generic seam tests and the shared date-preparation path rather than adding
duplicate type-validation logic. Follow the repository's work-count requirements
for numeric preparation, interpolation, and output construction.

Draft Excel descriptions:

| Help item | Text |
|---|---|
| Function | Linearly interpolates supplied discount factors to every calendar day from the first date through the last. Returns two numeric columns: date and df. |
| `header_row` | One row containing date and df. Matching ignores case; unknown or duplicate names fail. Required. |
| `values` | Numeric date/df pairs in strictly increasing date order; gaps are allowed. Start with df 1. All factors must be greater than 0, at most 1, and non-increasing. Exclude headers. Required. |

Show these in formula-entry help and the Function Arguments dialog. An Excel
smoke case should verify the eight-row numeric spill for the valid segment and
that its body can be supplied to `CreateDiscountCurve`. Finalize the utility name,
output proposal, single-point behavior, and outstanding shared table-preparation
choices before implementation. This draft adds no executable implementation,
other utilities, or companion worksheet functions.
