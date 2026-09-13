# CreateValuationDate

**Normative.** The date and progress through that date at which a calculation is
evaluated. Why these choices, and what they cost, is in
[decisions.md](../decisions.md#dates-and-the-valuation-date) — D1 to D5.

Not implemented. Not buildable until the seam can return a handle (D26).

## Worksheet contract

```python
def CreateValuationDate(as_of: Date, day_fraction_elapsed: float) -> ValuationDate: ...
```

```excel
Inputs!B2   =CreateValuationDate(A2, 0.5)     A2 holds 11-Sep-2026; B2 displays a handle
```

Two scalars, both required, neither with a default. A single-cell reference is a scalar;
an array is not, even a 1×1 one. Consumers refer to the creator cell or to a defined name
referring to it ([handles.md](../handles.md)).

## The seam checks

Write no code and no test for anything in this section. The rules are
[inputs.md](../../seam/inputs.md).

| Argument | Declared | Accepts | Rejects |
|---|---|---|---|
| `as_of` | `Date` | one whole Excel serial in `[61, 2958465]`, handed over as `np.datetime64[D]` | text, boolean, blank, missing, any array, a fraction, a serial outside the calendar |
| `day_fraction_elapsed` | `float` | one number | text, boolean, blank, missing, any array |

The messages, produced by running the seam:

```text
as_of is text '2026-09-11', expected date
as_of is boolean TRUE, expected date
as_of is blank, expected date
as_of is missing, expected date
as_of is number 46276.5, expected date
as_of is number 60.0, expected date
as_of is number 2958466.0, expected date
as_of is 1x1 array, expected date
day_fraction_elapsed is text 'half', expected number
day_fraction_elapsed is boolean TRUE, expected number
day_fraction_elapsed is blank, expected number
day_fraction_elapsed is missing, expected number
day_fraction_elapsed is 1x1 array, expected number
```

Each reaches the cell prefixed `#ERROR CreateValuationDate: `. The builder never runs.

## The library checks

Write all of this, and one test for each row.

| Rule | Message |
|---|---|
| `0 <= f <= 1` | `day_fraction_elapsed is number 1.5, expected a number from 0 to 1` |
| `f` is finite | `day_fraction_elapsed is number nan, expected a number from 0 to 1` |

No rounding, no clamping, no advancing the date. A value just outside the interval fails
like any other.

Match the seam's message grammar — `{argument} is {what arrived}, expected {what was
wanted}` — but do not import `describe` from the bridge to do it; the pricing library does
not depend on the Excel-facing code. For a float the rendering is `number {value!r}`.

## In memory

| Field | Type | Shape |
|---|---|---|
| `as_of` | `np.datetime64` with day precision | scalar, not an ndarray |
| `day_fraction_elapsed` | Python `float` | scalar, not an ndarray |

Frozen after construction. Both fields belong to the object's identity. The date is
preserved at every accepted fraction, including exactly one.

| `as_of` | Fraction | Stored date |
|---|---:|---|
| 2026-09-11 | 0 | 2026-09-11 |
| 2026-09-11 | 0.5 | 2026-09-11 |
| 2026-09-11 | 1 | 2026-09-11 |
| 2026-09-12 | 0 | 2026-09-12 |

`(2026-09-11, 1)` is EOD Friday. It is not normalized to Saturday, relabeled, or merged
with `(2026-09-12, 0)`. No business-day adjustment is performed.

## Counted work

None. The builder converts nothing — the seam converted the date — allocates one frozen
record, and does no numeric work. It takes no `WorkCounter`.

The call costs what any two-scalar call costs, which the host already pins:
`objects_built 2`, `trips 1`. Publishing the handle will cost more and cannot be measured
until handles exist.

## Excel help

Each string fits Excel's argument-help limit of about 255 characters. These are 109 and 112.

| Item | Text |
|---|---|
| Function | Creates a valuation-date handle from a date and the fraction of that day elapsed. |
| `as_of` | One date: whole Excel date serial from 61 to 2958465 inclusive (1-Mar-1900 to 31-Dec-9999). Scalar; required. |
| `day_fraction_elapsed` | One number from 0 to 1 inclusive: 0 = start of as_of; 1 = EOD of as_of. The date is preserved. Scalar; required. |

There is nowhere to put these yet: `function_specs()` exports no argument descriptions and
the host builds `ExcelArgumentAttribute { Name = p }` without one.

## Tests

| Case | Kind | Where |
|---|---|---|
| `61` → 1900-03-01, `2958465` → 9999-12-31, `46164` → 2026-05-22, `75` → 1900-03-15 | example | passes today — `test_accepted`, `test_range_validation.py` |
| `46164.5`, `60`, `2958466`, `1e19`, text, a 1×1 array rejected as `Date` | example | passes today — `test_rejected`, `test_range_validation.py` |
| text, boolean, blank, missing, array rejected in a `float` slot | example | passes today — `test_scalar_matrix`, `test_type_validation.py` |
| a library exception reaches the cell as `#ERROR Fn: ValueError: message` | example | passes today — `test_library_failure_names_function_type_and_message` |
| `0`, `0.5`, `1` accepted; both fields preserved exactly | example | new |
| `-1`, `2`, `nextafter(0, -inf)`, `nextafter(1, +inf)` rejected, unclamped | example | new |
| NaN, `+inf`, `-inf` rejected | example | new |
| for any valid date and any `f` in `[0, 1]`, both values are preserved | property | new |
| for any finite `f` outside `[0, 1]`, construction fails | property | new |
| fraction `1` preserves weekends, leap days, year ends, and 9999-12-31 | example | new |
| `(2026-09-11, 1)` and `(2026-09-12, 0)` remain distinct records | example | new |
| a failed construction publishes no object and no handle | example | new, needs handles |
| Friday at `0` and at `1` each return a handle; an invalid date and an invalid fraction each fail | Excel smoke | new, needs handles |
| typing the formula shows the signature and each argument's description; same in the Function Arguments dialog | Excel smoke | new, needs help plumbing |

Eleven of fifteen are new; four already pass. Write nothing that duplicates those four —
the seam's matrix is complete and is not this function's to restate.

Use `np.nextafter(0.0, -np.inf)` and `np.nextafter(1.0, np.inf)` for the boundary
neighbours. Non-finite fractions are Python-side tests only: Excel sends finite doubles
only, so a cell cannot produce one. The rule still belongs in the code, because the
builder is reachable from Python.

Metadata tests do not establish that a user can see the guidance. Check it in Excel.

## Open

| | |
|---|---|
| The ordering key, and whether the fraction stays | D3, D4 |
| The handle return type, which blocks the whole function | D26 |
| Which exception type the builder raises, since it is part of what the cell shows | D26 |
| Where argument help lives | D18 |

Not covered by this specification: elapsed-time arithmetic, hourly mapping, time zones,
exchange sessions, day-count arithmetic, fixing and payment cutoffs, curves, instruments,
market calendars, pricing.
