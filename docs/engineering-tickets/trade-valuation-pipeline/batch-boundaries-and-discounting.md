# Batch boundaries and discounting before final compression

[Pipeline overview](README.md) · [Creation](create-trade.md) · [Preparation](03-market-binding.md) · [Evaluation](04-evaluation.md)

**Status:** Whiteboard refinement, 3 October 2026. One template, required, serves the rows
passed to `_CreateTrades(index, fields, trade_rows, template)`, and one index per batch is a
fact of that call, since the index is its argument. No pricing code changes here.

## One template, then validate the resolved collection

A template supplies the shared instrument context and defaults for an array of ticket rows.
Cleared versus bilateral is a useful initial batch boundary. The first proposed scope is:

| Property | First-scope recommendation |
|---|---|
| Template | One template, required, for the call's rows |
| Index | One, the call's argument, for the whole batch |
| Route | Uniform cleared or bilateral route |
| Currency | One amount/result currency; no implicit FX conversion |
| Contracts, quantities, agreed prices | May vary by ticket |
| Supported observation schedules | May vary within the selected schema and conventions |
| Payment dates and applicable curve associations | Preserve and group as needed; need not all be identical |

Template fields and ticket columns must be disjoint; repeating a field fails even when
the values match. A shared template establishes common values for the fields it supplies,
but ticket-only fields can vary. Validate the completed batch after resolving its rows.
An unsupported mixture fails visibly rather than being silently split or priced under one
row's rules. The uniform no-duplication rule and the batch compatibility check need no
per-field template lock or revival of template_allowed.

Template identity is not itself the economic grouping key. Two differently named templates
can produce compatible trades; the eventual aggregation rules depend on resolved facts.
Route also does not fully determine settlement or valuation treatment. Retain the actual
product/agreement convention rather than interpreting cleared as a universal no-rates rule.

## Why begin with one index?

It keeps one history and one price-vector association visible while the first pipeline is
built. The current Market has one MarketHistory, one PriceVector and a first-contract offset;
it is not a general multi-index/rates container. Current labels alone do not prove identity.

The numerical design does not need one index forever. A later call could take an explicit
market collection and supply a concatenated axis such as:

```text
[(NG reference, Z26, own-contract mark),
 (NG reference, F27, own-contract mark),
 (CL reference, Z26, own-contract mark)]
```

Each column carries its actual reference, contract/observation identity, role and units.
NG Z26 and CL Z26 never merge just because their month codes match. Multiple indexes require
explicit histories, market mappings, coherent as-of context and risk axes, not different
linear arithmetic. Add that surface deliberately when needed; do not make every first
worksheet formula manage a collection of markets. Cash-only instruments remain index-neutral.

## Resolve the curve association; supply current rates later

| Stage | Responsibility |
|---|---|
| CreateTrades: resolution/encoding | Resolve contractual payment dates and the applicable discount/settlement convention or curve association; encode static coefficients and fixed legs |
| PrepareTrades(trades, history) | Apply fixings; retain set amounts and remaining live exposure within compatible payment groups |
| EvaluateTrades | Bind explicit current rate inputs to those associations, obtain payment factors, complete value/cash/risk and return aggregate results |

A toy role such as USD_discount identifies which supplied curve the valuation should use;
it is not the current DiscountCurve object or its factor values. Currency alone need not
determine the curve when agreement/settlement terms differ. Role names and public field names
remain to be specified. The current curve snapshot comes from explicit valuation inputs,
not an ambient lookup or inference from the commodity index.

Trade creation stays market-value-independent. A rate update must not amend executed terms
or rebuild static schedules. Keep the currently proposed PrepareTrades signature independent
of rates. The future EvaluateTrades contract needs a rate/valuation context, supplied either
explicitly or through a deliberately expanded market context; the existing Market does not
already supply it. Final worksheet argument packaging is still open.

## Compress within payment groups, then discount and combine

For the bilateral payment path, retain groups sharing relevant payment date, currency, curve
association and valuation/settlement treatment. The proposed initial rule derives modeled
settlement from `payment_date <= as_of`: only remaining groups enter the discounting below.
Settled groups contribute their full signed amount to cumulative modeled cash. See the
[result-field proposal](result-fields-by-route.md). An actual-payment status dependency is
outside this first model; unrelated booking labels do not require extra groups.
This produces group rows, not one evaluated object per trade.

```text
fixed_leg[G]
floating_leg_set[G]
live_exposure[G, M]
payment_dates[G]
curve_associations[G]
valuation_treatment[G]
```

G counts compatible payment groups; M counts identified live market inputs. The one-vector
amount specimen was valid for its undiscounted output. It is not sufficient retained state
for valuing payments under different discount factors.

Use two toy payments on the same live input, with agreed price 70 and current price 75:

| Payment group | fixed_leg | floating_leg_set | Live coefficient | Discount factor |
|---|---:|---:|---:|---:|
| January | -7,000 | 0 | +100 | 0.99 |
| February | +7,000 | 0 | -100 | 0.98 |

One route computes group amounts [500, -500], values them [495, -490], then returns NPV 5.
Equivalently, multiply each group's fixed/set contributions and exposure by its discount
factor before the final compression:

| Payment group | Discounted fixed leg | Discounted set amount | Discounted live coefficient |
|---|---:|---:|---:|
| January | -6,930 | 0 | +99 |
| February | +6,860 | 0 | -98 |
| **Compressed for NPV** | **-70** | **0** | **+1** |

```text
npv = -70 + 0 + 1 * 75 = 5
npv_delta = [1]
```

Discount all contributions, including fixed and set, not just live exposure. In matrix form:

```python
group_amounts = fixed_leg + floating_leg_set + live_exposure @ prices
npv = discount_factors @ group_amounts

# Equivalent compression for this current rate snapshot:
pv_fixed_leg = discount_factors @ fixed_leg
pv_floating_leg_set = discount_factors @ floating_leg_set
pv_exposure = discount_factors @ live_exposure
npv = pv_fixed_leg + pv_floating_leg_set + pv_exposure @ prices
npv_delta = pv_exposure
```

These equations assume the supplied discount factors do not depend on the commodity prices
being differentiated, and the prepared projection is linear on the stated market axis.
Any additional dependence requires the corresponding risk mapping.

## Keep the groups behind the NPV compression

The discounted vector is a derived representation for a particular rate/as-of context.
Keep the underlying group structure for rate changes, cash treatment and DV01. One compressed
NPV vector is not a universal replacement for those inputs or the raw undiscounted amounts.

Under an explicitly specified bump that changes only discount factors, the change in NPV is:

```text
rate_scenario_change = (bumped_discount_factors - discount_factors) @ group_amounts
```

This becomes a DV01 measure only after defining the one-basis-point curve bump, buckets,
sign and held-fixed inputs. If the rate scenario also changes projected commodity inputs,
that change belongs in the scenario too. Existing DiscountCurve supplies factors; it does
not by itself define those bump conventions. Cash still needs its separately agreed meaning.

For the simplest implementation, evaluation applies current factors to the prepared groups
on each call and produces the required aggregates. Reusing a discounted vector across price
ticks can come later, with explicit curve/as-of dependency tracking. It must not silently
attach rate-dependent state to a preparation handle whose only inputs are trades and history.

Acceptance: group-first and discounted-exposure calculations agree with hand answers; the
example retains NPV 5/delta 1 despite zero net undiscounted exposure; rate changes update NPV
without recreating trades or reapplying unchanged fixings; every requested full-result field
is completed before publication. No per-trade valuation storage is required.
