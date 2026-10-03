# 5. Evaluation results

[Pipeline overview](README.md) · [Previous](04-evaluation.md) · [Next: readers](06-readers.md)

## Responsibility

Publish one immutable snapshot of the requested batch's supported aggregate measures and
risks, computed from a coherent set of inputs. A result identifies the supplied collection;
it is not a promise to calculate individual trade values when someone asks to read it.

The target has **mark and cash for the batch's route, plus delta and dv01**. The accepted
outward labels are `bilateral_mark`/`bilateral_cash` and `cleared_mark`/`cleared_cash`.
Evaluation completes all four applicable fields before publishing the result handle,
or fails visibly. It does not populate the other route's fields with meaningless zeros.
Readers do not finish valuation or risk calculations later. Final public casing and reader
names remain open. See [result fields by route](result-fields-by-route.md).

Values and risks are two result families in the same evaluation context. They can share
immutable arrays safely; they do not need separate trade traversal or independent market gathering.
`_EvaluateTrades` returns one results handle for the batch as a whole. A batch of one has the
same result structure as many trades: one aggregate value per requested measure and a risk
vector over each measure's identified coordinates. It does not require per-trade result arrays.

## Values by route and shared risks

| Route | Remaining-value field | Modeled settled-amount field |
|---|---|---|
| Bilateral | `bilateral_mark`: present value of payments not yet modeled as settled, in the identified currency and valuation context | `bilateral_cash`: cumulative full signed net payments modeled as settled, without discounting those settled amounts |
| Cleared, with margining excluded | `cleared_mark`: entry-to-current-price P&L before final fixing, or entry-to-final-price P&L while awaiting the modeled final settlement date | `cleared_cash`: cumulative entry-to-final-price P&L for components included by the modeled final settlement-date cutoff |

The cleared fields are undiscounted economic P&L buckets. They do not claim to be current
asset NPV or actual variation-margin cash transfers. Margining, collateral and actual bank
reconciliation are outside this initial scope. Their absence does not block the date-driven
model; a future actual-cash/reconciliation feature would need its own settlement records.

Both routes use `delta` and `dv01`. Their differentiated remaining-value measure is
`bilateral_mark` or `cleared_mark`, explicitly identified in metadata. Mark is a monetary
amount, not a quoted commodity price.
Delta carries the commodity axis, units and projection/risk mapping. DV01 carries the
curve/bucket axis, one-basis-point bump, sign convention and held-fixed inputs; the detailed
bump/sign convention still needs agreement. The shared names do not make bilateral NPV and
cleared P&L interchangeable measures.

For the explicitly undiscounted cleared model, holding commodity inputs fixed gives zero
rate sensitivity. That is a valid model result. An unimplemented bilateral DV01 calculation
is not zero. Fixed and set-but-unpaid bilateral amounts may retain rate sensitivity even
when their live commodity exposure is zero.

## Proposed date-driven settlement rule

The proposed initial cutoff is `payment_date <= valuation_asof`. Encoded contractual dates
and the explicit as-of then determine modeled settlement; no bank confirmation is required.
For cleared components use their modeled final settlement/payment date, not merely the
contract month or the date their final price becomes known.

At the cutoff, move the **full signed net payment** into the bilateral cash bucket and
remove the whole obligation from remaining NPV. Do not transfer yesterday's discounted NPV
or remove only the floating part while leaving a fixed-leg obligation. Settled amounts
remain undiscounted. The proposed cumulative scope includes all settled components in the
supplied batch through as-of; a date-interval reporting view is a separate future decision.

Required final fixings must be known before a component enters a settled bucket. A missing
required fixing fails visibly; a forecast must not silently become settled cash or settled
P&L. Track this at each relevant monthly/payment component of a Cal trade, while keeping
the original executed terms static. `floating_leg_set` still means known observations,
not settled cash: price fixing and modeled settlement remain separate facts.

This is an explicit assumed-settlement convention, not evidence that money actually moved.
The wider distinctions and excluded actual-payment lifecycle are described in
[fixing and payment state](fixing-and-payment-state.md).

The intermediate amount prototype uses one currency and one compatible undiscounted amount
measure. It proves a portion of the pipeline, not completion of the four-field target.
The initial result contract includes all four outputs; no optional-measure framework is
introduced here. Unimplemented measures must not be replaced with zeros. A numerical zero is valid only when the supported
measure and supplied inputs establish it.

## Minimum semantic contents

| Group | Required meaning |
|---|---|
| Requested collection | Reference to the supplied batch, including its original occurrences and display labels |
| Measures | The route's two completed value fields plus `delta` and `dv01`, with their meanings and units; intermediate amount results remain explicitly identified |
| Conventions | Route, currency, as-of, remaining-value basis, date cutoff and cumulative modeled-settlement scope |
| Optional diagnostics | Aggregate `fixed_leg`, `floating_leg_set`, `floating_leg_live` when meaningful; these are not extra required fields in the four-output target |
| Risk | Aggregate sensitivity vector, measure differentiated, ordered market/curve coordinates, units and bump convention where applicable |
| Provenance | The resolved trade/definition inputs and valuation/market context used; sufficient immutable references or metadata to prevent mixed snapshots |
| Completeness | The declared result scope and every measure it requires; no partial publication of the four-field target |

