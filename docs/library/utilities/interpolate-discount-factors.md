# InterpolateDiscountFactors

Open: D18, D21, D27, D29, D30.

Turns sparse date/discount-factor points into an explicit daily table. Why these choices, and what they cost, is [decisions.md](../decisions.md#the-discount-curve), D7, D9, D10, D21 and D30. The name is the owner's working name; whether `util_` becomes a convention or an Excel category is D18.

## Worksheet contract

The input is the same `date` and `df` table the curve takes, but gaps between source dates are expected: the first supplied date starts the generated table and the last ends it, and there is no separate start, end or valuation-date input. How the table crosses the seam, and so the signature and the formula, is D21, resolved together with the curve's. Whatever the layout, the library receives dates as numpy days and factors as numbers, aligned by row, with the seam's checks already made.

The result is data, not a handle: a numeric array spilling in two columns, `date` then `df`, with no header row, the dates as whole Excel serials to be formatted as dates on the sheet, which [outputs.md](../../seam/outputs.md) carries as a `NumberArray`. Whether the date column is returned at all is part of D21. The body can be fed to `CreateDiscountCurve` as a separate call.

```excel
=InterpolateDiscountFactors(...)       spills date and df, one row per calendar day
```

## Excel help

| Item | Text |
|---|---|
| Function | Linearly interpolates supplied discount factors to every calendar day from the first date through the last. Returns two numeric columns: date and df. |
| the arguments | one line each, written when D21 names them |

## The library checks

The checks consume typed columns; headers, cell kinds and serials are the seam's. Messages follow the seam's grammar, and `values` stands for the body argument until D21 names it.

**Source dates**

| Rule | Message |
|---|---|
| strictly increasing | `values row 12 is 2027-01-17, expected a date after row 11's 2027-02-16` |

Gaps are expected and accepted. Duplicate, reversed or otherwise unordered dates fail. The input is not sorted.

**Source factors**, the curve constructor's rules (D8, D9):

| Rule | Message |
|---|---|
| `df[0] == 1` exactly | `values cell (1, 2) is 0.98, expected exactly 1 at the first date` |
| non-increasing | `factor rises between values rows 21 and 22, from 0.91318 on 2028-08-09 to 0.92254 on 2028-11-07` |
| `df[-1] > 0` | `values cell (34, 2) is 0, expected greater than 0` |

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

No dates are generated before the first source date or after the last. No endpoint extension, no extrapolation. Interpolating on `df` rather than on `log df` is a model choice, not data preparation (D10).

[`np.interp`](https://numpy.org/doc/stable/reference/generated/numpy.interp.html) is the implementation choice. It does not enforce increasing source coordinates, and outside the source range it repeats endpoint values: validate the order yourself, and generate only the inclusive range above. Its endpoint behaviour is not permission to accept out-of-range dates. Vectorized throughout; no per-row Python loops.

The first four rows of the owner's sample, through 2026-05-29, give eight rows out. The gap from May 24 to May 29 spans five calendar-day intervals; the factor change is `0.99929 − 0.9998 = −0.00051`, or `−0.000102` per day.

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

These are mathematical targets; compare with a stated `float64` tolerance. Supplied knots are preserved exactly. This is a reviewed reference output: it lands as a golden file in its own change, never beside the implementation, and this table goes when it does.

## In memory

Received: what the layout hands over, per [bridge.md](../../seam/bridge.md#the-declared-input-types). Interpolation coordinates: calendar-day offsets from the first source date, numeric. Generated: aligned date and factor arrays, each shape `(N,)`. Result: `NDArray[np.float64]`, shape `(N, 2)`, serials and factors, which the seam checks and sends.

## Counted work

Preparation, interpolation and output construction all count. Names and expected values are not yet fixed; D27 is open on how a counter reaches library code. A ten-year daily result is 3,631 rows, about 7,262 cells out against a source of 34 rows in, inside the seam's measured range.

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

## Open

| | |
|---|---|
| The input layout, and so the signature and the formula, and whether the output carries its date column | D21 |
| The final name, and whether `util_` becomes a convention or a category | D18 |
| The smallest input: whether a single supplied point returns one unchanged row | D30 |
| How a work counter reaches this code | D27 |
| The exception type a rejection raises | D29 |

## Not here

Extrapolation, any curve construction, any other interpolation basis, other utilities.
