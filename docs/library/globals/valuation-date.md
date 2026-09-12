# CreateValuationDate

**Status: specified, not buildable.** See [Blocked on](#blocked-on) — the handle return
type does not exist at the seam, and declaring one refuses to register.

Everything above the rule is the contract; an engineer needs only that. Everything below
it is why, and is for a reviewer. Nothing in this document is implemented.

## What it is

`ValuationDate` records the date and progress through that date at which a calculation is
evaluated. `CreateValuationDate` creates one and returns its handle.

## Worksheet contract

```python
def CreateValuationDate(as_of: Date, day_fraction_elapsed: float) -> ValuationDate: ...
```

```excel
Inputs!B2   =CreateValuationDate(A2, 0.5)     A2 holds 11-Sep-2026; B2 displays a handle
```

Two scalars, both required, neither with a default. A single-cell reference is a scalar;
an array is not, even a 1×1 one. Consumers refer to the creator cell or to a defined name
referring to it, per the [handle worksheet contract](../handles/README.md).

## The seam checks

You write none of this, and no test for any of it. The rules are
[inputs.md](../../seam/inputs.md); the messages below are the seam's own, produced by
running it.

| Argument | Declared | Accepts | Rejects |
|---|---|---|---|
| `as_of` | `Date` | one whole Excel serial in `[61, 2958465]`, handed over as `np.datetime64[D]` | text, boolean, blank, missing, any array, a fraction, a serial outside the calendar |
| `day_fraction_elapsed` | `float` | one number | text, boolean, blank, missing, any array |

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

You write all of this, and one test for each row. The seam hands the builder a converted
date and a float and has already stopped everything in the table above.

| Rule | Message | Why the seam cannot |
|---|---|---|
| `0 <= f <= 1` | `day_fraction_elapsed is number 1.5, expected a number from 0 to 1` | the seam checks type and shape, never a value against a bound — [inputs.md](../../seam/inputs.md) rule 6 |
| `f` is finite | `day_fraction_elapsed is number nan, expected a number from 0 to 1` | same; and see the note below on reachability |

No rounding, no clamping, no advancing the date. A value just outside the interval fails
like any other.

Match the seam's message grammar — `{argument} is {what arrived}, expected {what was
wanted}` — but **do not import `describe` from the bridge**: the pricing library does not
depend on the Excel-facing code. For a float the rendering is `number {value!r}`.

## In memory

| Field | Type | Shape |
|---|---|---|
| `as_of` | `np.datetime64` with day precision | scalar, not an ndarray |
| `day_fraction_elapsed` | Python `float` | scalar, not an ndarray |

A small frozen record. No array is allocated to hold one date and one fraction, and the
constructor does not become a batch function. Both fields belong to the object's identity.
This follows the [shared NumPy convention](../function-conventions.md#numpy-default-and-input-shapes):
numerical collections use arrays, scalar metadata keeps its declared shape.

## Counted work

**None, and that is the answer.** The builder converts nothing — the seam already
converted the date — allocates one frozen record, and does no numeric work. It takes no
`WorkCounter`.

The call still costs what any two-scalar call costs, which the host already pins:
`objects_built 2`, `trips 1`. Publishing the handle will cost more, and cannot be
measured until handles exist.

## Excel help

Each string must fit Excel's argument-help limit of about 255 characters. These are 109
and 112.

| Item | Text |
|---|---|
| Function | Creates a valuation-date handle from a date and the fraction of that day elapsed. |
| `as_of` | One date: whole Excel date serial from 61 to 2958465 inclusive (1-Mar-1900 to 31-Dec-9999). Scalar; required. |
| `day_fraction_elapsed` | One number from 0 to 1 inclusive: 0 = start of as_of; 1 = EOD of as_of. The date is preserved. Scalar; required. |

There is nowhere to put these yet — see [Blocked on](#blocked-on).

## Tests

| Case | Kind | Where |
|---|---|---|
| `61` → 1900-03-01, `2958465` → 9999-12-31, `46164` → 2026-05-22, `75` → 1900-03-15 | example | **passes today** — `test_accepted`, `test_range_validation.py` |
| `46164.5`, `60`, `2958466`, `1e19`, text, a 1×1 array all rejected as `Date` | example | **passes today** — `test_rejected`, `test_range_validation.py` |
| text, boolean, blank, missing, array rejected in a `float` slot | example | **passes today** — `test_scalar_matrix`, `test_type_validation.py` |
| a library exception reaches the cell as `#ERROR Fn: ValueError: message` | example | **passes today** — `test_library_failure_names_function_type_and_message` |
| `0`, `0.5`, `1` accepted; both fields preserved exactly | example | new |
| `-1`, `2`, `nextafter(0, -inf)`, `nextafter(1, +inf)` rejected, unclamped | example | new |
| NaN, `+inf`, `-inf` rejected | example | new |
| for any valid date and any `f` in `[0, 1]`, construction preserves both values | property | new |
| for any finite `f` outside `[0, 1]`, construction fails | property | new |
| fraction `1` preserves weekends, leap days, year ends, and 9999-12-31 | example | new |
| `(2026-09-11, 1)` and `(2026-09-12, 0)` remain distinct records | example | new |
| a failed construction publishes no object and no handle | example | new, blocked on handles |
| Friday at `0` and at `1` each return a handle; an invalid date and an invalid fraction each fail | Excel smoke | new, blocked on handles |
| typing the formula shows the signature, and stepping between arguments shows each description; same in the Function Arguments dialog | Excel smoke | new, blocked on help plumbing |