Source trade facts, payment dates and units remain available through retained immutable
references. They describe which contributions were included; they do not imply that individual
trade amounts were evaluated or stored. Duplicate occurrences contribute in full, even when
their labels or economics are identical. Preserve enough provenance for interpretation without
deep-copying every raw market array into every result. Runtime object identity supports reuse;
it is not a durable provenance identifier or a serialized golden field.

## Proposed in-memory storage

One immutable `EvaluationResult` can contain valuation and risk sections with shared context:

```text
EvaluationResult
    context
        route, currency, valuation_asof, value_basis
        date_cutoff, cumulative_scope, modeled_settlement_convention
        commodity_axis, rate_axis, delta_definition, dv01_definition
        immutable valuation-input references
    valuation
        mark                     # aggregate currency amount
        cash                     # aggregate modeled settled amount
    risk
        delta: float64[M]
        dv01: float64[R]
    source_batch                 # shared immutable occurrence and payment facts
```

M counts commodity risk coordinates and R rate-risk coordinates, not input trades. R is one
when the agreed DV01 convention is a single scalar; the bump, sign and bucket convention
still needs agreement. A batch of one and a larger batch use this same record shape.

A uniform-route record needs only internal `mark` and `cash` values. Its route and value
basis determine the outward labels; there is no second copy under each label, no irrelevant
route-zero fields, and no need for parallel route-specific result subclasses. Separate
valuation and risk sections clarify their meanings without creating independent calculations.
The [evaluation boundary](04-evaluation.md) coordinates private helpers that share prepared
exposures, current factors and group amounts before publishing one completed result.

Share immutable axes, source and context references rather than copying the entire market
or trade batch into every result. Temporary group amounts and calculation workspaces need
not persist after evaluation. Retain only the provenance and data needed to interpret the
completed snapshot; no evaluated amount per trade is required.

Published NumPy arrays must be owned and read-only, or safely share already immutable
backing with no writable aliases. A frozen dataclass or a read-only view alone does not
establish that guarantee. Reusing an immutable prepared delta array is valid when its
meaning matches the result; later ticks must never mutate it. Handle ownership must retain
the required references while readers remain live and release obsolete results and their
dependencies when no owner remains, without an unbounded global result store.

## Intermediate amount example

For the [fixture](worked-example.md), the intermediate amount-only content is:

```python
result.trades = supplied_trade_batch  # retains T1, T2 and their payment facts
result.currency = "USD"
result.fixed_leg = -4120
result.floating_leg_set = 2040
result.floating_leg_live = 2220
result.projected_unpaid_amount = 140
result.amount_delta = [30]
result.mark_axis = [(toy_index, "Z26", "remaining_assessments", "USD/unit")]
```

The scalar notation describes one batch value. A one-row numerical representation is also
possible; the result shape does not gain one row for every input trade. The aggregate value
is `-4120 + 2040 + 30 * 74 = 140`. Individual values require separately evaluating the desired
one-trade or subset batch. How the surface selects such a batch remains to be specified.

For a future payment-valuation extension, the fixture's aggregate NPV is `138.2` and NPV
delta is `[29.9]`. Evaluation must apply the respective payment treatments before aggregation,
using the retained payment-group structure. Applying one discount factor to the already
netted amount `140` is not equivalent. This extension can still return only the batch total;
it need not publish individual payment values. Those two illustrative numbers establish
neither a tested settlement lifecycle nor DV01, so the amount prototype is not a complete
implementation of the route's four-field result.

## Lifetime and acceptance

A later tick creates a new result; it cannot mutate a retained result read elsewhere. Value
and risk readers of one result must refer to the same snapshot, even if a current market cell
has moved on. Retained source facts continue to identify every contributing occurrence.

For the first implementation, favor a complete validated batch or a visible failure over
silently partial numbers. Any later per-row error behavior needs an explicit contract.
For the full target, all four measures must be valid and complete before publication.
Failure to calculate one required field must not leave a successful-looking partial handle.
The results handle must define retention/release when formulas change,
readers remain live, workbooks close, or evaluation fails. A result handle's lifetime is not
automatically the lifetime of preparation shared across successive results.

Acceptance: inputs cannot mutate results; readers of one result agree on context and axes;
unsupported measures cannot masquerade as zero; released ownership returns memory to
the expected baseline. Under the same compatible market context and measure, the batch value
and aligned risk vector equal the sums of separately evaluated singleton results within the
stated numerical tolerances. Duplicate occurrences count repeatedly. This comparison is an
acceptance check, not a requirement to evaluate every singleton on the batch tick path.
Exact public casing and reader table layouts remain decisions.
