# 3. Market binding: PrepareTrades

[Pipeline overview](README.md) · [Previous](02-static-encoding.md) · [Next: evaluation](04-evaluation.md)

Built in #136 as the preparation of the trade kernel, `src/goosedove/trades/preparation.py`, on the NG example and
with no worksheet function yet; [kernel.md](../../library/trades/kernel.md) is the page.

## Responsibility

Connect the static encoding's market inputs to an explicit market state. Establish where
each input obtains its value and under what projection rule. Correct source identity,
coverage and order come before minimizing the arrays used for calculation.

Three responsibilities have become bundled in our discussion and should remain distinguishable:

1. **Binding:** map observations to applicable fixings or identified current-market positions.
2. **Compression/preparation:** fold known contributions and sum the supplied batch's
   exposure to each identified live input for the supported aggregate measure.
3. **Retention:** keep that work valid and available for later evaluations.

The agreed first implementation exposes these through one explicit operation:

```text
_PrepareTrades(trades, history) -> prepared_trades_handle
```

| Argument | Meaning |
|---|---|
| trades | One handle returned by CreateTrades, retaining resolved terms and static encoding for one or many trade occurrences |
| history | One compatible MarketHistory handle, carrying the index, calendar, valuation context and applied historical fixings; its calendar's index must be the batch's index, the same object, else refused by name |

Both arguments are required. The result is one immutable prepared-batch handle. For example,
`=_PrepareTrades(TradesHandle, HistoryHandle)` exposes the two dependencies directly to
Excel. The current as-of source is history.calendar.valuation_date.as_of; no separate as_of
argument is needed. Current prices arrive later through EvaluateTrades. This is the agreed
worksheet boundary, not a currently implemented creator.

One handle contains one or many trade occurrences. There is one batch path, including a
batch of one. The prepared handle retains the history-dependent work for evaluation;
the first version needs no separate private preparation store behind evaluation.

## Inputs and output

Inputs are static encoding, history/as-of/publication state, market layout and the declared
projection policy. The initial layout can be derived from history's calendar/schedule.
Current price values are not needed to prepare the linear fixed/float coefficients.

CreateTrades has already returned its resolved terms and static encoding under one handle.
Binding consumes the retained market input descriptors; it does not call resolution or
encoding again. Keep its history-dependent state separate from that immutable trade batch.

The initial amount output retains its input identities, the batch's `floating_leg_set`,
summed live exposure vector and its market axis. It can pre-add the aggregate fixed leg and set contribution
for arithmetic while preserving their separate meanings. Missing required fixings fail;
they are not forecasts, zeros or omitted averaging days. A physical futures component whose
expiry has passed fails preparation for the whole batch: the calendar marks its expiry day as
fixed, so from the day after expiry on, and the message names the occurrence, the contract,
its expiry and the valuation date. Nothing is omitted, zeroed, kept in mark or moved to cash;
the post-expiry workflow is a later feature. Scheduled dates and publication
availability are different facts; define the supported cutoff explicitly.

The current MarketHistory carries the as-of context through its calendar. In this initial signature, history
and the trade's retained static definitions must determine the live layout and projection
rule completely. If a supported layout or projection can vary independently, add it as an
explicit preparation input before supporting that variation. Current price values never
choose the rule. Preparing means applying the complete supplied history to the original
encoding, not adding a new fixing onto the previously prepared amounts.

Conceptual retained state (shared immutable references are sufficient):

```text
PreparedTrades
    trades reference                 # resolved facts, static encoding, fixed_leg
    history reference                # includes as-of and fixing snapshot
    live market axis / layout identity / projection rule
    fixed_leg                        # aggregate fixed leg, can reuse creation's total
    floating_leg_set                  # aggregate historical contribution
    live_exposure                    # M signed coefficients for the whole supplied batch
    source and payment facts         # retained through the original trade batch
```

See the [prepared matrix walkthrough](prepared-matrix.md) for different schedules summed
into one batch vector. Its expanded trade rows explain and validate the mathematics; they
are not required per-trade evaluation outputs or mandatory intermediate dense allocations.
Grouping by live input belongs in preparation when history-dependent, not on each tick.
The source batch preserves occurrence and payment facts for inspection and future preparation.
Producing individual values requires evaluating the desired single-trade/subset batch,
rather than asking a pure reader to reconstruct those values from the aggregate.
`floating_leg_live` is calculated later from current prices; it is not a prepared amount.
The word **set** means an observation has fixed, not that its payment has been paid.