**Eleven of the fifteen rows are new; four already pass.** Write no test that duplicates
one of those four — the seam's matrix is complete and is not this function's to restate.

For the Python boundary tests use `np.nextafter(0.0, -np.inf)` and
`np.nextafter(1.0, np.inf)`. Non-finite fractions are Python-side tests only: Excel sends
"always a finite double" ([inputs.md](../../seam/inputs.md)), so a cell cannot produce one.
The rule still belongs in the code, because the builder is reachable from Python.

Metadata tests do not establish that a user can see the guidance. Check it in Excel.

## Blocked on

| Decision | Who decides | What unblocks it |
|---|---|---|
| **The handle return type.** `_RESULTS` in [bridge.py](../../../src/goosedove/excel/bridge.py) carries ten declared results and no handle. Declaring one is refused by `_result` at **registration**, which runs at import, so `AutoOpen` catches it and *no* function registers — not this one, not `Ping`, not a probe. The add-in does not degrade; it fails to load. | seam | a `_RESULTS` entry that stores an object and returns its text, a `_DECLARED` entry that resolves text back, and a home for the registration that does not make the library import the bridge |
| **Which exception the builder raises**, since the type is part of what the cell shows: `#ERROR CreateValuationDate: {Type}: {message}`. `ValueError` reads as noise. | owner | pick a type whose name reads well in a cell |
| **Argument help has nowhere to go.** `function_specs()` exports name, description, parameter names and hidden; the host builds `ExcelArgumentAttribute { Name = p }` with no `Description`. | seam and host together | widen `function_specs()` and set the description; both sides move in one change |

Open, but not blocking:

- **`day_fraction_elapsed` has no consumer yet.** It is retained now so later
  specifications can use it.
- **Ordering is undefined, and there is a tie waiting.** `(2026-09-11, 1.0)` and
  `(2026-09-12, 0.0)` are the same instant and different records, both agreed. The first
  function that orders two valuation dates, or measures elapsed time between them, meets a
  pair that sorts strictly but is zero apart. Deciding the ordering key now costs nothing;
  deciding it after two callers exist does not.

## PR plan

Two pull requests, in this order. This document specifies only the second.

1. **The handle type at the seam.** One object kind, in and out, with its store. Does not
   add a worksheet function, does not decide release timing, does not touch the library.
