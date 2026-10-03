# 4. Evaluation: EvaluateTrades

[Pipeline overview](README.md) · [Previous](03-market-binding.md) · [Next: results](05-results.md)

## Responsibility

Evaluate named financial measures and risks from valid prepared trade data and one coherent
market context. “Evaluation” is the operation's name; arithmetic also occurs in encoding,
binding and reporting. The requested result meanings determine the kernel inputs.

The agreed worksheet operation is the boundary into evaluation:

```python
_EvaluateTrades(prepared, market) -> results_handle
```

Each handle represents the supplied batch as the unit being valued, including a batch of one.
It returns aggregate measures and risks, without requiring one priced result per occurrence.
For an individual trade's value, evaluate that trade as a singleton batch. It accepts the output of
`_PrepareTrades`; it does not recreate schedules or fold historical fixings on a tick.
The target contains **two route-specific value fields plus shared delta and dv01**, completed
together before publication. The agreed names are `bilateral_mark`/`bilateral_cash` or
`cleared_mark`/`cleared_cash`, with common `delta` and `dv01`. The
[field definitions](result-fields-by-route.md) distinguish their valuation treatments and
define the proposed date-driven settlement cutoff with margining excluded. Detailed risk
conventions and additional rate-input arguments remain open.
The amount calculation below is an intermediate building block. It cannot claim to supply
that full target by filling unsupported fields with zeros. See the [results contract](05-results.md).
## One public operation, small private responsibilities

EvaluateTrades has one responsibility: produce a coherent evaluation snapshot of the supplied
prepared collection. Valuation and risk are separate result sections and private numerical
responsibilities. They share one validated set of current inputs and the same intermediate
amounts; separate Excel evaluation calls are not needed for the first four-field target.

An illustrative private flow is:

```python
def evaluate_trades(prepared, market):
    inputs = _evaluation_inputs(prepared, market)
    amounts = _payment_amounts(prepared, inputs)
    valuation = _value_payments(prepared, amounts, inputs)
    risk = _payment_risks(prepared, amounts, inputs)
    return EvaluationResult(valuation, risk, inputs.context)
```

These are responsibility sketches, not final declarations or a requirement to allocate an
object for each line. The Excel boundary publishes the completed result through a handle.
The library's private functions exchange typed data and arrays, not Excel handles.

| Private responsibility | Shared inputs and output |
|---|---|
| `_evaluation_inputs` | Check prepared/market compatibility once; gather aligned current prices and applicable rate factors/conventions once |
| `_payment_amounts` | Compute the required aggregate or payment-group amounts from retained fixed/set contributions and live coefficients |
| `_value_payments` | Apply the supported valuation treatment; produce aggregate mark and modeled cash |
| `_payment_risks` | Use the same coefficients, amounts and rate context to produce aggregate delta and DV01 |
| Result construction | Combine valuation, risk and shared context only after every required output succeeds |

This first flow materializes payment-group amounts where cash/discounting/DV01 need them;
it does not materialize an evaluated row per original trade. Cleared compatible components
can retain the simpler aggregate arithmetic. Private valuation and risk functions do not
each walk trades, bind observations or fetch history. Delta can reuse prepared exposure or
its discount-weighted form. DV01 can reuse the group amounts under its selected rate bump.
If a small kernel naturally produces value and a sensitivity together, share that work;
the logical separation does not require calculating the same quantity twice.

Applicable current curves, as-of and risk conventions must come from explicit supplied
inputs. The current Market API may need a later rate-context extension; this sketch does
not claim that it already carries every rate input or introduce ambient lookup. Numerical
functions consume trusted aligned arrays after compatibility has been established.

CreateTrades and PrepareTrades remain outside evaluation. Readers and reporting joins remain
after it. Start with the agreed four outputs; no arbitrary metric registry, flags for dozens
of outputs, lazy risk calculations or separate valuation/risk handle lifecycles are needed.
See [result storage](05-results.md) for the proposed small record behind the one result handle.

## First action at the boundary

After the Excel seam has validated individual argument types, establish compatibility
between the prepared batch and the supplied market: the history/as-of snapshot, source
identity, expected live layout and price units must agree. Use retained identities and
already validated mappings; do not re-resolve each trade or walk its observation schedule.
An incompatible market fails here and needs the appropriate preparation outside evaluation.

The market's history must be the prepared history, the same object; a market over another
history, even one of the same index and name, is refused by name, and evaluation never
prepares again. Then obtain current prices in the prepared matrix's column order, using the
retained mapping.
A correctly sized vector or the same display index name is not proof of correct alignment.
If the required inputs are already in precisely that order, the numerical path may consume
them directly. The first version evaluates the complete prepared batch.

The [prepared matrix walkthrough](prepared-matrix.md) shows what arrives at this boundary:
one batch exposure vector on identified live market inputs, and summed fixed/set amounts.
Expanded per-component rows are a reference for deriving/checking that vector, not required
tick outputs. Preparation has already summed the coefficients. Original occurrences remain
in the retained source batch, and repeated input occurrences each contribute to the aggregate.

## Amount calculation, then valuation treatment

For the linear fixed/float batch in one currency and one compatible undiscounted amount
measure, with M live market points:

```python
floating_leg_live = live_exposure @ prices  # (M,) @ (M,) -> one amount
amount = fixed_leg + floating_leg_set + floating_leg_live
amount_delta = live_exposure  # M aggregate mark sensitivities
```

