# InterpolateDiscountFactors

Ready to ship.

Turns sparse date/discount-factor points into an explicit daily table. Interpolating on the factors themselves is the library's rule for interpolation ([conventions.md](../conventions.md#what-holds-everywhere)).

## Worksheet contract

```python
def InterpolateDiscountFactors(header_row: TextRow, table: DiscountCurveTable) -> NumberArray: ...
```

The input is the table the curve takes: a header row `date` and `discount_factor`, in either order, over a body of supplied points, but gaps between source dates are expected: the first supplied date starts the generated table and the last ends it, and there is no separate start, end or valuation-date input. The seam binds the headers and checks the columns, and the library receives dates as numpy days and factors as numbers, aligned by row.

The result is data, not a handle: a numeric array spilling in two columns, `date` then `discount_factor`, with no header row, the dates as whole Excel serials to be formatted as dates on the sheet, which [outputs.md](../../seam/outputs.md) carries as a `NumberArray`. The body can be fed to `CreateDiscountCurve` as a separate call, under the same headers.

```excel
=InterpolateDiscountFactors(A1:B1, A2:B35)       spills date and discount_factor, one row per calendar day
```

## Excel help

| Item | Text |
|---|---|
| Function | Interpolates your discount factors to every calendar day from the first date to the last, and spills two columns, date and discount_factor. |
| `header_row` | The header cells of your points, such as A1:B1, reading date and discount_factor in either order. |
| `table` | The rows under the headers, such as A2:B35: one supplied point per row, the date and its discount factor, with gaps between dates allowed. |

## The library checks

The checks consume typed columns; headers, cell kinds and serials are the seam's. Messages follow the seam's grammar and name a column by its header, as the curve's do; rows count as the sheet counts them, the first row of the body being row 1.

**Source dates**

| Rule | Message |
|---|---|
| strictly increasing | `date row 12 is 2027-01-17, expected a date after row 11's 2027-02-16` |

Gaps are expected and accepted. Duplicate, reversed or otherwise unordered dates fail. The input is not sorted.

**Source factors**, the curve constructor's rules:

| Rule | Message |
|---|---|
| `discount_factor[0] == 1` exactly | `discount_factor row 1 is 0.98, expected exactly 1 at the first date` |
| non-increasing | `discount_factor rises between rows 21 and 22, from 0.91318 on 2028-08-09 to 0.92254 on 2028-11-07` |
| `discount_factor[-1] > 0` | `discount_factor row 34 is 0.0, expected greater than 0` |

An increase names both dates and both factors. Nothing is repaired, rescaled, smoothed or discarded. A failure returns no partial table.

## The interpolation

For adjacent supplied points `(date_left, df_left)` and `(date_right, df_right)`, and each whole date `d` between them:

```text
weight = calendar_days(d - date_left) / calendar_days(date_right - date_left)
df(d)  = df_left + weight * (df_right - df_left)
```

Weights count calendar days, weekends and leap days included. Every supplied point keeps its own factor exactly. One output row per calendar day from the first source date through the last, inclusive:

```text
output_rows = calendar_days(last_source_date - first_source_date) + 1
```

No dates are generated before the first source date or after the last. No endpoint extension, no extrapolation. Interpolating on `df` rather than on `log df` is a model choice, not data preparation: the implied forward rate ramps inside each gap and steps at each knot, about one basis point over a one-year gap in the owner's sample.

[`np.interp`](https://numpy.org/doc/stable/reference/generated/numpy.interp.html) is the implementation choice. It does not enforce increasing source coordinates, and outside the source range it repeats endpoint values: validate the order yourself, and generate only the inclusive range above. Its endpoint behaviour is not permission to accept out-of-range dates. Vectorized throughout; no per-row Python loops.

The first four rows of the owner's sample, through 2026-05-29, give eight rows out. The gap from May 24 to May 29 spans five calendar-day intervals; the factor change is `0.99929 − 0.9998 = −0.00051`, or `−0.000102` per day.

| date | discount_factor |
|---|---:|
| 2026-05-22 | 1 |
| 2026-05-23 | 0.9999 |
| 2026-05-24 | 0.9998 |
| 2026-05-25 | 0.999698 |
| 2026-05-26 | 0.999596 |
| 2026-05-27 | 0.999494 |
| 2026-05-28 | 0.999392 |
| 2026-05-29 | 0.99929 |

These are mathematical targets; compare with a stated `float64` tolerance. Supplied knots are preserved exactly. This is a reviewed reference output: it lands as a golden file in its own change, never beside the implementation, and this table goes when it does.

## Tests

| Case | Kind |
|---|---|
| the worked example above, to tolerance | golden, in its own change |
| first and last source dates both appear in the output | example |
| every supplied point keeps its factor exactly | property |
| output rows are exactly one calendar day apart throughout | property |
| output row count equals `days(last − first) + 1` | property |
| every interpolated value lies between its bracketing knots | property |
| the output is non-increasing given non-increasing input | property |
| already-daily input is returned unchanged | example |
| gaps spanning weekends and leap days | example |
| equal adjacent factors are preserved, not perturbed | example |
| input arrays are unchanged by the call | example |
| repeated or unordered dates rejected | example |
| a first factor other than `1` rejected | example |
| the supplied 2028 increase rejected, naming both dates and both factors | example |
| a failure returns no partial table | example |
| the eight-row spill appears in a real workbook, and its body feeds `CreateDiscountCurve` | Excel smoke |

Prefer the properties over more examples: they survive a regenerated golden and the eight-row table does not. The owner's full 34-point sample is preserved as supplied and must fail validation: the factor rises from `0.91318` on 2028-08-09 to `0.92254` on 2028-11-07, which the owner confirmed is bad input data, with no replacement values, so it is the concrete rejection case. It is not in the repository yet; it lands as a file with that test.

## Not here

Extrapolation, any curve construction, any other interpolation basis, other utilities.
