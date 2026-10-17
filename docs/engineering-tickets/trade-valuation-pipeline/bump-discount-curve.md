# Bump a discount curve

[Pipeline overview](README.md) · [UAT item 22](surface-uat-notes.md#22-bump-a-discount-curve)

**Status:** Built in #199, 17 October 2026, as one feature PR from main after #197 and #198;
[bump-discount-curve.md](../../library/utilities/bump-discount-curve.md) owns the function. This
ticket adds a utility, not a new risk model.

## Outcome

Create a bumped discount curve from an existing curve and a signed number of basis points.
Return an ordinary curve handle that the desk can inspect and pass to `_EvaluateTrades`.
This supplies a simple way to explore rate scenarios and check the reported DV01 and
cross-gamma using the existing evaluator and readers.

## Worksheet contract

```text
util_BumpDiscountCurve(curve, bump_bps) -> discount-curve handle
```

Both arguments are required; there are no optional arguments or defaults.

| Argument | Meaning |
|---|---|
| `curve` | A live discount-curve handle, including one produced by this utility |
| `bump_bps` | A finite number of basis points: `1` means +1 bp, `-25` means -25 bp, and `0.5` means +0.5 bp |

Use the existing typed handle and numeric seam rules. Blank, missing, text, boolean,
failed-creator and wrong-kind inputs retain the normal refusals. Do not parse text such as
`"+1bp"`, round fractional bumps, or infer percentage units.

```excel
B3: =util_BumpDiscountCurve(B2,1)
B4: =util_BumpDiscountCurve(B2,-1)

=util_ReadHandle(B3)
=_EvaluateTrades(prepared,market,B3)
```

Here B2 holds the original curve. Readback uses the existing `date | discount_factor` table,
including its type row. There is no new handle kind, wrapper, reader, or evaluation signature.

## Bump convention

Apply a parallel shift to continuously compounded zero rates, using ACT/365F, matching the
existing [DV01 and cross-gamma convention](../../library/trades/evaluate-trades.md#the-cross-gamma).
For every stored daily factor:

```text
tau(t)       = calendar_days(t - curve.start_date) / 365
shift        = bump_bps / 10000
bumped_DF(t) = original_DF(t) * exp(-shift * tau(t))
```

A positive bump raises rates and lowers future discount factors; a negative bump lowers
rates and raises them. The curve supplies the time anchor. Do not read a global valuation
date or add a valuation-date argument. The evaluator retains its existing requirement that
the curve starts on the result's valuation day.

Preserve every date, the start, and the coverage. The starting factor remains exactly 1.
Shift **every stored daily factor**, including days interpolated when the source was built;
bumping sparse anchors and then interpolating them would describe a different scenario.
Zero bump preserves the dates and factors exactly. Object and handle identity for zero bump
are not part of the public contract.

## Preserve existing curve checks

Signed bumps are accepted, but the result must satisfy the same rules as any other
[discount curve](../../library/globals/discount-curve.md#the-library-checks). Reuse the
existing construction and validation path; do not introduce a second definition of validity.

In particular, discount factors must be finite, positive, start at 1, and never rise with
maturity. A downward bump that makes any adjacent factors rise fails, including when those
factors remain below 1. A curve of ones bumped down is a simple rejected case. This ticket
does not relax the library's restriction on negative implied rates.

Nonfinite arithmetic or underflow to a zero factor also fails visibly, with no curve handle
published. Do not clip factors, reduce the requested bump, rescale the curve, or return a
partially bumped result. Use the existing error style and identify the offending date or row.

## Ownership and work

Keep the arithmetic in the discount-curve library layer and the worksheet adapter thin.
The result is an immutable ordinary `DiscountCurve`; the original curve and previously
evaluated results remain unchanged. Use the existing publication, reuse and release machinery.

The operation is vectorized over stored curve dates. It does not read trades, fixings,
commodity prices, or evaluate risk. Work depends on the curve length, not trade cardinality.
Count the factors shifted and the actual construction/allocation work under the existing
work-budget conventions; state the counts in the PR. Do not add caching machinery for this
utility. A commodity tick does not dirty its inputs, so the bump is reused through the normal
Excel dependency graph while evaluation runs over the same prepared trades.

## Worked acceptance

Use a synthetic source with anchors on **4 January 2027 at 1** and **4 January 2028 at 0.95**.
The payment is 365 days from the curve start. Its factor after each bump is:

| Bump in bp | Expected factor on 4 January 2028 |
|---|---:|
| 0 | 0.95 |
| +1 | 0.9499050047498416 |
| -1 | 0.9500950047501583 |

These nonzero-bump figures are numerical targets with an explicit floating-point tolerance.
The first date remains at 1, and every intervening date is retained.

For one live nominal reporting lot paid on that date, discounted delta is 0.95 and the
original analytic cross-gamma is **-0.000095 lots per bp**. The two bumped evaluations give:

```text
(delta_up_1bp - delta_down_1bp) / 2 = approximately -0.0000950000001583
```

For a single unpaid amount of 100 on that date, NPV is 95 and analytic DV01 is
**-0.0095 currency units per bp**. The same centered comparison of the bumped NPVs
approximates that DV01. Use one existing synthetic bilateral fixture, with its observation
still live, to exercise both checks through the ordinary evaluation path.

For a general positive test bump `h` measured in **basis points**:

```text
(delta(+h) - delta(-h)) / (2*h)  approximates cross_gamma
(NPV(+h)   - NPV(-h))   / (2*h)  approximates dv01
```

There is no extra factor of 0.0001 in these comparisons: the denominator is already in basis
points. Test a small bump such as 0.1 bp with justified numerical tolerances. The analytic
risk is a derivative; a finite one-sided scenario change is not required to equal it exactly.

## Acceptance and delivery

Keep the verification focused on these behaviors:

1. The worked positive, negative and zero bumps, plus a fractional bump. Readback and
   evaluation consume the result as an ordinary curve; source arrays remain unchanged and
   output arrays are read-only.
2. An interior day from a sparse-anchor source is shifted directly. A 366-day interval
   uses `366/365`, including leap day, rather than treating every calendar year as one unit.
3. A downward bump violating the existing curve rules is refused. Extreme bumps producing
   invalid factors are refused with no publication. Ordinary negative bumps remain accepted.
4. Centered changes in both NPV and discounted lot delta agree with the saved analytic risks.
   Reuse the existing cross-gamma examples and evaluation path, not a second pricing engine.
5. The real worksheet path, readback, input failure and recovery follow existing seam, smoke,
   host and lifetime conventions. Repeated equal calls and source/bump changes use the
   ordinary handle lifecycle; held curves and results remain valid snapshots. Pin work by
   curve length and reuse across a commodity tick.

Add a small kept-workbook block showing the original and bumped curves, the reported analytic
risk, and the centered check. Give the utility one maintained function page linked to the
curve rules and risk convention rather than copying their policies. Link it from the utility
listing, update this ticket's status and the UAT entry, and run the repository checks.

Out of scope: node-specific bumps, a vector of bump sizes in one call, curve rebasing,
extrapolation, alternative compounding/day-count choices, negative-rate policy changes,
new trade fields, automatic scenario reports, and changes to valuation or risk formulas.