No per-trade live amounts or normalized exposure-pattern reconstruction are required for
this aggregate output. Different schedules can be summed column by column without matching
patterns. A fully fixed batch has zero live contribution and needs no live prices.

The implementation may pre-add `fixed_leg + floating_leg_set` during preparation. In the
fixture, amount is a projected unpaid payment. For a futures adapter,
`quantity * (current_price - entry_price)` must be labelled as its specified entry-price P&L measure; it is not
automatically current asset NPV or the next variation-margin payment.

Rates are deferred in this first amount path. For a future extension with an eligible unpaid
payment or compatible payment group per row, in one currency, under the explicit fixture assumption
that supplied discount factors are independent of commodity marks:

```python
payment_npv = discount_factor_by_payment * payment_amounts
batch_npv = np.sum(payment_npv)
batch_npv_delta = np.sum(discount_factor_by_payment[:, None] * payment_exposure, axis=0)
```

This extension must retain/prepare payment-group amounts and exposures from the source facts;
the single aggregate amount vector above does not supply them. Discount each payment group
before aggregating. Different currencies, payment dates and settlement
treatments require their own mappings; a batch total alone is insufficient. Product-specific
valuation treatment remains necessary even when the arithmetic is shared.

Price fixing and modeled payment settlement remain separate facts. The proposed initial
rule assumes payment when `payment_date <= as_of`; preparation can derive this from encoded
dates and history's as-of. Apply it to each whole net obligation before final compression.
Discount only remaining bilateral payments. Settled payments contribute their full signed
amount to cumulative bilateral cash, without discounting or remaining trade risk. Move the
full amount, not a prior discounted NPV. Required final fixings must exist; forecasts cannot
become settled amounts. Cleared values use the proposed undiscounted entry-price P&L buckets.
Margining and actual-payment reconciliation are outside scope. See the
[result-field proposal](result-fields-by-route.md) and [lifecycle walkthrough](fixing-and-payment-state.md).
An actual-payment mode would be a separate future feature with explicit settlement inputs.

Equivalently, under those independence assumptions, discount each payment group's fixed/set
contributions and exposure before final compression. The resulting aggregate NPV exposure
is `discount_factors @ payment_exposure`, and is also the NPV delta on the stated commodity
axis. Keep the raw payment groups for cash, rate changes and DV01; the discounted vector is
specific to the current rate context. The [worked discounting example](batch-boundaries-and-discounting.md)
shows both equivalent calculations. The first version can apply factors during evaluation;
retaining a discounted vector between price ticks is a later dependency/reuse decision.

## Risks must identify their coordinates

Commodity and rate risks belong to evaluation, not readers. With the full target requested,
an inability to compute a required field fails publication rather than returning a partial
successful-looking result. An interim amount-only specimen is identified as such.

Commodity delta identifies both its value measure and its market axis: amount or NPV per
one unit of an identified mark. Evaluation retains delta by contract on the batch's stable
axis, the contracts in static order with zero on a contract that has fixed, with the axis's
labels and units, and the scalar total, the batch's change for a common one-price-unit move
across its contracts; `_ReportRisk` spills the scalar aggregates, the total and DV01 where
supported, and recalculates nothing, while the vector stays in the result for later use. Lots
and underlying quantity are different presentations
requiring the stored conversion. Sensitivity to bound marks is not automatically sensitivity
to raw vendor inputs or calibration instruments if another curve transformation lies between.

DV01 concerns a one-basis-point rate change, with the bumped curve/rates, sign convention,
parallel versus bucketed interpretation and held-fixed inputs specified. See
[CME's basis-point-value definition](https://www.cmegroup.com/education/courses/introduction-to-sofr/understanding-the-importance-of-basis-point-value).
The pipeline must choose its exact risk contract rather than borrow an unstated convention.
Sensitivity to a supplied discount factor is not yet DV01. Price-linear payoffs do not imply
linearity in the rate inputs used to build discount factors. Fixed and set-but-unpaid amounts
can retain rate sensitivity after their live commodity exposure is gone.

## Worked outputs and acceptance

At a remaining-assessment projection of 74, the [fixture](worked-example.md) gives batch
amount `140` and amount delta `[30]`. Separate singleton evaluations give `100` and `40`,
with deltas `[50]` and `[-20]`; these are acceptance comparisons, not required batch outputs.
The future payment-aware extension with factors `[0.99, 0.98]` gives batch NPV `138.2`
and NPV delta `[29.9]`. There is no DV01 expectation until a curve/bump is defined.

Require independent financial answers, batch-equals-summed-singletons consistency under
the same compatible context, duplicate contribution preservation, correct fixing transitions,
and agreement of reference and optimized calculations within documented unit-aware tolerances.
A missing or unsupported requested measure fails explicitly; it is not reported as zero.

Initially evaluate the whole prepared batch. PR119's `compressed_amounts` is one candidate
for this tick operation. Selective repricing needs changed-column identification, retained
matching prior prices/results and evidence that it beats a full multiplication. Incremental
amount differences also require a numerical-drift policy. Neither is a prerequisite here.

The [synthetic aggregation benchmark](aggregation-performance.md) measures only the amount
kernel. It does not measure this full result contract or the Excel dependency path.
