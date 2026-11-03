# I4a Dated exposure and market alignment

[Pipeline overview](README.md) · [Encoding](02-static-encoding.md) ·
[Preparation](03-market-binding.md) · [Evaluation](04-evaluation.md) · [Results](05-results.md)

**Status:** Agreed engineering slice, 4 October 2026, with the two narrowings of the review of
the same day: the market reference is derived from the observation date by the calendar's own
rule and retained, and the fixing source is kept once on the shared object. Built in #140:
[kernel.md](../../library/trades/kernel.md) is the page of the kernel as it stands, the five
records and the daily toy among them; `src/catalyst/trades/observations.py` is the new module,
`encoding.py`, `preparation.py` and `evaluation.py` the reshaped ones.

**Placement:** I4 → **I4a** → I5 → I6 → R1. I4 is built, #139, I4a #140, I5 #141 and I6 #142,
each stacked on the one before. [R1](penultimate-trades.md) specifies public penultimate
booking using this dated path, the payment lag counted from the derived pen date, and stacks
on #142.

## Outcome

Evaluate the supplied batch on an aggregate array of dated market inputs. Each array position
maps to an actual observation date and an explicit market reference. Different dates can
reference the same contract price. Trades using the same dated input can contribute to one
aggregate slot, within a compatible valuation and payment group.

This extends the contract-only kernel from #136. It changes the representation used in
encoding, preparation and evaluation; it is not solely a report that expands a monthly total
after valuation. The existing NG answers and public function signatures remain acceptance
requirements. One trade and many trades use the same path, and duplicate occurrences count.

The first implementation uses dates. Market/index definitions and the resolved observation
rules establish the relevant dates and referencing rules. Hourly intervals and other time
coordinates remain later work. There is no new `valuationParams` or resolution argument in
this slice; its eventual API is not settled by this ticket.

## What I4 preserved

I4 implements `_CreateTradeTemplate` and `_CreateTrades` without a daily valuation engine or
Asian entry. The returned batch retains the resolved schedule method, component-to-contract
mapping, static schedule/source references, signed quantities and coefficients, entry-price
offsets, and payment/component ownership. For `lastday`, the retained immutable contract
schedule already supplies the observation date: its final pricing date. No copied date array
was needed in I4, the date being unambiguously available through the retained objects. I4a
materializes the dated encoding from those facts without reparsing tickets or contract codes
during preparation or evaluation.

The retained trade state is not reduced to contract totals alone. Those totals cannot explain
different observation weights within a month. No additional workbook field carries a date
already determined by the approved schedule rule.

## Coordinates and aggregation

The logical coordinate is **observation date + identified market reference**, inside the
existing compatible valuation/payment group. Index/source identity and units are part of
compatibility, not inferred from a display label.

The reference is derived, not supplied. The market's calendar already says which contract
supplies each day's price, the first contract whose expiry is on or after the day, and its
history stores that contract's settlement for the day: in the toy below, 1 December maps to
Z26, and the history holds Z26's fixing for that date and no other contract's. So each slot's
reference is the contract pricing its date, derived once from that rule at encoding and
retained. An observation whose component's contract is not the day's pricing contract, F27 on
a day Z26 prices, fails under the expiry-based methods rather than silently becoming Z26,
since those methods take the contract's own days and a futures history holds one settle per
day; under `asian`, since #165, the day's contract is the reference and the booked contract
keeps the fixed leg and the payment,
[calendar-driven-asian-references.md](calendar-driven-asian-references.md). A reference may appear on several dates;
supporting several contracts on one observation date comes later, with a history that holds
them. This is the slice's supported scope: what the current history covers.

| Retained fact | Meaning |
|---|---|
| Observation date | The date whose observation contributes to the payoff; not the valuation date, contract month label or payment date |
| Market reference | The contract pricing that date, derived by the calendar's rule and retained: the live contract supplying the projected price while the observation is unfixed, and the contract whose settlement on that date fixes it |
| Signed coefficient | Amount currency per unit of the referenced quote price, after the existing quantity and currency conversions |
| Component/payment ownership | The obligations and treatment to which fixed, set and live amounts belong |

