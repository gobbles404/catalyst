# CreateTrades: resolution, encoding and retained state

[Pipeline overview](README.md) · [Resolution](01-trade-representation.md) ·
[Encoding](02-static-encoding.md) · [Next: market binding](03-market-binding.md)

Agreed responsibility boundary, 3 October 2026. This is a design contract, not an implementation.

## The public wrapper and its two children

**CreateTrades wraps resolution followed by static encoding.** It returns one handle to the
resulting immutable trade batch. One trade uses the same batch path as many trades.

The agreed worksheet name is `_CreateTrades`, matching `_PrepareTrades` and `_EvaluateTrades`.
The plural makes the one-or-many batch contract explicit. The final creation argument list
remains open; there is no separate singular function or compatibility alias.

The user envisages one supplied template for the call's array of trade rows. The recommended
first commodity scope is one actual index, route and amount currency per batch; index scope
is still a proposal rather than a permanent restriction. Ticket overrides remain possible,
so resolution must validate the completed batch rather than infer compatibility from its
template handle. See [batch boundaries and discounting](batch-boundaries-and-discounting.md).

Illustrative private orchestration, after the seam has supplied typed input:

```python
def create_trades(instrument_context, ticket_rows, template, static_definitions, counter):
    resolved = _resolve_trades(
        instrument_context, ticket_rows, template, static_definitions, counter
    )
    encoded = _encode_trades(resolved, counter)
    return TradeBatch(resolved=resolved, encoded=encoded)
```

The parameter groups are logical, not the final Excel signature. A template can supply the
instrument context and static references; a no-template path must establish those explicitly.
Static unit definitions used by encoding must be retained/supplied explicitly through the
resolved inputs; the encoder cannot discover them through an ambient global lookup.

| Child | Owns | Produces |
|---|---|---|
| Resolution | Merge defaults and ticket values; establish actual instrument/product/reference identity, selected contracts and conventions; validate the completed terms and compatibility | Resolved trade facts and the static definitions that give them meaning |
| Encoding | Consume those resolved facts; expand applicable observation schedules, compute static conversions/weights and contributions, assign numerical positions and attribution | Read-only numerical arrays and identified market inputs |

Resolution decides which contract and contractual rule apply. Encoding materializes that
rule into static arrays; it does not re-merge templates, reinterpret contract codes or repeat
completed-trade compatibility checks. These are separate internal responsibilities even
though one public call coordinates them. No partly resolved or partly encoded trade handle
is published if either child fails.

## What the handle retains

The minimum useful state is:

```text
TradeBatch
    resolved
        occurrence identities and trade labels
        executed terms and agreed price/units
        actual instrument, product, index and specification references
        applicable static conventions and unit definitions
        contractual payment/settlement terms and retained attribution
    encoded
        market_inputs                  # identities/descriptors, no supplied market values
        static numerical contributions # quantities, weights, coefficients, fixed amounts
        component/leg/payment mappings
        links from contributions to market inputs and trade occurrences
```

| Retained content | Purpose |
|---|---|
| Resolved terms | Explain which deal is represented, including agreed price, quantity/unit, contract and supported booking fields |
| Definition identities/references | Preserve the meaning of those terms without copying specifications into every row |
| Ordered occurrence identities | Keep duplicate input rows distinct, independently of user-supplied trade labels |
| Static NumPy arrays | Supply signed/scaled contributions, including `fixed_leg` for fixed/float trades and known amounts for applicable cash records |
| Market input descriptors | Identify the market data the trade consumes: reference/index, input kind, contract/date and expected units |
| Ownership/mappings | Tie terms and inputs back to the correct occurrence, component, actual leg and payment |

A future retains its agreed entry-price reference and applicable treatment; its entry-price
P&L arithmetic does not make it a fixed/float swap or turn that reference into an actual
cash payment. Keep product-appropriate names rather than calling every fixed arithmetic
term `fixed_leg`.