The [Henry Hub lifecycle example](fixing-and-payment-state.md) distinguishes those states at
the monthly component level. For the proposed initial model, assume settlement on the encoded
payment date: preparation can derive `payment_date <= history.calendar.valuation_date.as_of` and retain the mask with
its payment groups. Required final fixings must be known before moving a component into the
settled bucket. Date rolls already rebuild preparation. No actual-payment store is required;
margining and reconciliation are outside this scope. The [result-field proposal](result-fields-by-route.md)
defines the proposed inclusive cutoff and cumulative cash scope. A future actual-payment
mode would require explicit settlement inputs rather than inferring bank transfers from history.

That decomposition describes fixed/float trades. A known cash record has no commodity
observations to bind; only inputs needed by its requested valuation measure apply. A common
pipeline does not require every instrument to have a commodity history or floating leg.

## Worked payload

The [fixture](worked-example.md) marks December 15 fixed at 68 and December 16 live:

```python
is_fixed = [True, False]
prints = [68, unused]
mark_of = [unused, 0]
mark_axis = [(toy_index, "Z26", "remaining_assessments")]

fixed_leg = -4120  # -7000 + 2880, already static
floating_leg_set = 2040  # 3400 - 1360
live_exposure = [30]  # 50 - 20 on the one common live input
fixed_plus_set = -2080
```

Here the live input is the projected level of the remaining assessment in Z26, not a quote
for the complete two-observation averaging contract. The point's role is part of its identity.
A directly quoted listed average/basis future may instead use its own market price. Its final
settlement formula does not force a reconstruction or create extra economic trade legs.

Aggregation is valid here for one compatible currency and undiscounted amount measure.
Different schedules need not be proportional: add coefficients in their identified columns.
Preserve contractual payment/source facts. Future discounting must prepare suitable payment
groups or otherwise retain the needed payment amounts before aggregation; a single already
summed amount cannot be discounted correctly with several distinct payment factors.

The [discounting walkthrough](batch-boundaries-and-discounting.md) develops that next step:
retain fixed/set amounts and live exposures by compatible payment group, with each group's
date, currency, curve association and treatment. These are group arrays, not evaluated
objects per trade. Current discount factors arrive at evaluation. The present two-input
PrepareTrades signature has no rate dependency and must not secretly retain discounted
coefficients across rate changes.

## Dependencies and reuse

Preparation is reusable only while its encoding, history, market layout and projection rule
remain valid. If the latter dependencies are immutable parts of encoding/history, comparing
those two object identities can be sufficient. A future independently changing layout must
become an explicit dependency. Matching vector lengths or display names is insufficient.

PR119's `Binding` and `Compressed` can supply the numerical mapping/fold. A real adapter still
needs to find the required observations: history contains fixed priced rows, not a ready-made
array aligned to every encoded market input. Current `PriceVector` has ordered numbers and
an index label; it cannot detect a silently permuted, correctly sized price column.

Excel sees the dependencies explicitly:

```text
trades   = _CreateTrades(...)
prepared = _PrepareTrades(trades, history)
results  = _EvaluateTrades(prepared, market)  # market references that same history
```

| Change | Work in the first implementation |
|---|---|
| Trade terms or used static definitions | Create a new trade batch, prepare it, evaluate it |
| History fixing arrival/correction or as-of | Prepare the whole batch from the new history, then evaluate |
| Only live prices, same history/layout | Evaluate the existing prepared batch |
| Reader selection | Read existing results |

The initial policy is a complete batch preparation whenever a preparation input changes.
Incremental fixing edits and per-row reuse are later optimizations. No append-only fixing
accumulator is required; corrected history and date changes use the same full preparation path.
Prepared handles retain their immutable dependencies through the real handle lifecycle.
At evaluation's boundary, reject a market whose history or live layout is incompatible;
do not repair the mismatch by silently preparing again inside evaluation.

## Acceptance

Hold encoding and history fixed; a new commodity-price snapshot must not rebuild binding,
gather historical observations or fold set contributions. A fixing arrival/correction or
date roll must rebuild the whole prepared batch under the initial conservative policy. Simultaneous
markets/histories must not overwrite each other's state. Releases and failures must leave
no stale results or indefinitely retained obsolete preparations.

Test fully fixed trades and the zero-live-mark case: a fully fixed batch within a still-live
market is supported, reads zero live prices and has zero live exposure. A market whose whole
calendar has ended is deferred; the Market is unchanged, and no dummy quote or inserted
contract stands in for it. Selective per-fixing updates and sparse representations can
follow measurements.

The [NG creation/preparation fixture](ng-creation-preparation-example.md) now gives concrete
input descriptors and ordered live coefficients, with a separate toy lifecycle for the
fixing/date cutoff and set contributions. It includes duplicate occurrences and compares
the aggregate with compatible single-trade examples. A tick must do zero fixing-fold work; a corrected
history or date roll prepares afresh. Current PriceVector carries a name and positional
values, so the fixture and the input contract must establish their order. Do not promise
detection of a silently permuted raw price column without a source of contract identities
that makes that check possible.