The fixing source is one for the batch, the batch's index and the history over it, and is kept
once on the shared object: the identity check that the history is the index's is the whole
rule. No slot repeats it. Each slot retains its date and its contract reference. A second
fixing source or publication rule, when one exists, is retained or refused then; this slice
uses the supported single-index context and direct contract references, and adds no
interpolation or market-construction API.

Use deterministic coordinate order, by payment group and then by date within it. Keep the
coordinate identities stable across ticks and history changes; fixed slots retain zero live
exposure. Compact active views are permitted alongside that axis. Calendar days with no
exposure need not occupy permanent dense storage; any expanded inspection view must map
positions to real dates and identify zero-exposure gaps correctly.

Aggregation must preserve entry-price offsets and payment ownership even where live exposures
net to zero. This ticket does not widen today's payment compatibility rules. In particular,
it does not authorize merging obligations with different payment dates or settlement states
into one payment. Future discounting will require those retained distinctions.

Three distinctions hold throughout. Payment groups remain separate from price references:
sharing Z26's quote does not establish that two obligations pay together. Physical expiry
remains the traded contract's expiry: an earlier observation fixing must not itself trigger
the expired-physical refusal. Names keep their meaning: `offset` is the futures entry-price
adjustment; fixed/float explanations may say `fixed_leg`, `floating_leg_set` and
`floating_leg_live`; `set_unsettled` specifically excludes amounts already paid.

## Responsibilities through the pipeline

| Boundary | Required work |
|---|---|
| CreateTrades and encoding | Materialize the supported observation dates, signed weights and static market references from resolved terms. Preserve the source facts and payment ownership. No current prices or history flags. |
| PrepareTrades | Apply the supplied history under its cutoff; obtain each required fixing; retain the set amounts; aggregate compatible dated live exposures; retain the mapping from dated slots to unique live contract references. Compute the dated exposure vector and its contract delta aggregation here, once for this history. |
| EvaluateTrades | Check the existing identity/coverage rules, obtain the unique required live contract prices, gather them onto the prepared dated slots, multiply the aligned arrays and complete the aggregate results. Retain the dated live contributions and their coordinates. |
| Results and readers | Preserve the dated state and the existing contract delta vector and totals. The two scalar reports keep their agreed meanings. Inspection reads this snapshot without rebuilding schedules, applying fixings or obtaining current prices. |

A minimal logical payload is shown below. Names are illustrative internal fields, not new
worksheet parameters or a required class layout. K counts retained dated coordinates, L
live dated coordinates and C unique live contract references; none counts input trades.

```text
Encoded dated terms
    observation_date[K]
    market_reference[K]            # derived from the date, retained
    signed_coefficient[K]
    component and payment attribution
    offsets by the existing compatible payment groups

Prepared dated state
    reference to encoded terms and supplied history
    is_fixed[K]
    dated_live_exposure[K]          # zero where fixed
    set contributions and modeled cash by their existing ownership
    live_slot[L]                   # positions on the retained dated axis
    unique_live_contract_rows[C]   # static schedule references, not raw price-vector offsets
    contract_for_live_slot[L]      # positions in the C gathered contract prices
    delta_by_contract and delta_total on the existing stable contract axis

Evaluation result
    existing context, mark, cash, contract delta, total delta and supported DV01
    reference to prepared dated state
    dated_live_contribution[L]     # paired with live_slot; not a daily allocation of total mark
```

The defining live calculation is:

```python
contract_prices = market.live_prices(prepared.unique_live_contract_rows)
dated_prices = contract_prices[prepared.contract_for_live_slot]
dated_live_contribution = prepared.dated_live_exposure[prepared.live_slot] * dated_prices
floating_leg_live = dated_live_contribution.sum()
```

The existing payment/settlement treatment combines that live amount with the retained fixed
and set amounts to complete mark and cash. A fully fixed supported financial batch reads
no live prices and has zero live contribution. Market compatibility and missing coverage
still fail visibly. A moving prompt never turns a retained static schedule reference into
an unchecked offset into today's shortened price vector.