2. **`CreateValuationDate`.** The record, the fraction rule, the tests marked new above.
   Does not add elapsed-time arithmetic, hourly mapping, curves, or any second object.

Argument help can land in either, or its own; nothing here depends on it except the last
test row.

---

# Notes

Reviewer's context. None of this is contract.

## What was agreed, and what is proposed

The owner confirmed that dates are calendar dates, weekends included, and that the
fraction runs from zero through one inclusive within the supplied date, which is
preserved. The two-scalar shape and the `[0, 1]` interval follow from that. The message
wording, the exception type, and the test list are proposals.

`Date` is the existing seam type backed by `np.datetime64` with day precision. The return
annotation names the Python object, and the seam stores it and returns its text handle.

## Date and fraction semantics

The two fields stay separate. `as_of` identifies the valuation date; the fraction records
progress within it. The constructor preserves the supplied date at every accepted
fraction, including exactly one.

| `as_of` | Fraction | Interpretation | Stored date |
|---|---:|---|---|
| 2026-09-11 | 0 | Start of Friday | 2026-09-11 |
| 2026-09-11 | 0.5 | Halfway through Friday | 2026-09-11 |
| 2026-09-11 | 1 | End of Friday | 2026-09-11 |
| 2026-09-12 | 0 | Start of Saturday | 2026-09-12 |

`(2026-09-11, 1)` is EOD Friday. It is not normalized to Saturday, relabeled, or merged
with `(2026-09-12, 0)`. No business-day adjustment is performed.

EOD Friday and start of Saturday describe the same calendar-time boundary: no additional
calendar time passes between them. They remain different records because they describe
progress through different named dates. Recognizing the shared boundary does not require
adding the fields together or changing the supplied date. It does mean the ordering
question above is real.

This slice does not add the date and fraction into a timestamp or define elapsed time
between two records. Mapping fractions to hours, time zones, exchange sessions, day-count
arithmetic, and fixing or payment cutoffs will be specified when the corresponding
calculations are introduced.

## Why the date bounds are the seam's and not the builder's

The bounds are the existing `FIRST_SERIAL` and `LAST_SERIAL` constants in
[bridge.py](../../../src/goosedove/excel/bridge.py), enforced by its `Date` accept rule.
The builder receives the converted date and does not repeat those checks. Excel sends
numbers as doubles, so `46276.0` is a whole serial and is accepted; `46276.5` is not. The
lower bound excludes Excel's fictitious 1900-02-29 and the earlier serials.

The seam does not support the 1904 workbook date system and has no signal with which to
detect it, so the builder cannot infer that setting either. That is the seam's policy and
is recorded in [inputs.md](../../seam/inputs.md), not restated as a rule of this function.

## Why a record and not a DataFrame

Two scalar fields, read far more often than they are built, and never iterated. A frozen
record is the smaller thing that works, and it keeps the pricing library free of any
import from the Excel bridge.

## Where the Excel help mechanism stands

The current bridge exports a function description and parameter names; the host registers
those names but supplies no parameter descriptions. Capture argument guidance with the
worksheet function declaration and pass it through registration, so its wording has one
maintained source.

[Excel-DNA IntelliSense](https://excel-dna.net/docs/guides-basic/Intellisense/) provides
the in-sheet help mechanism to investigate when implementing this. It is not currently
referenced by the host project, and the host registers through
`ExcelIntegration.RegisterDelegates`, which is not the pipeline IntelliSense hooks.

## Not done

No curves, conversion rules, instruments, market calendars, pricing, hourly resolution,
elapsed-time arithmetic, handle infrastructure, or general handle reclamation. No
executable tests. The [handle worksheet contract](../handles/README.md) captures the
agreed Excel use case and the favored unchanged-input reuse direction; the mechanism,
precise reuse and equality rules, and detailed lifetime remain open, with the
[Excel-DNA research](../handles/excel-dna-research.md) supporting that discussion.

Reviewed pricing reference outputs come separately from changes to pricing code, under
the repository's golden-output rule.
