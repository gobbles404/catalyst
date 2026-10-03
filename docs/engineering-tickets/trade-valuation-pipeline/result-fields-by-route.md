# Result fields: bilateral and cleared

[Pipeline overview](README.md) · [Results contract](05-results.md) · [Readers](06-readers.md)

**Status:** Working design, 3 October 2026. Parallel mark/cash names are agreed in discussion;
the date cutoff, detailed risk conventions and concrete API/storage remain design proposals.
No production implementation is claimed. Margining, collateral, actual payment
reconciliation and partial/defaulted payments are outside this initial model.

## Parallel mark/cash fields

Use the same suffixes on bilateral and cleared results:

| Bilateral field | Cleared field | Common role |
|---|---|---|
| `bilateral_mark` | `cleared_mark` | Monetary valuation of components not yet moved into modeled cash |
| `bilateral_cash` | `cleared_cash` | Cumulative signed amounts finalized under the encoded payment-date convention |
| `delta` | `delta` | Commodity sensitivities of the applicable mark |
| `dv01` | `dv01` | Rate sensitivities of the applicable mark |

Here **mark is a currency amount**, not a quoted commodity price. Bilateral mark is the NPV
of remaining payments. Cleared mark retains the discussed undiscounted entry-to-current/final
price P&L meaning. Cleared cash retains the modeled cumulative entry-to-final-price P&L
meaning; margin flows are excluded. These names change neither calculation nor cutoff.

NPV is more specific: a present-value measure. Mark is a broader valuation label and can
include discounting where applicable. A discount factor of one does not by itself make NPV
an incorrect term; the concern is that entry-price P&L is not automatically the present value
of a remaining payment obligation. CME describes futures mark-to-market amounts as settlement
variation, distinguishing their calculation from a generic remaining-payment PV.
[CME money calculations](https://www.cmegroup.com/clearing/files/CME-Money-Calculations-Futures-and-Options.pdf).

Use route as a reporting distinction, while retaining the actual valuation treatment in
the resolved instrument/context. Cleared versus bilateral alone must not become a universal
rule for whether every future supported product uses discounting. The two risk fields keep
the applicable mark as their value basis. Detailed bump and sign conventions remain open.

The [result storage design](05-results.md) separates valuation and risk within one completed
snapshot. It proposes common internal `mark`/`cash` slots plus route context, with the explicit
route-specific labels exposed to the surface. These are different names for the applicable
stored measures, not duplicated numbers or fields for the other route.

## Payment dates are sufficient under an explicit assumption

CreateTrades resolves and encodes a payment date for each relevant payment component.
For a monthly Cal swap, that means twelve dates, not one date on the annual trade.
PrepareTrades applies history, including its valuation as-of, and can derive the proposed
mask `payment_date <= as_of`. We assume a component is paid on that scheduled date.
This is a pricing convention, not a claim to have observed a bank transfer.

Before its date, the component contributes to remaining value. On or after its date,
the full signed net amount contributes to the settled bucket. Required final fixings
must exist; missing fixings fail rather than turning a forecast into cash.
The cutoff is date-based and inclusive; intraday cutoffs are outside this first model.

`floating_leg_set` means known price observations. It remains distinct from payment
status. For a net fixed/float payment, move the fixed and floating contributions together.
Where the agreement instead requires separate payments, retain their separate dates.

For a fictional receive-floating/pay-fixed payment with quantity 2,500, agreed price
3.00 and final fixing 3.20, the full amount is `-7,500 + 8,000 = 500`:

| Snapshot | Bilateral NPV | Bilateral cash | Commodity delta |
|---|---:|---:|---:|
| Fully fixed, before payment; discount factor 0.99 | 495 | 0 | 0 |
| On/after payment date | 0 | 500 | 0 |

It is the full 500 that becomes cash, not a prior discounted value of 495. Until payment,
the known amount may still have rate sensitivity. Afterwards it is excluded from the
trade's remaining value and risk. Cash here is a historical signed payment total, not
a reinvested account balance or cash asset requiring separate valuation.

## Field meanings

Every result is aggregate for the supplied compatible collection, whether one trade or
many. Return the two fields for its route plus the same two risk fields. Do not populate
the other route's fields with zero placeholders.

| Route | Field | Meaning |
|---|---|---|
| Bilateral | `bilateral_mark` | Present value of remaining payments, discounted by their own payment date and applicable curve; this mark is NPV |
| Bilateral | `bilateral_cash` | Cumulative full signed net payments whose modeled payment dates are on/before as-of; undiscounted |
| Cleared | `cleared_mark` | Undiscounted entry-to-current-price P&L; once fixed, entry-to-final-price P&L until the modeled final payment date |
| Cleared | `cleared_cash` | Cumulative entry-to-final-price P&L for components on/after their modeled final payment date |
| Both | `delta` | Commodity sensitivities of the route's remaining-value field, on identified market coordinates |
| Both | `dv01` | Rate sensitivities of that same remaining-value field under the agreed one-basis-point bump convention |

The cleared buckets describe economic P&L and its finalization. They do not reconstruct
actual daily margin cash and do not assert an actual final cash transfer of the full P&L.
This proposal covers the discussed financial price-difference payoff; route alone does
not define every listed product's payoff or physical-delivery accounting.

The proposed cash/settled scope is **all settled components of the supplied batch through
as-of**, preserving signed amounts and duplicate occurrences. It is not only today's cash,
cash during a reporting month, or an account balance. Those would be separately named views
with the requisite retained dated results; a reader cannot reconstruct them from one total.

## Shared risks and context

Delta uses the same field and coordinate convention on both routes. Its value basis is
`bilateral_mark` or `cleared_mark`; bilateral delta therefore includes the applicable
payment discounting. A set-but-unpaid amount can have zero commodity delta and nonzero DV01.
Components in the settled bucket contribute neither to these remaining-trade risks.

DV01 needs an agreed curve/bucket, bump direction, sign and held-fixed inputs before the
bilateral field can be implemented. The explicitly undiscounted cleared P&L model has zero
rate sensitivity when commodity prices are held fixed. This is a supported model zero;
missing bilateral rate-risk implementation must never be replaced with zero.

Retain route, currency, as-of, value basis, cutoff, cumulative scope, market/curve axes,
risk units and immutable source/context references with the result. These give meaning to
the four measures without requiring a valuation object per trade.

## Pipeline consequences and acceptance

- CreateTrades retains static dates, terms and payment ownership.
- PrepareTrades folds fixings and derives date-based status from encoded dates and history's
  as-of. Keep compatible payment groups before compressing remaining live exposures.
- EvaluateTrades discounts only remaining bilateral payments, includes settled signed amounts
  without discounting, and completes both route-specific values and common risks together.
- Readers expose the completed snapshot. They never infer settlement or reprice it.

An as-of change already rebuilds preparation; it updates the date mask without a new
external settlement store. A future actual-payment feature would add an explicit dependency,
but is not required for this model. Current discount factors still belong to evaluation.

Acceptance examples should cover before/on/after-date snapshots, a fixed-but-unpaid payment,
multiple monthly payments at different states, negative and duplicate payments, missing final
fixings, and batch equality with the sum of compatible singleton results. The whole net payment
leaves remaining value exactly once. No settled amount receives a discount factor.