A future optimization may use an algebraically equivalent contract-level dot product only
if it preserves the required dated state and has its work and retained outputs reviewed.
This slice first establishes and tests the dated evaluation path. It does not retain two
production engines or evaluate every trade separately to reconstruct the dated aggregate.

## A contract future on the dated axis

A `lastday` future places its whole coefficient on its final observation date and references
its traded contract. It does not spread its quantity over every day of the month merely
because the axis has daily resolution. Thus the existing NG example can acquire dated
coordinates without changing its economics or introducing an averaging assumption.

The physical NG boundary remains unchanged: preparation refuses an expired physical
component, by the traded contract's expiry. Do not manufacture a zero-delta post-expiry result
or move that physical position into cash. The financial fixture below demonstrates
observations becoming fixed. Its cutoff uses the current rule: an observation remains live on
its date and becomes fixed once that date is before as-of, with the required fixing supplied.

## Independent small financial example

Use this as a library-level fixture supplied with resolved observation terms. It does not
enable a new public `schedule_method` or claim to describe a listed exchange product.

Assume one index quoted in USD per unit and settled in USD, three equally weighted observations on
1, 2 and 3 December 2026, and one compatible financial payment group paying on 5 January
2027. Every live observation projects directly from a toy Z26 reference that remains in
the market's live coverage throughout these states. Its history supplies the three dated
fixings specified below. All states shown are before payment, so cash is zero.

Give the toy schedule X26 expiring on 30 November 2026 as its preceding boundary, Z26
expiring on 31 December 2026 and G27 expiring on 29 January 2027; provide all history required
by that calendar in addition to
the three observations shown. This keeps Z26 live for projection through the example and
allows the fully fixed batch to sit inside a valid market. These are synthetic schedule
dates, not the real NYMEX NG expiry schedule. The traded toy's last observation is 3 December;
the expiry of its live reference does not replace that observation date.

| Trade | Signed total quantity | Fixed price | Coefficient on each date | Offset |
|---|---:|---:|---:|---:|
| A | 60 | 70 | 20 | -4,200 |
| B | -30 | 72 | -10 | 2,160 |
| Batch | 30 | Not one executed price | 10 | -2,040 |

Before any fixing, with Z26 at 74, the dated view is:

| Array position | 0 | 1 | 2 |
|---|---:|---:|---:|
| Observation date | 2026-12-01 | 2026-12-02 | 2026-12-03 |
| Market reference | Z26 | Z26 | Z26 |
| Dated live exposure | 10 | 10 | 10 |
| Referenced price | 74 | 74 | 74 |
| Live contribution | 740 | 740 | 740 |

Three date slots require one current contract quote, reused at three positions. The hand
answer is `-2040 + 740 + 740 + 740 = 180`. Holding the live quote at 74 and applying dated
fixings of 71, 75 and 73 gives these independent expectations:

| As-of | Newly fixed observation | Dated live exposure | floating_leg_set | floating_leg_live | Mark | Contract delta |
|---|---|---|---:|---:|---:|---:|
| 2026-12-01 | None | [10, 10, 10] | 0 | 2,220 | 180 | 30 |
| 2026-12-02 | 1 Dec at 71 | [0, 10, 10] | 710 | 1,480 | 150 | 20 |
| 2026-12-03 | 2 Dec at 75 | [0, 0, 10] | 1,460 | 740 | 160 | 10 |
| 2026-12-04 | 3 Dec at 73 | [0, 0, 0] | 2,190 | 0 | 150 | 0 |

These are mark amounts under the explicitly undiscounted financial fixture. Retaining the
observation-date contributions does not allocate the offset, cash or total mark among those
dates. Label the dated live contribution accordingly.

## Delta and roll-off meaning

The dated live exposure is an attribution of sensitivity to the referenced contract price.
Repeated references do not create independently observable daily market prices or three
independent market shocks. In this direct-reference model, sum dated live exposures by their
reference to obtain the existing contract delta vector, then its scalar parallel-move total.