Resolved facts remain inspectable alongside the encoding. Keep one canonical copy of a
fact; the two logical sections can share immutable arrays or references. The payload above
does not require duplicating payment metadata, retaining every raw Excel cell, or keeping
both dense and compact copies of the same matrix. Temporary merge structures can be released.
Retaining field-source provenance is a separate optional inspection choice, not needed to
make numerical evaluation correct.

Once defaults have resolved, retaining the entire template or raw ticket graph is not required
for the trade's meaning. Retain the actual definition/reference dependencies used by the
resolved object. Binding and results can retain this immutable batch or its relevant shared
parts without copying all its arrays.

## Market inputs: identity first, data later

Use **market inputs**, not market requirements, for the data-facing part of the design.
At creation, `encoded.market_inputs` describes those inputs; it does not hold their prices.
At binding/evaluation, the market supplies the associated data values. Conventions and
specifications remain static definition inputs, named separately.

Examples of market input descriptors:

| Kind | Identity |
|---|---|
| Own contract mark | The particular product/reference and contract, with the expected quote units |
| Index assessment | The reference index, assessment kind and observation date |
| Multiple observations | Each identified observation, with static coefficients linking it to components |

An averaging contract with its own traded mark can retain that market identity; an explicitly
observation-based payoff retains the relevant observation identities. The descriptor is not
permission to interchange the two or choose a new projection rule implicitly. Binding
establishes the actual history/live mapping under an explicit supported projection rule.

Integer positions inside an encoding identify its own static input list. They are not
positions in today's shortened price vector. A cash record can have zero commodity inputs.
Its currency and dated payment facts remain available for later valuation inputs when supported.

For bilateral payment valuation, resolve payment dates and the applicable discount convention
or curve association as static facts. This names which rate input applies; it does not freeze
a current curve snapshot or discount factor into the trade. Current rate values are supplied
to evaluation under an explicit valuation context. A rate update leaves creation unchanged.

## State that belongs after creation

Do not attach mutable market preparation or an evaluation cache to the static trade record.
The created batch contains no market-history snapshot, valuation as-of, published fixing
values, is-fixed flags, live-vector positions, current market prices, `floating_leg_set`,
`floating_leg_live`, discount factors or evaluated results. An executed trade date, payment
date, agreed trade price and `fixed_leg` remain legitimate static trade data.

`_PrepareTrades(trades, history)` owns the history-dependent mapping and prepared set
contribution under an explicit prepared handle. `_EvaluateTrades(prepared, market)` consumes
that preparation plus compatible current inputs and produces a results handle. Receiving
history inside the public trade constructor was an earlier candidate; it is outside this
agreed static wrapper. The first implementation does not need a private preparation cache.

## Worked state and acceptance

For the [two-trade average fixture](worked-example.md), the retained resolved terms include
quantities `[100, -40]`, agreed prices `[70, 72]`, the shared two-assessment definition and
the two different payment dates. Encoding adds:

```text
market_inputs      = [TOY assessment 15-Dec, TOY assessment 16-Dec]
fixed_leg          = [-7000, 2880]
term_component     = [0, 0, 1, 1]
term_input         = [0, 1, 0, 1]
term_coefficient   = [50, 50, -20, -20]
component_to_trade = [0, 1]
```

The first fixing of 68 and the live projection of 74 arrive later. Neither value, nor the
derived set/live split, is stored by CreateTrades.

- Creation runs resolution and encoding on one path for one or N trades, preserving occurrences.
- Reusing the created object for a price tick, fixing correction or date roll performs neither
  child again. Subsequent binding responds to the applicable market-state changes.
- A ticket/default/static-definition change creates a new resolved and encoded batch.
- Inspecting the created batch explains its terms, market input identities and static arrays
  without reading a market or performing evaluation.
- Work counters distinguish resolution/encoding work from binding/evaluation work; immutable
  ownership and failure handling are verified through the real handle lifecycle.
