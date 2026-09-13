# CreateValuationDate

Open: D3, D4, D26, D29.

The date and progress through that date at which a calculation is evaluated. Why these choices, and what they cost, is [decisions.md](../decisions.md#dates-and-the-valuation-date), D1 to D5.

## Worksheet contract

```python
def CreateValuationDate(as_of: Date, day_fraction_elapsed: float) -> ValuationDate: ...
```

```excel
Inputs!B2   =CreateValuationDate(A2, 0.5)     A2 holds 11-Sep-2026; B2 displays a handle
```

Two scalars, both required, neither with a default. A single-cell reference is a scalar; an array is not, even a 1×1 one. The seam checks both against their declared types and hands over a numpy day and a float; nothing here restates that. `ValuationDate` is a handle, text in the cell that stands for the object held in memory, and the declaration `-> ValuationDate` is what D26 makes registrable: the seam's spec for it is [handles.md](../../seam/handles.md). Consumers refer to the creator cell or to a defined name referring to it.

## Excel help

| Item | Text |
|---|---|
| Function | Creates a valuation-date handle from a date and the fraction of that day elapsed. |
| `as_of` | One date: whole Excel date serial from 61 to 2958465 inclusive (1-Mar-1900 to 31-Dec-9999). Scalar; required. |
| `day_fraction_elapsed` | One number from 0 to 1 inclusive: 0 = start of as_of; 1 = EOD of as_of. The date is preserved. Scalar; required. |

## The library checks

| Rule | Message |
|---|---|
| `0 <= f <= 1` | `day_fraction_elapsed is number 1.5, expected a number from 0 to 1` |
| `f` is finite | `day_fraction_elapsed is number nan, expected a number from 0 to 1` |

No rounding, no clamping, no advancing the date. A value just outside the interval fails like any other. The exception type is D29. For a float the rendering is `number {value!r}`.

## In memory

Received: `as_of` as a numpy day and `day_fraction_elapsed` as a Python float, as [bridge.md](../../seam/bridge.md#the-declared-input-types) says. Retained: a frozen record of the two values, unchanged. No array is allocated for either, and the constructor does not become a batch function.

Both fields belong to the object's identity. The date is preserved at every accepted fraction, including exactly one.

| `as_of` | Fraction | Stored date |
|---|---:|---|
| 2026-09-11 | 0 | 2026-09-11 |
| 2026-09-11 | 0.5 | 2026-09-11 |
| 2026-09-11 | 1 | 2026-09-11 |
| 2026-09-12 | 0 | 2026-09-12 |

`(2026-09-11, 1)` is EOD Friday. It is not normalized to Saturday, relabeled, or merged with `(2026-09-12, 0)`. No business-day adjustment is performed.

## Counted work

None. The builder converts nothing, the seam converted the date, allocates one frozen record, and does no numeric work. It takes no `WorkCounter`. The call is a two-scalar call, which the host already pins; publishing the handle is D26's to count.

## Tests

| Case | Kind |
|---|---|
| `0`, `0.5`, `1` accepted; both fields preserved exactly | example |
| `-1`, `2`, `nextafter(0, -inf)`, `nextafter(1, +inf)` rejected, unclamped | example |
| NaN, `+inf`, `-inf` rejected | example |
| for any valid date and any `f` in `[0, 1]`, both values are preserved | property |
| for any finite `f` outside `[0, 1]`, construction fails | property |
| fraction `1` preserves weekends, leap days, year ends, and 9999-12-31 | example |
| `(2026-09-11, 1)` and `(2026-09-12, 0)` remain distinct records | example |
| a failed construction publishes no object and no handle | example, with handles |
| Friday at `0` and at `1` each return a handle; an invalid date and an invalid fraction each fail | Excel smoke, with handles |

Use `np.nextafter(0.0, -np.inf)` and `np.nextafter(1.0, np.inf)` for the boundary neighbours. Non-finite fractions are Python-side tests only: Excel sends finite doubles only, so a cell cannot produce one. The rule still belongs in the code, because the builder is reachable from Python.

## Open

| | |
|---|---|
| The ordering key, and whether the fraction stays | D3, D4 |
| The handle return type, which blocks the whole function | D26 |
| The exception type the builder raises | D29 |

## Not here

Elapsed-time arithmetic, hourly mapping, time zones, exchange sessions, day-count arithmetic, fixing and payment cutoffs, curves, instruments, market calendars, pricing.
