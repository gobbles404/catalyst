# InterpolateDiscountFactors

**Normative.** Turns sparse date/discount-factor points into an explicit daily table. Why
these choices, and what they cost, is in [decisions.md](../decisions.md#the-discount-curve)
— D7, D9, D10, D21.

Not implemented. **The only specified worksheet function the seam can carry today** — it
returns a `NumberArray`, not a handle. It still waits on D21, which decides how its input
table crosses.

The name is provisional. The owner's working name is `util_InterpolateDiscountFactors`;
the prefix is not a convention (D18).

## Worksheet contract

The shape below is the one currently written down. **D21 is open and may change it.** It
shares the input shape with [CreateDiscountCurve](../globals/discount-curve.md) and should
keep sharing it.

```python
def InterpolateDiscountFactors(header_row: TextRow, values: NumberArray) -> NumberArray: ...
```

```excel
=InterpolateDiscountFactors(A1:B1, A2:B35)
```

Both arguments required, no defaults. Unlike the curve constructor, gaps between source
dates are expected. The first supplied date defines the start of the generated table and
the last defines its end; there is no separate start date, end date, or valuation-date
input.

**Output.** A numeric array spilling in two columns, `date` then `df`, with no header row.
The first column holds whole Excel date serials — format those cells as dates in Excel.
This returns data, not a curve handle; its body can be fed to `CreateDiscountCurve` with a
matching header row, as a separate call.

## The seam checks

Write no code and no test for anything in this section. Identical to
[CreateDiscountCurve's](../globals/discount-curve.md#the-seam-checks), including what the
seam lets through by design. The rules are [inputs.md](../../seam/inputs.md).

On the way out, [outputs.md](../../seam/outputs.md) already carries a two-dimensional
numeric array: the seam rejects a non-finite cell, an empty array, or a one-dimensional
result, naming the cell as `INDEX` counts. Keep Excel serialization out of the numerical
code; the seam converts.

## The library checks

Write all of this, and one test for each row. Messages are proposed and follow the seam's
grammar.

**Headers** — the same three rules as the curve constructor (D19).

**Source dates**

| Rule | Message |
|---|---|
| every date a whole serial inside Excel's calendar | `values cell (4, 1) is 46164.5, expected a whole date serial` |
| strictly increasing | `values row 12 is 2027-01-17, expected a date after row 11's 2027-02-16` |

Gaps are expected and accepted. Duplicate, reversed or otherwise unordered dates fail. The
input is not sorted.

**Source factors** — the same rules as the curve constructor (D8, D9), so the same three
checks: `df[0] == 1` exactly, non-increasing, `df[-1] > 0`.

| Rule | Message |
|---|---|
| `df[0] == 1` exactly | `values cell (1, 2) is 0.98, expected exactly 1 at the first date` |
| non-increasing | `factor rises between values rows 21 and 22, from 0.91318 on 2028-08-09 to 0.92254 on 2028-11-07` |
| `df[-1] > 0` | `values cell (34, 2) is 0, expected greater than 0` |

An increase names both dates and both factors. Nothing is repaired, rescaled, smoothed or
discarded. A failure returns no partial table.

## The interpolation

For adjacent supplied points `(date_left, df_left)` and `(date_right, df_right)`, and each
whole date `d` between them:

```text
weight = calendar_days(d - date_left) / calendar_days(date_right - date_left)
df(d)  = df_left + weight * (df_right - df_left)
```

Weights count calendar days, weekends and leap days included. Every supplied point keeps
its own factor exactly. One output row per calendar day from the first source date through
the last, inclusive:

```text
output_rows = calendar_days(last_source_date - first_source_date) + 1
```

No dates are generated before the first source date or after the last. No endpoint
extension, no extrapolation.

Interpolating on `df` rather than on `log df` is a model choice, not data preparation
(D10).

## In memory

| Stage | Representation |
|---|---|
| headers at the seam | `tuple[str, ...]`, two entries |
| source body at the seam | `NDArray[np.float64]`, shape `(K, 2)`; dates still serials |
| prepared source | aligned `datetime64[D]` and `float64`, each shape `(K,)` |
| interpolation coordinates | calendar-day offsets from the first source date, numeric |
| generated daily data | aligned date and factor arrays, each shape `(N,)` |
| worksheet result | `NDArray[np.float64]`, shape `(N, 2)`: serials and factors |

[`np.interp`](https://numpy.org/doc/stable/reference/generated/numpy.interp.html) is the
implementation choice. It does not enforce increasing source coordinates, and outside the
source range it repeats endpoint values — validate the order yourself, and generate only
the inclusive range above. Its endpoint behaviour is not permission to accept out-of-range
dates. Vectorized throughout; no per-row Python loops.

## Counted work

Preparation, interpolation and output construction all count. Names and expected values are
not yet fixed; D27 is open on how a counter reaches library code.

A ten-year daily result is 3,631 rows: about 7,262 result cells and 58,096 result bytes out,
one result copy, against a source of 34 rows in. Within the seam's existing measured range.

## Excel help

Each string must fit Excel's argument-help limit of about 255 characters. These are 149 and
185.

| Item | Text |
|---|---|
| Function | Linearly interpolates supplied discount factors to every calendar day from the first date through the last. Returns two numeric columns: date and df. |
| `header_row` | One row containing date and df. Matching ignores case; unknown or duplicate names fail. Required. |
| `values` | Numeric date/df pairs in strictly increasing date order; gaps are allowed. Start with df 1. All factors must be greater than 0, at most 1, and non-increasing. Exclude headers. Required. |

## Worked example

The first four rows of the owner's sample, through 2026-05-29, with headers in `A1:B1` and
the rows in `A2:B5`:

```excel
=InterpolateDiscountFactors(A1:B1, A2:B5)
```

Eight rows out. The gap from May 24 to May 29 spans five calendar-day intervals; the factor
change is `0.99929 − 0.9998 = −0.00051`, or `−0.000102` per day.

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

These are mathematical targets; compare with a stated `float64` tolerance. Supplied knots
are preserved exactly. This is a reviewed reference output — it lands as a golden file in
its own change, not alongside the implementation.

The daily example in the [curve specification](../globals/discount-curve.md) is separate
source data and is not this function's expected output.

## Tests

| Case | Kind | Where |
|---|---|---|
| the seam's type, shape and cell-naming matrix for a text row and a numeric array | example | passes today — `test_range_validation.py` |
| a two-dimensional numeric result spills as returned; a non-finite cell fails, named | example | passes today — `test_result_validation.py` |
| the worked example above, to tolerance | golden | new, own change |
| first and last source dates both appear in the output | example | new |
| every supplied point keeps its factor exactly | property | new |
| output rows are exactly one calendar day apart throughout | property | new |
| output row count equals `days(last − first) + 1` | property | new |
| every interpolated value lies between its bracketing knots | property | new |
| the output is non-increasing given non-increasing input | property | new |
| already-daily input is returned unchanged | example | new |
| gaps spanning weekends and leap days | example | new |
| equal adjacent factors are preserved, not perturbed | example | new |
| input arrays are unchanged by the call | example | new |
| unknown, duplicate, or `Maturity`/`Mid` headers rejected | example | new |
| invalid date serials, repeated or unordered dates rejected | example | new |
| a first factor other than `1` rejected | example | new |
| the supplied 2028 increase rejected, naming both dates and both factors | example | new |
| a failure returns no partial table | example | new |
| the eight-row spill appears in a real workbook, and its body feeds `CreateDiscountCurve` | Excel smoke | new |

Two already pass. Prefer the properties over more examples — they survive a regenerated
golden and the eight-row table does not.

**A note on the owner's full 34-point sample.** It is preserved as supplied and **must fail
validation**: the factor rises from `0.91318` on 2028-08-09 to `0.92254` on 2028-11-07. The
owner confirmed that is bad input data. No replacement values exist; do not infer a
correction. Keep it as the concrete rejection case.

## Open

| | |
|---|---|
| How the input table crosses the seam, which decides the signature and the date rules | D21 |
| The final name, and whether `util_` becomes a convention or a category | D18 |
| Header whitespace, and whether columns may be reordered | D19 |
| Whether a single supplied point returns one unchanged row | — |
| Whether the output should carry its date column at all, given the date-formatting cost of a spill whose size changes | D21 |

Not covered by this specification: extrapolation, any curve construction, any other
interpolation basis, other utilities.
