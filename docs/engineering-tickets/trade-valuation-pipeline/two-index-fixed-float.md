# Two index legs on fixed_float

**Status:** Agreed with the owner, 21 October 2026, for
[issue #212](https://github.com/gobbles404/catalyst/issues/212). Build as three
stacked pull requests after the payment-day work in #214, as the delivery section
sets out. One common net payment per monthly component is the v1 rule, agreed here
and not checked against a confirmation; separately paying legs are outside this
version. This ticket supersedes the issue's original single-fixed-price and
combined-index alternatives. The first pull request, the internal one-leg
representation, is #215; the second, two-leg resolution and pricing, is #216,
stacked on it; the third, the pair on the sheet, is #217, stacked on #216.

## Outcome

Book a fixed-price location deal as one ticket row whose two index legs are
added. Each leg has its own fixed price and schedule method. The whole trade's
fixed price is their sum, calculated rather than entered a third time. Support
cleared and bilateral financial trades, retaining the existing single-index path.

Use the existing index, history and market objects directly. Do not create a
combined index or a third risk position. A Henry Hub plus Waha trade retains
Henry Hub and Waha exposures, and its rate risk belongs to the selected discount
curve. Save each leg's value and DV01 attribution without changing the primary
DV01 report grouping from curve and currency.

The concrete market example is ICE's
[Waha Fixed Price Future](https://www.ice.com/products/69723181/Waha-Fixed-Price-Future),
which settles to the monthly outright IFERC Waha index. The
[Waha Basis Future](https://www.ice.com/products/6590171) settles to that index
minus NYMEX Henry Hub's last-day settlement. Matching-month LD1 plus basis thus
reproduces the outright final reference price. This identity does not assign the
outright deal the payment dates or fees of two separately booked futures. These are
sourced product examples; they establish nothing about the terms of a bilateral
confirmation.

## Booking and worksheet contract

Keep the three function names and argument positions. The first argument of each
is named `indexes`, `histories` and `markets`, and its help says it accepts a
single handle or a row or column of handles through the existing `Handles[...]`
binding; the ordinary single-index entry stays as it is:

```text
_CreateTrades(indexes, fields, trade_rows, template)
_PrepareTrades(trades, histories)
_EvaluateTrades(prepared, markets, [discount_curve_set])
```

One batch uses one index or a fixed pair of distinct indexes, in that order, for
every row. Histories and markets are matched by exact index identity, independent
of their range order. Refuse a third index, the same index twice, missing or extra
inputs, two histories/markets for one index, and distinct indexes with the same
name under the existing uniqueness rule. Do not justify the duplicate refusal
by saying that adding an index to itself nets to zero; it is a scope boundary.

Preparation requires one valuation date across the histories. Evaluation requires
each market to retain the exact history used to prepare its leg. Keep the current
live-price coverage/alignment checks. A refusal names the argument position or
cell, index and leg where relevant. No partial handle is published.

Extend the existing `fixed_float` definition:

| Field | One index | Two indexes |
|---|---|---|
| `fixed_price` | Existing fixed price | First leg's fixed price |
| `schedule_method` | Existing method | First leg's method |
| `second_fixed_price` | Absent | Required, finite number |
| `second_schedule_method` | Absent | Required, existing method choices supported by the second index |

Fields may be supplied in either template or ticket, never both. Keep strict
headers, no overrides, numeric trade IDs, zero quantities and duplicate occurrences.
There is no `index2` field: indexes are the creator's argument. Addition is the
only combination in this slice, so there is no sign selector.

A template has no indexes. It validates any supplied second-leg field's type and
intrinsic choices, but leaves the count-dependent rule to `_CreateTrades`, where
the index count is known. Both fields show `two indexes` under `required_when` in
`_ShowInstrument`, and `_CreateTrades` refuses by the field's name:
`second_fixed_price is missing, expected it with two indexes` and
`second_fixed_price is 1.0, expected none unless two indexes`, likewise for
`second_schedule_method`. The index count is not a ticket field. Both new fields
are disallowed in quote templates. Existing single-index quote templates and
`_Quote` remain unchanged.

An illustrative ticket, with the index handles in B2:B3 and the shared terms in
the template:

| trade_id | contract_code | quantity | fixed_price | second_fixed_price |
|---|---|---:|---:|---:|
| 12345 | F27 | 10000 | 3.30 | -0.30 |
| 12346 | G27 | -5000 | 3.40 | -0.35 |

```excel
=_CreateTrades(B2:B3, TicketHeaders, TicketRows, TemplateHandle)
```

The template selects `fixed_float`, both schedule methods, `quantity_unit`,
`quantity_per`, route, settlement and payment terms. Bilateral rows also retain
the current counterparty and `discount_curve_key` requirements. Existing mixed
row fields continue to work: methods, prices, quantity bases, payment terms and
curve keys need not be constant across the batch where they can vary today.

## Shared terms and compatibility

Each leg owns its index, fixed price, method, observations and pricing references.
The trade owns the period, signed quantity, quantity basis, route, settlement,
payment terms, attribution fields and selected discount-curve key. Both legs
represent the same physical quantity for each booked monthly component.

For this first slice, require the indexes to have the same quote currency unit,
quote quantity unit and settlement currency unit. This makes the two entered
prices directly additive. Do not invent cross-currency or differently quoted
price normalization in this feature. Existing quantity conversions still apply.

The entered `quantity_unit` must resolve on both indexes to the same economic
quantity per entered unit, using existing conversion tables. A shared label alone
is insufficient. In particular, `LOT` meaning 10000 MMBtu on one index and 2500
MMBtu on the other is refused as an ambiguous common quantity. `MMBTU` at one on
both is accepted; the two reporting lots may differ. Keep these extra pair checks
off the existing one-index behavior.

Resolve the period independently against each schedule and match the booked
monthly components by month, not by the schedules' row numbers. A missing month
fails by index and month. Existing method rules still select each index's own
observations and, for Asians, its daily pricing references. `quantity_per=month`
uses the existing monthly amount; `calday` counts the common covered calendar
days once, independently of the two observation schedules. No implicit second
quantity or second quantity basis is introduced.

Two-index physical settlement is outside this slice and fails explicitly.
Existing single-index physical behavior stays intact. Futures and IFERC indexes
already supply the first use case; Gas Daily support in #211 is not a prerequisite
and this ticket adds no Gas Daily method or fixing policy.

## One payment arrangement

**The v1 rule, agreed 21 October 2026:** both legs share one net payment per
booked monthly component. Each leg's amount is its own index's price against its
own fixed price on the common quantity; the two add into the component's one
payment, discounted once on its date with the selected curve, both legs taking
that factor; each leg's value and DV01 are retained, and their sums are the
combined result. A calendar strip has twelve such payments, both legs sharing each
monthly date. This was agreed here and has not been checked against a
confirmation; it is a design rule, not a verified market fact. Separately paying
legs are outside this version and are never silently forced together: they would
need distinct payment groups and their own discounting, while primary DV01
reporting would still group by curve and currency with leg and index attribution
retained, and a second payment date would create no third index and change no
reporting policy by itself.

The shared date:

- A rule in `payment_day` applies once to the later of the two legs' last required
  observations, on the trade's payment calendar. The resulting date must be
  strictly after both observations.
- An explicit date applies unchanged to both legs and every component of a strip,
  and must be after the row's final observation across both legs. Do not roll an
  explicit weekend or holiday date.
- Keep the existing payment-calendar requirement and compound offset grammar.
  No new payment anchor field or date-rule parser is needed.

Do not calculate a separate payment from each leg and then choose one after
valuation. Resolve the shared date during creation. Retain each leg's observations
and the shared resolved payment in readback so the rule is inspectable.

Both legs in a bilateral row use its `discount_curve_key`. Existing different
keys across rows remain supported. Payments on different dates or keys must not
net before discounting. Paid amounts follow the existing `payment_date <= as_of`
cash treatment; the common payment cannot become paid while one required
observation is still live.

## Calculation and retained state

For each monthly component, after quantity conversion and observation weighting:

```text
amount_A = Q * (price_A - fixed_price_A)
amount_B = Q * (price_B - fixed_price_B)
combined_fixed_price = fixed_price_A + fixed_price_B
payment_amount = amount_A + amount_B
```

For an unpaid bilateral payment, use its selected factor `DF` and
`tau = calendar_days(as_of, payment_date) / 365`:

```text
NPV_A = amount_A * DF
NPV_B = amount_B * DF
DV01_A = -tau * NPV_A / 10000
DV01_B = -tau * NPV_B / 10000
NPV = NPV_A + NPV_B
DV01 = DV01_A + DV01_B
```

Use the current signed analytic DV01 and cross-gamma conventions. Cleared
valuation remains undiscounted with zero DV01 and cross-gamma. On payment, the
undiscounted leg amounts become cash and their remaining mark and rate risk are
zero. A fixed but unpaid leg still has DV01, even though it has no commodity delta.

Represent legs as a collection inside the existing pipeline, with one member for
today's case. Keep shared trade facts once. The implementation may choose record
names, but must preserve these ownership boundaries:

| Record | Shared state | Per-leg state |
|---|---|---|
| Created trades | Booked rows, periods/quantities, payment dates/keys, reserves | Index, method, entered fixed price, resolved observations and encoding |
| Prepared trades | Valuation date, shared payment status and rate-date preparation | Exact history, fixed amounts, live exposures and original index risk axes |
| Evaluated trades | Combined mark/cash, DV01 by curve/currency, reserves | Exact market, leg/payment amounts and values, index delta, leg DV01 attribution and index/curve cross-gamma |

Keep original index identity in slot and contribution ownership. Two observations
on the same date under different indexes are not the same slot. Likewise, keep
fixed-price amounts and leg values separable when payment dates and curve keys
coincide. Grouping into payment groups and slots may merge compatible occurrences
within a leg; it must not erase the attribution required here.

Each leg's fixed-price offset is booked once. The derived combined fixed price
does not create another offset. Compute the common payment's total from its leg
contributions; do not collect both that total and its constituents as positions.
The existing risk-only `AggregateResults` is not a substitute for the evaluated
trade result's values, cash and reserves.

## Risk grouping and readback

Primary DV01 reporting remains **exact discount-curve object and settlement
currency**, on the payment date/month/year axes. Index is retained as attribution,
not introduced as a new rate factor. Cashflows continue to join the same curve
group without needing a commodity index.

Commodity nominal delta and delta remain separate per original index, in each
index's reporting lot. Cross-gamma remains separate per original index and exact
curve. Never publish a grand total of unlike index lots or their cross-gammas.
Preserve today's observation-day and pricing-contract month/year bucketing rules.

`_ReportValues` and `_ReportReserves` keep their combined-batch shapes.
`_ReportRisk(results, risk, bucket)` keeps its signature, selectors and Total-first
layout. A two-index result shows the same risk grouping as an equivalent
collection of two single-index results: two commodity groups, and one DV01 column
per used curve/currency, not a new combined-index column. No new index-based DV01
selector or deal-grouping reader is required in this slice.

Retain leg DV01 with its original index, selected curve/currency, payment date and
source batch/leg. The collector preserves access to this attribution while adding
the saved rate contributions once to curve totals. It may retain source records
by reference; it need not eagerly create every future grouping. Readers do not
reprice, reapply factors or perform risk reductions.

Readback must expose the retained leg/payment values. For one payment of the
example below, its economically relevant rows are:

| leg | index | curve | payment_date | payment_amount | payment_factor | leg_mark | leg_cash | leg_dv01 |
|---|---|---|---|---:|---:|---:|---:|---:|
| 1 | A | SOFR | 4-Jan-2028 | 2000 | 0.95 | 1900 | 0 | -0.19 |
| 2 | B | SOFR | 4-Jan-2028 | -1000 | 0.95 | -950 | 0 | 0.095 |

This is a column/meaning requirement, not a requirement for a new reader or a
second table format. Extend the existing result readback: leg/payment amounts
appear once on that leg/payment group's first slot row, with dashes below, as
current payment facts do. Never repeat additive values on every observation.
Show the combined totals separately once; they are not another index row.
The created-trades readback keeps one row per component, showing `fixed_price`,
`second_fixed_price` and the derived `combined_fixed_price` beside the other
applicable fields; the prepared and result readbacks keep one row per slot and
identify each slot's leg and original index; the combined payment and the totals
appear once and are never repeated across leg rows. Keep the existing single-index
readback layout; define and pin the extra columns for the new two-index form
before implementing its workbook block.

Readback describes the payment groups and slots as saved, not per-ticket-row
valuations.
Source membership and leg identity are retained without promising new per-trade
valuation storage. Index and curve labels use the existing identity/name rules.
The handle text joins the two index names with `+` in leg order,
`30512:trades:NYMEX NG+Waha IFERC:9`, a readable descriptor and nothing more:
identity checks use the objects, nothing parses the descriptor, and no Index is
registered for the pair.

## Reserves

The first leg's matched specification supplies the deal's brokerage and clearing
rates. Apply them once to the booked components and absolute quantities, under
the current applicability rules: a brokered row incurs brokerage, a cleared row
incurs clearing, and a bilateral row incurs no clearing. The current absent or
case-insensitive `none` broker treatment remains. Do not read the second index's
fee rates or charge a second fee because it supplies another price.

Marketing is booked once per occurrence, as today. All reserves remain outside
mark, cash, delta and DV01. Leg order is meaningful for fees; reordering indexes
and their prices/methods preserves economics but need not preserve reserves.

## Hand-priced acceptance

Use synthetic indexes quoted in USD/MMBtu, each defining one MMBtu per entered
unit. A's reporting lot is 10000 MMBtu; B's is 2500. For the first table both legs
are live on 4 January 2027, with an explicit valid payment on 4 January 2028,
exactly 365 days later. Supply preceding boundary contracts and observation dates
that make those states valid; these are synthetic schedules, not exchange dates.

Quantity is 10000 MMBtu, fixed prices are 3.30 and -0.30, live prices are 3.50 and
-0.40, and the selected SOFR factor is 0.95:

| Measure | A | B | Whole trade |
|---|---:|---:|---:|
| Entered/derived fixed price | 3.30 | -0.30 | 3.00 |
| Undiscounted amount | 2000 | -1000 | 1000 |
| Bilateral mark | 1900 | -950 | 950 |
| Nominal delta, each index's lots | 1 | 4 | No cross-index sum |
| Delta, each index's lots | 0.95 | 3.8 | No cross-index sum |
| DV01, USD/bp | -0.19 | 0.095 | -0.095 |
| Cross-gamma, each index's lots/bp | -0.000095 | -0.00038 | No cross-index sum |

The cleared version has leg marks 2000 and -1000, whole mark 1000, delta equal to
nominal delta, and zero rate risk. Reverse the signed quantity to reverse all
values and risks; reserve costs retain the current absolute-quantity treatment.

Change only the fixed prices to 3.20 and -0.20. The combined fixed price stays
3.00; leg marks become 2850 and -1900 and leg DV01s -0.285 and 0.19. Whole mark
950, DV01 -0.095, deltas and cross-gammas stay unchanged. This proves why leg DV01
is retained attribution while the curve total is the primary rate risk view.

For aggregation, collect this result alongside a single-index A result with
nominal delta 0.5 A lots, delta 0.475 and SOFR DV01 -0.0475 on the same payment
date and exact market/curve objects. Expect A totals 1.5 nominal and 1.425 delta;
B remains 4 nominal and 3.8 delta; SOFR DV01 is -0.1425. Book that A source at
5000 MMBtu and fixed price 3.40 against the same 3.50 market: amount 500 and mark
475, rather than constructing invented result scalars. A
cashflow source on SOFR changes only that rate column. A repeated result occurs
twice, and collection never adds a combined total on top of the leg contributions.

## Lifecycle and regression acceptance

Use a separate synthetic F27 lifecycle: A observes 29 December 2026 at 3.55;
B publishes 4 January 2027 at -0.35. The same fixed prices and quantity apply.
With weekends-only payment holidays, `+2bd` from the later observation pays
6 January 2027. Use the existing fixing cutoff and histories, not a new cutoff.

| State | A amount | B amount | Nominal delta A/B | Value/cash expectation |
|---|---:|---:|---|---|
| 28-Dec, live prices 3.50/-0.40 | 2000 | -1000 | 1 / 4 | Mark is 1000 times that day's payment factor |
| 30-Dec, A fixed, B live at -0.40 | 2500 | -1000 | 0 / 4 | Mark is 1500 times that day's factor; both unpaid legs have DV01 |
| 5-Jan, both fixed | 2500 | -500 | 0 / 0 | Mark is 2000 times that day's factor; DV01 remains |
| 6-Jan, paid | 2500 | -500 | 0 / 0 | Mark/DV01 zero; cash 2000, split 2500/-500 |

Each state uses a curve anchored to its own valuation date. Compute DV01 from
the actual remaining day count and each leg's NPV. Correct A's fixing or move
B's live quote separately; only the appropriate economic contribution changes.
Use `util_BumpDiscountCurve` with positive/negative bumps as an independent
numerical check of analytic DV01 and each index's cross-gamma.
Both schedules retain a later unused contract so the existing market creators
remain usable after the booked exposures have all fixed.

Also pin:

- Both indexes observing on the same date at different prices; their slots and
  fixings stay distinct. Zero total NPV can coexist with nonzero leg values and
  deltas. Fixed-price offsets retain index attribution after grouping into slots.
- A strip with monthly rule payments and a strip deferred to one explicit date;
  multiple rows with different payment dates/calendars/curve keys, no premature
  netting; `month` and `calday`, negative and zero quantities, partial dates under
  the existing period rules, and different supported methods on the two legs.
- Batch equals separately evaluated singleton rows for values and each risk
  group; duplicate rows count twice. Existing single-index results remain equal
  in numbers, reports and readback, including the physical path.
- Index order defines the entered fields; reversing histories/markets does not
  change anything. Reversing indexes with their associated prices/methods
  preserves values/risks but may change first-leg fees.
- Missing second fields, second fields with one index, invalid methods, template
  overlap/unknown headers, incompatible units/currencies, unequal quantity sizes,
  missing months, physical two-leg settlement, bad handle ranges/identities/dates,
  absent fixing/quote/factor coverage and nonfinite arithmetic fail before output.
- Nonzero second-index fee rates have no effect. Broker absent/`none`, bilateral
  clearing, strips, sells, duplicate rows and zero rows keep existing fee rules.

## Engineering boundaries and delivery

Keep the existing creators, handle kinds and valuation stages. Internal common
terms, leg encoding and leg risk ownership are the main work; the handle-range
parser already exists. Update the collector's assumption that one result implies
one index/history/market. Retain the current stale-snapshot and identity checks
for every index contribution, including mixed one-index/two-index collections.

Deliver as three stacked pull requests, each on its own branch targeting the one
before, reviewed and tested apart, and the whole stack put through UAT before any
of it lands: (1) the internal one-leg representation and contribution ownership,
preserving every existing behavior and work count; (2) two-leg resolution,
payment and fee ownership and pricing, with the hand-priced acceptance cases;
(3) the worksheet binding, reports and readback, aggregation, and the workbook,
host, smoke and lifetime coverage. Write each boundary before building it; if the
split would need temporary fallbacks or combined-index adapters, flag that before
building around it rather than adding them.

Measure the one-leg baseline and two-leg case at one and many rows. Creation
counts each leg's observations and encoding, with reserves/shared quantities
owned once. Preparation applies each history once to its relevant observations.
Evaluation reads each distinct live reference per index and each distinct selected
curve/payment-date factor once, reusing that factor across the two leg amounts.
A tick rebuilds no schedule, fixing state, static offset or reserve. Readers make
no numerical reductions; collection works from saved vectors. Report actual
before/after counts and retained/temporary array sizes, rather than inventing
an exact budget in this ticket.

The lifetime checks cover a tick on either market, a correction to either history,
a date roll, a selected curve change, a failed input and recovery, and held older
results/collections. Market and curve ticks reuse preparation; a history change
rebuilds preparation and evaluation without re-encoding trades.

The implementation updates the maintained owners:
[instrument definition](../../library/instruments/show-instrument.md),
[creation](../../library/trades/create-trades.md),
[kernel](../../library/trades/kernel.md),
[preparation](../../library/trades/prepare-trades.md),
[evaluation](../../library/trades/evaluate-trades.md),
[risk reporting](../../library/trades/report-risk.md),
[aggregation](../../library/trades/aggregate-results.md),
[reserves](../../library/trades/report-reserves.md) and
[readback](../../library/utilities/read-handle.md), only where their contracts
change. Add a compact kept-workbook example and matching host/smoke coverage.
Run the repository gate; preserve the source/golden separation rule if goldens
are introduced. Do not rewrite historical tickets as current specifications.

## Outside this slice

Subtraction, a third index, same-index time spreads, per-row index pairs,
separately paying legs and independent leg quantities/routes/curve keys, cross-currency or
differently quoted leg prices, two-index quoting, strategy/grouping selectors,
per-ticket-row valuation reports, selective tick recalculation and margining.

No commercial assumption remains open in this ticket: the common payment is the
agreed v1 rule above. The quantity/quote compatibility limits and the readback
shape are first-slice decisions, not conventions inferred from market data.
