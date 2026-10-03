# Prepared trades: one exposure vector for the supplied batch

[Pipeline overview](README.md) · [Preparation](03-market-binding.md) · [Evaluation](04-evaluation.md)

**Status:** Agreed aggregate-result direction, 3 October 2026. Numerical examples are fictional
and hand-checkable, not exchange contract specifications or production goldens. Discounting
is deferred. The first scope combines compatible undiscounted amounts in one currency.

## The collection is the unit being valued

`_EvaluateTrades(prepared, market)` values the collection supplied to preparation. A collection
of 100 trades produces one aggregate amount and its market-risk vector. To value one trade,
supply a one-trade collection through the same pipeline. Preparing/evaluating subsets is
conceptually the same operation; a convenience function for selecting subsets is not yet specified.

The earlier expanded trade matrix remains useful for understanding and checking the economics.
It does not require the production evaluator to calculate 100 individual values before summing
them. Preparation can sum coefficients directly by identified live market input.

| Retained preparation | Shape | Meaning |
|---|---|---|
| Source trade batch | One reference | Every original occurrence, terms, schedules and payment facts |
| `fixed_leg`, for fixed/float amounts | One aggregate amount | Sum of the batch's static fixed legs, reusable from creation |
| `floating_leg_set` | One aggregate amount | Sum of history-dependent floating contributions |
| `live_exposure` | M coefficients | Batch's net signed exposure to each identified live input |
| Ordered market axis | M identities | Meaning and units of each vector position |
| History/layout references | Immutable dependencies | Establish where this preparation is valid |

Preserving original occurrences means duplicates contribute fully and source facts remain
inspectable. It does not mean every tick computes individual trade values. A reader of the
aggregate result cannot recover those values without a separate evaluation.

## Five schedules, shown expanded only to explain preparation

Use one fictional assessment index with five ordered observations, D1 through D5. The window's
penultimate observation is D4 and its last observation is D5. Quantities are underlying units,
prices are currency/unit, and averaging weights are equal. Every payment is unpaid.

| Trade | Example | Explicit payoff |
|---|---|---|
| T1 | Asian average | 100 x (average(D1,D2,D3,D4,D5) - 70) |
| T2 | Last day | -40 x (D5 - 75) |
| T3 | Penultimate | 60 x (D4 - 73) |
| T4 | Last three days | 30 x (average(D3,D4,D5) - 72) |
| T5 | Illustrative same-index CFD | 10 x (D5 - D4) |

CFD alone does not define a schedule. T5 explicitly defines both sides of a same-index
difference; the eventual desk CFD convention remains to be established. No second index
is introduced. T5 has no fixed leg; its zero agreed spread adds zero to the fixed amount.
Actual calendar, publication and reference-contract rules must be resolved upstream.

At this snapshot D1 has fixed at 68 and D2 at 69. The market supplies separate identified
remaining-assessment projections for D3, D4 and D5. Their current prices are not needed in
preparation. The expanded contributions and their sums are:

| Contribution | fixed_leg | floating_leg_set | D3 exposure | D4 exposure | D5 exposure |
|---|---:|---:|---:|---:|---:|
| T1 | -7,000 | 2,740 | 20 | 20 | 20 |
| T2 | 3,000 | 0 | 0 | 0 | -40 |
| T3 | -4,380 | 0 | 0 | 60 | 0 |
| T4 | -2,160 | 0 | 10 | 10 | 10 |
| T5 | Not applicable (zero addition) | 0 | 0 | -10 | 10 |
| **Batch** | **-10,540** | **2,740** | **30** | **80** | **0** |

For T1, each observation's coefficient is 100 / 5 = 20. Its set portion is
20 x 68 + 20 x 69 = 2,740. The unfixed observations keep coefficients of 20;
do not renormalize the original five-observation payoff to one-third weights.

Preparation retains the batch row for the tick calculation:

```text
fixed_leg       = -10540
floating_leg_set = 2740
live_exposure   = [30, 80, 0]
market_axis     = [D3 projection, D4 projection, D5 projection]
```

The source trade batch retains the original terms and payment identities. The expanded
table is a mathematical reference; constructing or storing a dense per-trade matrix is
not required to obtain the aggregate. Opposite coefficients on D5 cancel for this batch
under this preparation. Keeping or omitting its explicit zero column is a storage choice;
its zero aggregate sensitivity and original source observations must remain unambiguous.

## Evaluate the aggregate directly

First verify that the supplied market has compatible history, source, units and live layout.
Then obtain prices in the prepared vector's order, using its retained mapping:

| Identified live input | Current price |
|---|---:|
| D3 remaining-assessment projection | 72 |
| D4 remaining-assessment projection | 74 |
| D5 remaining-assessment projection | 76 |

```text
floating_leg_live = live_exposure @ live_prices
                  = 30*72 + 80*74 + 0*76
                  = 8080

amount = fixed_leg + floating_leg_set + floating_leg_live
       = -10540 + 2740 + 8080
       = 280

amount_delta = [30, 80, 0]
```

