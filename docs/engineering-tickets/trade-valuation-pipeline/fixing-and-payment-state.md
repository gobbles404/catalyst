# When a price fixes and when a payment settles

[Pipeline overview](README.md) · [Preparation](03-market-binding.md) · [Results](05-results.md)

**Status:** Research and lifecycle whiteboard, updated 3 October 2026. The first model now
explicitly excludes margining and actual-payment reconciliation. It proposes assumed payment
on the encoded date; the earlier actual-payment discussion below is background, not a build
prerequisite. See [proposed result fields by route](result-fields-by-route.md).
The exchange example uses ICE's Henry Penultimate Fixed Price Future (PHH). Numerical cash
examples are fictional bilateral payments, not historical prices or a claim that a cleared
future makes one entry-to-final-price cash transfer at expiry.

## What the ICE contract establishes

PHH is a monthly cash-settled future. Its final reference is the corresponding NYMEX Henry
Hub contract's settlement on the business day preceding NYMEX's scheduled last trading day.
ICE trading ends four business days before the contract month starts; final payment falls
on the next clearing business day after that trading cutoff.
[ICE product specification](https://www.ice.com/products/6590264).

For this discussion Cal26 means the January-December strip of monthly contracts, not one
annual-average instrument. Each constituent retains its monthly price determination and
settlement rules. ICE's general calendar-strip explanation describes a year as its monthly
constituents; that guide is for ICE Futures Europe, not a substitute for a PHH execution's
actual package definition or allocations.
[ICE strip guide, section 3.6](https://www.ice.com/publicdocs/IFEU_Common_Strategies_and_Strips.pdf).

Under PHH's rule, the March price becomes final before March starts. The contract month is
not the payment month. No exact historical 2026 day is asserted here; date generation must
use the applicable exchange and clearing calendars. In particular, an expiry field labelled
final settlement is not automatically the cash payment date.

For background, ICE Clear Europe also marks open positions daily and settles variation P&L
in cash overnight. Those flows are outside our initial model; monthly final settlement does
not describe the actual frequency of cash movements.
[ICE Clear Europe risk management](https://www.ice.com/clear-europe/risk-management).

A bilateral Cal26 swap may adopt the same monthly price references, but its own agreement
establishes payment timing and any collateral/cash mechanics. Do not inherit every clearing
cash rule merely because the swap references PHH or the same NYMEX prices.

## Two independent questions

| Question | Example states | Evidence |
|---|---|---|
| How much of the floating price is known? | Unfixed, partially fixed, fully fixed | Observation schedule, publication cutoff, fixing history |
| Which components remain in modeled value? | Before payment date, on/after payment date | Encoded payment dates, valuation as-of and explicit assumed-settlement convention |

Use `floating_leg_set` for the amount contributed by known observations. It is not synonymous
with cash paid. A fixing says which price applies; a payment event says which obligation
has been discharged. There is no need to invent two different kinds of set floating price
to distinguish a paid month from an unpaid month. For this first model, the payment event
is assumed from the scheduled date; it is not supplied by a bank ledger.

For the monthly PHH strip, imagine a snapshot after March's final price is established but
before its final payment, assuming earlier months' payment dates have passed:

| Constituent | Final price known? | Modeled final settlement reached? |
|---|---|---|
| January, February | Yes | Yes, by the example's dates and convention |
| March | Yes | No, final payment outstanding |
| April-December | No | No, still live monthly positions |

This table concerns modeled finalization. A whole-trade flag such as Cal26_is_settled cannot
represent these constituent states adequately. Actual daily margin cash remains out of scope.

An Asian observation window can also be partially fixed while its one monthly payment is
unpaid. That intermediate price state does not apply to PHH's single final fixing in the
same way; preserve the actual product's observation rule.

## A bilateral March payment, with simple numbers

Assume a fictional bilateral monthly payment receives floating and pays 3.00 USD/MMBtu on
2,500 MMBtu. The applicable monthly reference eventually fixes at 3.20. Assume no earlier
payment or collateral transfer and no fees. These choices explain the states; they are not
PHH's daily variation-margin cash mechanics.

```text
fixed_leg = -2500 * 3.00 = -7500
floating_leg_set = 2500 * 3.20 = 8000
floating_leg_live = 0
known net payment = 500
```

| March state | Bilateral NPV | Modeled bilateral cash |
|---|---:|---:|
| Fixed, before payment date; discount factor 0.99 | 495 | 0 |
| Fixed, on/after payment date | 0 | 500 |

The original fixing stays 3.20 in every row. Floating commodity delta is zero once this
particular price has fixed. Before payment the claim may still have rate sensitivity.
The full net amount of 500 becomes cash, not the prior discounted NPV of 495. Remove both
fixed and floating contributions from remaining value together. The proposed cumulative
cash field is a signed historical payment total, not a reinvested cash-account balance.

Keeping the Cal26 trade's terms does not keep all twelve monthly obligations outstanding.
Past components remain available as source facts, while evaluation
values the remaining obligations and reports cash under its separately defined scope.

## Background: actual cleared cash would need different inputs

For a cleared PHH position, entry-to-final-price P&L can have been paid in multiple variation
margin transfers. Do not compute quantity times final-minus-entry price and book that whole
amount again as the final payment. A current daily settlement quote is also not necessarily
the contract's final fixing. Current price, final observation and paid cash are different inputs.

Cash for the March contract and cash paid during March are different selections. The latter
uses actual cash dates and may include variation margin on several later-dated contracts.
We are not building that feature here. The proposed cleared result instead returns
`cleared_mark` and `cleared_cash`, with shared `delta` and `dv01` names.
Its cash field means modeled finalized P&L. Bilateral `bilateral_cash` is proposed as all
modeled settled payments in the supplied collection through as-of.

## Consequences for the pipeline

| Boundary | Responsibility |
|---|---|
| CreateTrades | Retain contractual observation and payment rules/dates for monthly constituents; executed terms remain static |
| PrepareTrades(trades, history) | Fold fixings, derive modeled settlement from dates/as-of, and retain contributions by relevant payment group |
| Evaluation with explicit valuation context | Discount remaining bilateral payments, report settled amounts without discounting, and complete route-specific values and shared risks |
| Readers | Display the completed result's selected cash scope and remaining value; no settlement inference or lazy pricing |

The proposed cutoff is `payment_date <= as_of`. Encoded dates plus history's as-of supply
everything needed for this assumed-settlement mask, so the initial preparation needs no
extra settlement store. An as-of change already rebuilds preparation. The model requires
final fixings for settled components and fails if they are missing.

Reaching a date does not prove an actual transfer; that distinction is captured by the
explicit modeling convention. If actual-payment reporting is added later, settlement records
could change independently and must become an explicit dependency. Partial payment of 200
against a 500 obligation would then leave 300 outstanding. That future reconciliation mode,
along with margining, is outside the first implementation.

Acceptance: fixing changes set/live exposure without itself declaring a payment; a date roll
moves the full net payment from remaining value into the settled bucket without changing its
fixing; monthly components can occupy different states; no component is counted twice. Test
before/on/after-date cutoffs and required missing fixings under one explicit as-of convention.
