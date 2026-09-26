# _CreateValuationDate

Built in #53.

The date and progress through that date at which a calculation is evaluated. What is still open about it, the fraction nothing uses yet, is under Not here. The code is `src/goosedove/globals/valuation_date.py`, the record and its builder, and `src/goosedove/excel/globals.py`, the worksheet function.

## Worksheet contract

```python
def _CreateValuationDate(as_of: Date, day_fraction_elapsed: float) -> Handle[ValuationDate]: ...
```

```excel
Inputs!B2   =_CreateValuationDate(A2, 0.5)     A2 holds 11-Sep-2026; B2 shows valuation_date:1
```

Two scalars, both required, neither with a default. A single-cell reference is a scalar; an array is not, even a 1×1 one. The seam checks both against their declared types and hands over a numpy day and a float; nothing here restates that. The result is a handle: text in the cell that stands for the object the seam keeps, declared `Handle[ValuationDate]`, as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says. Consumers refer to the creator cell or to a defined name referring to it, and receive the object. What is still open about handles, release above all, is [handles.md](../../seam/handles.md).

## Excel help

Quoted from the declaration in `src/goosedove/excel/globals.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Creates a valuation date and shows its handle, the text other formulas take as the valuation date. |
| `as_of` | The valuation date, a date cell such as 11-Sep-2026, with no time of day. |
| `day_fraction_elapsed` | How far through as_of: 0 at the start of the day, 0.5 at midday, 1 at the end. |

## The library checks

| Rule | Message |
|---|---|
| `0 <= f <= 1` | `day_fraction_elapsed is number 1.5, expected a number from 0 to 1` |
| `f` is finite | `day_fraction_elapsed is number nan, expected a number from 0 to 1` |

No rounding, no clamping, no advancing the date. A value just outside the interval fails like any other. For a float the rendering is `number {value!r}`. Both fields are kept exactly as supplied: the date is preserved at every accepted fraction, including exactly one, so `(2026-09-11, 1)` is the end of Friday and is not normalized to Saturday, relabeled, or merged with `(2026-09-12, 0)`.

## Tests

The examples and properties below are `tests/unit/test_valuation_date.py`; the seam's texts and the handle are `tests/unit/test_globals.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`.

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

## Not here

Ordering two valuation dates, and whether the fraction stays: its first consumer, the calendar of #82, reads the day alone and never the fraction, and `(2026-09-11, 1)` and `(2026-09-12, 0)` are two records that describe one moment, so the first function that orders two valuation dates, or measures the time between them, decides both. Elapsed-time arithmetic, hourly mapping, time zones, exchange sessions, day-count arithmetic, fixing and payment cutoffs, curves, instruments, market calendars, pricing.