That is the requested batch result. No per-trade live values need to be calculated on this
path. As an independent acceptance check, separate singleton evaluations produce
[180, -40, 60, 60, 20], whose sum is 280. Their exposure vectors sum to [30, 80, 0].

Fixing or as-of changes rebuild the preparation from the original encoding and complete
new history. A price tick reuses the retained sums and vector, avoiding both a history fold
and another aggregation of trade exposures.

## Contract columns, daily observations and aggregation

Columns identify live market inputs. When several observations project onto one contract
input, their coefficients can be added into that column. Different contracts or distinct
daily projections keep separate positions, even if their current prices happen to match.
Same index or month alone does not justify replacing different inputs by one.

Across trades, coefficients on a shared input can be summed regardless of whether the
trades have identical schedules or proportional exposure patterns. Different schedules
change the coefficients and input identities; they do not prevent compatible amount addition.

A whole-month average quote is not automatically a remaining-assessment projection. Any
conversion requires its own explicit rule and risk mapping. The [two-observation example](worked-example.md)
shows the numerical difference. Aggregation must not conceal a wrong coordinate choice.

## The earlier two-trade example

For two fully live fixed/float trades on the equal-weight average of P and Q:

| Contribution | Signed quantity | Agreed price | fixed_leg | P exposure | Q exposure |
|---|---:|---:|---:|---:|---:|
| A | 100 | 70 | -7,000 | 50 | 50 |
| B | -40 | 72 | 2,880 | -20 | -20 |
| **Batch** | | | **-4,120** | **30** | **30** |

At P = 74 and Q = 76, with no set observations:

```text
amount = -4120 + 0 + [30,30] @ [74,76] = 380
```

The batch-equals-summed-singletons check is 500 + (-120) = 380. Returning both individual
amounts from the batch evaluation is no longer a requirement. The earlier alternative of
evaluating normalized patterns and reconstructing individual amounts remains useful only
if a future feature specifically requests those individual outputs. It is unnecessary
machinery for the selected aggregate result.

Net-zero live exposure does not imply zero amount. A +100 trade at 70 and a -100 trade at 72
on the same average have zero net live exposure but fixed-leg total 200. Retain aggregate
fixed and set amounts even when the live vector is zero. No division by net quantity or by
the sum of signed coefficients is needed anywhere in this aggregation.

## Payment dates and later valuation

This first result is an undiscounted compatible amount in one currency. It is not an NPV.
Retain each original payment's date, currency and treatment in the source trade facts.

When rates are introduced, prepare amounts/exposures in groups sharing the relevant payment
valuation treatment, apply that treatment, then sum to the requested batch result. Do not
apply one discount factor to an aggregate containing different payment dates. The current
single amount/vector does not itself contain enough payment detail for that extension; the
source facts remain available to build it. This does not require individual trade tick
outputs now.

For example, suppose two payments on the same price input have opposing quantities and the
same agreed price. At a current price of 75 and agreed price of 70:

| Payment group | Signed quantity | Amount | Illustrative discount factor | Present value |
|---|---:|---:|---:|---:|
| January payment | +100 | 500 | 0.99 | 495 |
| February payment | -100 | -500 | 0.98 | -490 |
| Batch | 0 | 0 | Not one common factor | 5 |

The raw aggregate exposure and fixed amount are both zero, yet NPV is 5. Under the explicit
assumption that those factors are independent of commodity prices, NPV delta is
100 x 0.99 - 100 x 0.98 = 1. These are hand checks of the grouping boundary, not a complete
rate model or a cash definition. The full target is **two route-specific value fields plus
shared delta and DV01**; see [proposed fields](result-fields-by-route.md). Keep the groups
needed by those measures, without requiring evaluated objects per trade.

The [performance note](aggregation-performance.md) measures the simpler amount-only case.
The number of compatible payment/rate groups, not just trade count, will govern how much
that compression carries through to the full result.

## Acceptance targets

- Under one compatible context, aggregate evaluation equals the sum of separate singleton
  evaluations within documented tolerances, for both amounts and aligned market risks.
- Duplicated occurrences contribute twice; they are never removed as duplicate bookings.
- Opposite live exposures cancel while their fixed/set amounts continue to contribute.
- Dense explanatory rows and direct aggregate preparation agree with independent payoff
  answers for different schedules, partial fixings and the zero-net example.
- A live tick performs no schedule building, fixing folding or re-summing across trades.
- A fixing correction/date roll rebuilds preparation from the full history and original
  observation weights, including observations whose aggregate live coefficient had cancelled.
- Equal current prices at different coordinates do not merge those coordinates.
- Incompatible history/layout or amount currencies/meanings fail explicitly.
- Readers consume the aggregate snapshot; an individual/subset value requires an evaluation
  of that collection, not lazy pricing or allocation from the aggregate.