For the fixture, each observation fixes 10 units of signed sensitivity, so the change in
contract delta at each fixing is -10. For a short exposure of -10, the sensitivity leaving
the live side is -10 and the change in delta is +10. Keep that sign distinction explicit in
any roll-off view. Fixing state, not payment, removes this commodity sensitivity; a fixed
but unpaid financial amount has zero live commodity delta.

The retained dates, coefficients and cutoff rule must support an inspection of scheduled
roll-off without live prices or repricing. A projected roll-off is conditional on the stated
fixing/cutoff convention; an actually missing required fixing still fails preparation. A
standalone chart/report API and other resolutions are later work.

## Acceptance and work budgets

| Acceptance | Evidence required |
|---|---|
| Existing NG behavior | Preserve all reviewed values, conversions, contract deltas, duplicate handling, identity failures and the expired-physical refusal from #136. |
| Dated evaluation | Reproduce every number above from hand expectations, including fixed-but-unpaid zero delta and a fully fixed batch inside a valid live market. Do not regenerate expected numbers from the implementation under test. |
| Aggregation | Batch equals summed compatible singletons; duplicates count; zero net live exposure does not erase a nonzero offset. Several dates may share a contract; one date naming a contract other than the day's pricing contract is refused as unsupported. |
| Offsetting dates | Keep +10 on 1 Dec and -10 on 2 Dec, both projecting to 74, even though current contract delta and live value net to zero. With no offset, after 1 Dec fixes at 71 the mark is -30 and live contract delta is -10. |
| Mapping | Reordered incoming trade rows preserve economics; reference/date permutations align correctly or fail. No accidental merging across incompatible payment groups. |
| Risk | Dated live exposures reconcile to contract deltas and total delta; dated live contributions sum to `floating_leg_live`. A one-unit quote bump moves mark by that contract's retained delta, not by one selected dated slot's exposure. Positive and negative roll-off signs are covered. |
| History changes | Fixing arrivals, corrections and date rolls build new preparation from static encoding. A correction updates set value without restoring fixed exposure. A required missing fixing fails. |
| Tick work | No schedule expansion, trade resolution, coefficient regrouping or fixing reads. Retrieve each unique live contract price once; gather/multiply by prepared dated coordinates. Delta arrays and totals are reused. |
| Cardinality and memory | Measure work against unique dated coordinates and unique referenced prices, as well as trade/component counts. Many duplicate trades must not create per-trade tick arrays. Measure date expansion and retained contributions explicitly. |
| Ownership and inspection | Arrays are owned/read-only or share immutable backing. Old results keep their coordinates and values after later ticks. I5 exposes the dated contents through inspection without completing valuation in a reader. |

Use example/property tests and the existing work-counter/allocation conventions. Preserve
the separation between independent financial expectations and production golden snapshots;
existing goldens are not rewritten in the code-change PR. The daily example is small enough
to review before any production snapshots are accepted.

## Handoff to I5 and later slices

I4a delivers the internal dated encoding, preparation, evaluation and retained-result
contract, with its fixtures and measured work. I5 wires `_PrepareTrades`, `_EvaluateTrades`,
`_ReportValues` and `_ReportRisk` to it, and pins the debugging spill and handle lifetimes.
The two reports still return the agreed aggregate scalars; stored contract and dated vectors
remain available without recalculation. No new public creator or mandatory reporting argument
is introduced here.

[R1](penultimate-trades.md) derives the pen observation from the underlying expiry and counts
payment from it, for PHH and ICE WTI. I6, #142, uses the dated representation for its
financial payment lifecycle under `lastday`. Observation dates must never be replaced by
payment dates to join these pieces.

Penultimate booking is R1's, built in #144 on this dated path, last3day R2's, built in #157, and calendar-month Asian booking R3's, built in #158. Hourly or
other time grids,
bilateral discounting and DV01, physical delivery, an entirely ended market calendar, incremental fixing updates,
selective tick recalculation and several contracts on one observation date remain separate
slices. Compact arrays versus dense storage is an implementation choice; the dated identities
and reconciliation requirements are not.
