# 2. Static trade encoding

[Pipeline overview](README.md) · [Previous](01-trade-representation.md) · [Next: binding](03-market-binding.md)

## Responsibility

Encoding is the second private child of [CreateTrades](create-trade.md), after resolution.
Consume resolved trade terms to produce static numerical contributions and identified market
inputs. Materialize the selected observation rules into schedules, compute signed/scaled
weights and amounts, and construct component mappings before emitting read-only typed arrays.

The encoder does not repeat resolution: it does not merge template values, choose a different
product, reinterpret contract codes or recheck already established compatibility. Its output
is an immutable derived record. CreateTrades retains that record alongside the resolved terms
under one handle; no history-dependent preparation is attached at this stage.

## Inputs and output

Inputs are records resolved under approved instrument schemas and every static definition
they use. Dispatch selects a library-supported encoder; a template does not supply numerical
formulas or custom execution rules. Unit conversion must be
an explicit dependency, whether supplied through a resolved definition or separately.
The current index's creation-time validation does not mean it retains all conversion data.

An encoding retains:

- Static signed contribution terms, indexed by component and observation, and the fixed
  leg for fixed/float trades.
- Market input descriptors: source/index definition, input kind, relevant contract/date,
  expected units and any further distinction needed to identify the data. An assessment is
  one such input; a contract's own market price is another. Descriptors contain no values.
- Occurrence/component attribution, actual leg identities where applicable, units, currency,
  payment ownership/dates and valuation-treatment metadata.

Known cash instruments can have no commodity observations at all. Preserve their signed
amount, currency and payment/balance context rather than inventing a zero-price contract.

Resolved definitions, payment metadata and array columns can be shared by reference where
immutable. Logical separation does not require a second copy of every retained fact; see
[CreateTrades's state contract](create-trade.md) for the combined object's ownership.

There are no current prices, published fixing values, as-of-dependent fixed flags or live
market-vector offsets. A contract's position in a static schedule is not necessarily its
position in today's shortened live price vector.

## Worked payload

For the [shared fixture](worked-example.md):

```python
market_inputs = [
    (toy_index, "assessment", "2026-12-15"),
    (toy_index, "assessment", "2026-12-16"),
]
fixed_leg = [-7000, 2880]
term_component = [0, 0, 1, 1]
term_input = [0, 1, 0, 1]
term_coefficient = [50, 50, -20, -20]
payment_dates = ["2027-01-05", "2027-02-05"]
```

The dense reference representation is:

```text
                    observation 0   observation 1
component T1               50              50
component T2              -20             -20
```

Each coefficient is USD of component amount per USD/unit of observation price. The two
trades share observations but retain separate components and payment dates. Compact term
columns and dense matrices can represent the same contract; this document does not select
the production storage layout.

In this fixture the market inputs are assessments, so the dense table labels them as
observations. `term_input` indexes that static list; it does not address a live price vector.

## Dependencies and acceptance

Encoding changes when the trade or its used static definitions change. It does not change
on a fixing correction or valuation-date roll. Expand the agreed averaging schedule before grouping
by contract; do not replace daily economic weights with an unexplained day-count shortcut.

Require independently checked units and coefficients, one/N consistency, duplicate preservation,
and correct component/payment attribution. Opposite quantities at different agreed prices
can have zero market exposure and nonzero combined amount; retain both fixed legs.

PR119's `Terms` is a candidate numerical core here. It carries positional observation numbers,
not these economic identities. Keep, adapt or replace it according to this boundary rather
than making its present fields the trade schema.
