# One example through the whole pipeline

[Pipeline overview](README.md)

This is a fictional bilateral fixed/float average in USD, with two equally weighted
observations. It is chosen for hand arithmetic and does not define an exchange calendar,
clearing convention or complete production product schema. The future NG release has its
own named P&L measure; this example demonstrates the broader pipeline contract.

The supplied collection is the unit being valued: evaluation returns its aggregate amount
and risk. Per-trade tables below are independent hand checks or separate singleton evaluations,
not a requirement that the batch evaluator computes each trade's value on every tick.

The example starts from an approved, test-only single-index swap definition and toy product
definition, following the [instrument catalog boundary](00-instrument-definitions.md).
Their economics are fixed by the fixture; a user template supplies permitted defaults, not
a workbook-authored payoff formula.

## CreateTrades child 1: resolution

The toy index defines contract Z26 as the average of assessments on 15 and 16 December 2026,
with weights 1/2 and 1/2. Quantities are underlying units, prices USD/unit, and settlement
amounts USD. Both trades were executed on 10 December 2026. Both payments remain unpaid.

| Occurrence | Trade label | Signed quantity | Agreed price | Payment date |
|---|---|---:|---:|---|
| 0 | T1 | 100 | 70 | 5 January 2027 |
| 1 | T2 | -40 | 72 | 5 February 2027 |

Different payment dates intentionally prevent premature aggregation of valuation treatment.
They do not prevent summing the compatible undiscounted amounts for the initial result.
These are the resolved terms and static references retained by CreateTrades's first child.

## CreateTrades child 2: static encoding

```text
fixed_leg                  = [-7000, 2880]
market_inputs              = [TOY assessment 15-Dec, TOY assessment 16-Dec]
observation_coefficients   = [[ 50,  50],
                              [-20, -20]]
```

These numbers do not depend on as-of, fixing state or market prices. Each component retains
its occurrence, currency and payment date. The dense table is a reference, not a mandatory
production representation.

CreateTrades returns one handle to `TradeBatch(resolved, encoded)`, retaining the terms above
and these static arrays/market input descriptors. No fixing or current market value has been
read. The market inputs in this example are the two assessment identities. The set/live split
is established by the next stage, outside the retained static trade object.

## PrepareTrades: binding and preparation

`_PrepareTrades(trades, history)` returns an explicit prepared handle, retaining the static
trade reference and this history snapshot. The batch of two follows the same path as either
trade on its own. A history change rebuilds the whole preparation in the first version.

At the fixture valuation snapshot on 16 December, observations strictly before as-of are
fixed. The first assessment is published at 68; the second is projected from an identified
TOY Z26 remaining-assessment input. Its value is the projected level of the one unfixed
assessment, not the quoted level of the complete averaging contract. The known fixing must
actually be present in that snapshot.

The expanded contributions are set amounts `[3400, -1360]` and live coefficients
`[[50], [-20]]`. Preparation sums them for this collection:

```text
fixed_leg         = -4120            # -7000 + 2880
floating_leg_set  = 2040             # 3400 - 1360
market_axis       = [TOY Z26 remaining-assessment projection]
live_exposure     = [30]             # 50 - 20
fixed_plus_set    = -2080
```

## EvaluateTrades: evaluation and results

`_EvaluateTrades(prepared, market)` first checks that the market's history and ordered live
inputs are compatible with the preparation. It then consumes aligned prices without folding
the history again. The returned results handle identifies the whole supplied collection;
the retained source batch preserves both original occurrences and their payment facts.

At the remaining-assessment mark of 74, the batch result is:

```text
floating_leg_live = 30 * 74 = 2220
amount = -4120 + 2040 + 2220 = 140
amount_delta = [30]
```

Separately checked per-trade contributions explain that answer:

| Component | Fixed leg | Floating leg set | Floating leg live | Projected unpaid amount |
|---|---:|---:|---:|---:|
| T1 | -7000 | 3400 | 3700 | 100 |
| T2 | 2880 | -1360 | -1480 | 40 |

Independent hand check: the average is `(68 + 74) / 2 = 71`; T1 receives
`100 * (71 - 70) = 100`, and T2 receives `-40 * (71 - 72) = 40`.

This input distinction is material. If 74 instead named the whole averaging-contract level,
the remaining assessment implied by the first print of 68 would be 80. The amounts would
then be `[400, -80]`, with sensitivities `[100, -40]` to that whole-average quote. Do not feed
such a quote into the remaining-assessment column merely because both mention Z26.

Amount sensitivities to a one USD/unit move in the remaining mark are +50 and -20.
They sum to +30. These are not sensitivities to a historical fixing.

For an illustrative unpaid-payment PV extension, supply payment-date factors 0.99 and 0.98.
Hold commodity marks independent of those factors for this fixture:

| Component | Payment factor | NPV | NPV sensitivity to remaining mark |
|---|---:|---:|---:|
| T1 | 0.99 | 99.00 | 49.50 |
| T2 | 0.98 | 39.20 | -19.60 |
| Total | Not one shared factor | 138.20 | 29.90 |

The supplied factors alone do not specify a rate curve, a bump or DV01. Component sensitivity
to its supplied discount factor is its payment amount, 100 or 40; label that separately if
exposed. Neither the amount matrix nor these factors establish a rate-risk convention.

## Event expectations

| Event | Expected batch amount | Independent singleton checks | Expected work/change |
|---|---:|---|---|
| Initial snapshot above | 140 | `[100, 40]` | Encode, bind/prepare and evaluate |
| Same inputs again | 140 | `[100, 40]` | Reuse static/prepared state; exact result reuse is optional |
| Mark 74 -> 75, same history | 170 | `[150, 20]` | No static encoding, set-floating fold or re-summing trades; batch delta stays `[30]` |
| Correct first print 68 -> 69, mark stays 75 | 200 | `[200, 0]` | New history/preparation; static encoding unchanged |
| Next as-of: second print is 73, first is 69 | 140 | `[100, 40]` | Remove last live exposure; batch commodity delta becomes zero |
| Any later commodity mark changes | 140 | `[100, 40]` | No economic dependence on those marks remains |
| Amend T1 quantity to 200 with first print 69/live mark 75 | 400 | `[400, 0]` | New trade encoding/preparation; batch live delta is 80 |

At the initial amounts, changing only T2's illustrative payment factor from 0.98 to 0.97
changes total NPV from 138.20 to 137.80. Amounts and amount delta remain unchanged. This is
a factor-input scenario, not a DV01 test. A real date-roll valuation must also update its
applicable discount context; do not infer that factors stay fixed when the clock advances.

Also require batch-equals-summed-singletons equality and duplicate contribution preservation.
Two T1 occurrences at the corrected-print/live-75 state return batch amount 400; separately,
each singleton returns 200. An offsetting +100 at 70 and
-100 at 72 has zero common-mark sensitivity but a combined amount of 200.

## How engineering uses this example

Review these targets before generating library outputs. Show the input/output payload at
every stage and record which functions execute under each event. Keep a simple reference
calculation when exploring compression or cache changes. Numerical comparisons use explicit
unit-aware tolerances, not a rule that two floating-point summation orders must be bit identical.

Add a real independently resolved contract schedule in the product adapter's acceptance
tests; agreement between paths sharing one wrong schedule is insufficient. Follow the
[golden harness plan](../ethane-golden-validation-harness.md) when the actual production path
is available. Do not turn this document's illustrative arrays into an unreviewed economic oracle.

