# 6. Result reports: _ReportValues and _ReportRisk

[Pipeline overview](README.md) · [Previous: results](05-results.md)

## Responsibility

Select, label and format the batch's already evaluated aggregate results for Excel. A reader
neither interprets trade economics nor reaches back into the current market to complete a
calculation that evaluation omitted.

The intended result supplies the route's **mark and cash plus delta and dv01**, all
completed by evaluation before its handle is published. The accepted labels are
`bilateral_mark` and `bilateral_cash`, or `cleared_mark` and `cleared_cash`. The two reports
expose existing fields without
deferred valuation or risk calculations, and without zero placeholders for the other route. See
[result fields by route](result-fields-by-route.md).

The two reports are committed from the start:

```python
_ReportValues(results) -> MixedArray  # mark and cash under the route's labels
_ReportRisk(results) -> MixedArray    # total delta; DV01 where supported
```

Both take the results handle and spill what evaluation stored; neither selects a measure,
since one result has one route. `util_ReadHandle` on the same handle is a debugging spill
of the stored contents and replaces neither. These reports close the initial end-to-end
trade-evaluation path. A decomposition view for retained fixed/set/live amounts is a possible
later view, not a third required report. The values layout shows the two monetary fields
together under their route labels; the risk layout shows the scalar aggregates, the total
delta, the batch's change for a common one-price-unit move across its contracts, with its
units, and DV01 where supported, named unsupported where not. The delta by contract on the
batch's stable axis is retained in the result with its axis, labels and units, for later use
without recalculation; this report does not spill it. The exact spill shapes are pinned in
the pull request that builds them.

The selected pipeline returns a results handle from `_EvaluateTrades`; the two reports spill
views from that handle and calculate nothing independently.
They select the `valuation` or `risk` section of the same immutable `EvaluationResult`, using
its shared context. The internal valuation section stores one `mark` and one `cash`; the
route determines their outward labels without duplicating amounts. A risk spill follows
the stored market/rate axes, not the number of trades in the supplied batch.
The initial result represents the supplied batch as a whole, whether it contains one trade
or many. The two functions are built in #NN, [report-values.md](../../library/trades/report-values.md)
and [report-risk.md](../../library/trades/report-risk.md), and no grouping API is introduced.

## Allowed work and dependencies

Allowed work includes selecting retained aggregate measures, labeling their market axes,
formatting and inspecting matching source metadata. Any reporting arithmetic is confined to
values already present in the result and compatible units/coordinates. It cannot silently
combine currencies, different measures, incompatible risk units or unrelated curve buckets.

A reader cannot extract individual trade amounts from the aggregate result. Retaining the
source trades and payment facts does not mean their current values were calculated. To value
one trade or a subset, supply that collection through preparation and evaluation separately;
the selection API remains undecided. Do not reconstruct missing values or price lazily in a
reader. A future grouping view would need an explicit retained-result contract.

There is no implicit lookup of the current trade, current history or current price vector.
If display metadata is joined, use the matching immutable metadata retained by the result;
do not join old values to a newer trade table merely because the display IDs match.

A request for the full four-field result must already have succeeded completely before a
reader receives its handle. If an explicitly intermediate prototype result does not contain
a requested measure, the reader reports a visible error or unsupported state. It must not
substitute zero or trigger lazy repricing, calendar work, fixing gathering, a risk bump or
another market bind. No optional-measure framework is introduced for the four-output target.

Display the retained route, currency, as-of, value basis, date cutoff and cumulative
modeled-settlement scope, plus delta's commodity axis and DV01's curve/bucket, bump and sign.
The proposed cutoff is payment date on or before as-of; the proposed cumulative scope is
all settled components in the supplied batch. Evaluation applies that convention before
publishing results. Readers neither infer payment nor move an amount between value buckets.

The bilateral cash field is a modeled undiscounted payment total; the cleared cash field
is modeled entry-to-final-price P&L. Neither is an actual bank reconciliation, and cleared
settled P&L does not reconstruct excluded variation-margin flows. Shared risk names retain
their active value basis: `bilateral_mark` or `cleared_mark`. Readers must not relabel
the cleared P&L as NPV or its settled bucket as observed cash. The conventions and remaining
API choices are recorded in [results](05-results.md).

Post-evaluation support functions can build these reporting views from retained results.
A scenario or other operation requiring new market inputs is a new evaluation, with explicit
dependencies and a new result; it is not a reader of the old result.

## Intermediate amount views

The [fixture](worked-example.md) can yield the following intermediate views. They demonstrate
the aggregate amount path, not the completed route-specific four-field result:

| Requested collection | Projected unpaid amount, USD |
|---|---:|
| Supplied T1 + T2 batch | 140 |

| Bound market point | Batch amount delta, USD per USD/unit |
|---|---:|
| TOY Z26 remaining-assessment projection | 30 |

An aggregate decomposition view can show fixed leg `-4120`, floating leg set `2040`, and
floating leg live `2220`, which sum to `140`. These are the batch's retained amounts.

If future payment valuation has been requested and evaluated, a reader can additionally show
aggregate NPV `138.20` and NPV delta `29.90` for this fixture. Evaluation applies each relevant
payment treatment before aggregation. The reader does not select a discount factor for the
total undiscounted amount. Rates and payment valuation are deferred from the initial amount
path, and these illustrative values do not establish a DV01 convention or test the proposed
date-driven settlement lifecycle. Completing the full result requires those calculations
before publication, not a more capable reader. Valid zero DV01 under the stated cleared
model must remain distinguishable from an unimplemented bilateral rate-risk calculation.

## Acceptance and first scope

Repeated readers must cause zero encoding, binding or evaluation calls. A reader over an
older retained result remains stable after a new tick. Aggregate decomposition reconciles to
the batch amount; values and risks identify the same result snapshot. Duplicate source
occurrences remain identifiable and contribute fully to the evaluated total. One-trade and
many-trade results use the same reader shape. Requesting an unavailable individual value or
measure cannot trigger further valuation work.
For the full target, reading either route-specific value field, delta or dv01 in any order
must expose the same completed snapshot without new numerical valuation or risk work.
Changing the desired as-of, cutoff or settlement convention requires an explicit evaluation;
a reader cannot reinterpret an older result under a new convention.

Count table construction, copies and worksheet publication separately from valuation work.
Selective numerical repricing does not necessarily reduce the size of a full Excel spill.
An intermediate values report and a supported amount-risk report can validate the prototype.
They do not complete the target result profile. Postpone arbitrary joins, pivot APIs,
cross-result comparisons and a general reporting language.
