# util_BumpDiscountCurve

Bumps a discount curve: a parallel shift of its continuously compounded zero rates by a signed number of basis points, the move the DV01 and the cross-gamma measure, applied to every stored day's factor from the curve's own start, ACT/365F, and shows the handle of the new curve, an ordinary curve that [util_ReadHandle](read-handle.md) spills and [_EvaluateTrades](../trades/evaluate-trades.md) takes. The desk bumps a curve a basis point up and a basis point down, re-evaluates the same prepared trades on each, and checks the reported DV01 and cross-gamma against the centered change in the NPV and in the discounted delta: a scenario tool over the existing evaluator, not a second risk model. The code is `src/catalyst/globals/discount_curve.py`, the shift beside the curve's own builder, and `src/catalyst/excel/utilities.py`, the worksheet function. [The ticket](../../engineering-tickets/trade-valuation-pipeline/bump-discount-curve.md) has the decisions.

## Worksheet contract

```python
def util_BumpDiscountCurve(
    curve: Handle[DiscountCurve], bump_bps: float
) -> Handle[DiscountCurve]: ...
```

| | A | B |
|---|---|---|
| 1 | date | discount_factor |
| 2 | 4-Jan-2027 | 1 |
| 3 | 4-Jan-2028 | 0.95 |
| 5 | `=_CreateDiscountCurve("SOFR",A1:B1,A2:B3)` | shows `30512:discount_curve:SOFR:2`, a curve of 366 days |
| 6 | `=util_BumpDiscountCurve(A5,1)` | shows `30512:discount_curve:SOFR:3`, the same days a basis point up, under the source's name |
| 7 | `=util_BumpDiscountCurve(A5,-1)` | shows `30512:discount_curve:SOFR:4`, a basis point down |
| 8 | `=INDEX(util_ReadHandle(A6),368,2)` | shows 0.949905004749842, the factor on 4 January 2028 |
| 9 | `=INDEX(util_ReadHandle(A7),368,2)` | shows 0.950095004750158 |

Two arguments, both required. The curve is a handle, the cell showing `_CreateDiscountCurve`'s result or this function's, which the seam checks as it checks any handle, as [inputs.md](../../seam/inputs.md) says: a blank, a left-out argument, text naming nothing, a number, another kind's handle and a creator's failure are refused in its words, the failure carried whole. The bump is a number, as the seam checks any number: `1` is a basis point up, `-25` twenty-five down, `0.5` half a point, `0` nothing; text such as `+1bp` is refused, nothing is parsed, nothing is rounded and no percentage is read. The result is a handle, text in the cell that stands for the new curve the seam keeps, declared `Handle[DiscountCurve]` as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says, and no new kind: the new curve keeps the source's name, in its handle and on every row of its readback, so `util_ReadHandle` spills its `date`, `discount_factor` and `name` columns under the type row as it spills any curve, a [collection](../globals/collect-discount-curves.md) takes it under that name, and `_EvaluateTrades` takes it as its curve, which must still start on the result's valuation day, as [its page](../trades/evaluate-trades.md) says; a bumped curve can be bumped again. Equal calls share one curve while any is live and it is released when Excel disconnects the last, as [handles.md](../../seam/handles.md#publication-and-release) says; a quote tick, which does not touch the curve, re-evaluates over the same bumped curve. The curve bumped is read and never written, and results already evaluated on it stand.

## The bump

For every stored day `t` of the curve, `tau(t)` the calendar days from the curve's first date over 365, weekends and leap days counted:

```text
shift     = bump_bps / 10000
bumped(t) = factor(t) * exp(-shift * tau(t))
```

Every stored day is moved, the days a sparse source filled in included, so the result is the scenario itself and not an interpolation of bumped anchors, which would be another scenario; the first factor stays 1 exactly, since `exp(0)` is 1; a bump of nothing moves nothing, bit for bit. A bump up lowers every later factor and a bump down raises them. The curve supplies the time anchor: no valuation date is read and none is taken. The ticket's example: 0.95 a year out becomes 0.9499050047498416 under +1 and 0.9500950047501583 under -1, numerical targets to a stated tolerance; a 366-day interval uses `366/365`. The rule is the one the DV01 and the cross-gamma move by, [evaluate-trades.md](../trades/evaluate-trades.md#the-cross-gamma), not another.

## The library checks

The shifted factors are built into a curve through the curve's own constructor and judged by its rules, [discount-curve.md](../globals/discount-curve.md#the-library-checks), nothing said twice here: every factor finite, the first exactly 1, none rising on the one before, the last above zero. So a bump down is accepted only while no factor rises: a curve of ones bumped down is refused by the row that rose, `discount_factor rises at row 2, from 1.0 to 1.0000002739726404`, and an ordinary falling curve bumped down is accepted; a bump so large that a factor underflows to nothing or overflows is refused by that row, in the constructor's words, under numpy's flags down. Nothing is clipped, rescaled, trimmed or returned in part, and a refusal publishes no handle. One rule is the bump's own, checked first: it is finite, a Python caller's nan or inf refused by name, which no cell can send.

## Checking the risk

The DV01 and the cross-gamma are analytic derivatives of the mark and of the delta in the rates; two evaluations on the curve bumped each way by `h` basis points approximate them by a centered difference, the denominator already in basis points:

```text
(NPV(+h)   - NPV(-h))   / (2 h)  ~  dv01
(delta(+h) - delta(-h)) / (2 h)  ~  cross_gamma
```

The ticket's checks: one live lot paid a year out at 0.95 is 0.95 of discounted delta and -0.000095 of cross-gamma, and the centered difference at one basis point is -0.0000950000001583; an unpaid amount of 100 on that day is 95 of NPV and -0.0095 of DV01, the centered difference -0.0095000000158. A finite difference carries its own truncation, so the agreement is within a stated tolerance and never exact. The kept workbook's block from row 2849 bumps the cross-gamma block's curve a basis point each way and shows the centered checks beside the saved risks.

## Excel help

Quoted from the declaration in `src/catalyst/excel/utilities.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Bumps a discount curve by a parallel shift of its continuously compounded zero rates in basis points, every day's factor moved from its start, ACT/365F, under the curve's rules, and shows the new curve's handle, an ordinary curve for _EvaluateTrades. |
| `curve` | The curve handle: the cell showing _CreateDiscountCurve's or this function's result, such as B2, or a name for it. |
| `bump_bps` | The parallel shift of the curve's zero rates in basis points, a signed number: 1 for one basis point up, -25 for twenty-five down, 0.5 for half a point; a number, not text. |

## Tests

The worked bumps, the rules, the centered checks against the evaluator's saved risks and the seam's words are `tests/unit/test_bump_discount_curve.py`; the help is pinned in `tests/unit/test_help.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Catalyst.Host.Tests/CallTests.cs`; the handle's life through a tick and a change of the source or the bump is the `bumps` group of `tools/excel_lifetime.ps1`. What a call costs is pinned in `tests/performance/test_bump_budgets.py`, the factors shifted and the constructor's work by the curve's length, and in `tests/performance/test_seam_budgets.py` and `tests/performance/test_seam_allocation.py` through the seam, one publication and its release.

## Not here

A bump of one node or a span, a vector of bumps in one call, a curve rebased to another day, extrapolation past its last date, another compounding or day count, and a policy for negative rates: none, the ticket's boundaries. A scenario report that bumps and evaluates in one cell: the sheet composes one from this function and the evaluator. Any change to the valuation or the risk formulas: none; what a curve is, and what the evaluator requires of one, are their own pages.
