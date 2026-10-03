# NG creation and preparation: independent acceptance example

[Pipeline overview](README.md) · [Creation](create-trade.md) ·
[Preparation](03-market-binding.md) · [Existing average example](worked-example.md)

Design fixture, 3 October 2026. This specifies expected economics and intermediate data
before implementing the general creators. It is not a saved production-library golden.
All trade inputs, static fixture facts and independent expected answers are specified below;
the proposed `_CreateTrades` and `_PrepareTrades` are not yet implemented.

## What this example proves

Start with the NYMEX NG trade rows and static index facts in this document. A repeated
occurrence makes accidental deduplication visible. First establish signed quantities, the entry-price
contribution, and compression against each contract's own quoted price. Then use an explicitly
fictional cash-settled product to specify history and payment transitions without assigning
invented payment terms to the physically deliverable NG contract.

The initial NG calculation is undiscounted entry-to-current economic P&L for open futures.
It does not model margin transfers, delivery obligations, a payment date, or post-expiry cash.
This restricted economic fixture is not a complete proposed production ticket: the final
instrument schema's payment terms still require supported, product-appropriate facts.

## Static facts and where they come from

| Fact | Source | Fixture value |
|---|---|---|
| Instrument | Library definition; selected first when creating a template | `future` |
| Index | Static `Index` reference | Fixture label `Henry Hub NYMEX`; futures schedule kind |
| Quote conventions | `index.conventions` | Quote currency `USD`, quote quantity `MMBTU`, amount currency `USD`, quantity type `ENERGY`, quantity unit `MMBTU` |
| Selected specification | Name within `index.specifications` | `NYMEX NG` |
| Lot size | Selected specification row | 10,000 MMBTU per lot |
| Contract identity | `index.schedule` | `Z26`, `F27` |
| Specification fee inputs | Selected specification row | Brokerage and clearing rates both `0` per lot; no fees valued in this example |
| Static schedule | `index.schedule` | `Z26` expires `2026-11-25`; `F27` expires `2026-12-29`; no option expiry array |
| Pricing calendar | `index.holiday_calendar` | Fixture holidays `2026-11-26`, `2026-12-25` |
| Contract positions in this static fixture | Static schedule lookup | `0`, `1` |
| Agreed price | Executed trade row | Values below |

The schedule dates and pricing holidays above are illustrative fixture inputs, not
independent evidence of exchange dates. The instrument definition
does not duplicate quote conventions or lot sizes. Creation selects the named specification
from the explicit index, validates compatibility, and retains the static references used.
Changing the row order of specifications must not change which named specification is used.

These examples use logical inputs instead of freezing the unresolved worksheet placement of
the index or instrument selection on the no-template path. The template parameter remains
optional and last on `CreateTrades`; it is not silently made mandatory here.

## Template facts and trade rows are disjoint

For the static NG portion, the shared supplied facts are `contract_specification = NYMEX NG`,
`quantity_unit = LOT`, and `quantity_per = month`. The index is an explicit static reference.
The template is bound to `future` when created. Other completed production terms must come
from the supported definition and supplied fields; this illustrative subset does not waive them.

The row headings are `trade_id`, `trade_date`, `contract_code`, `quantity`, and `fixed_price`:

| Occurrence | trade_id | trade_date | contract_code | quantity | fixed_price |
|---:|---|---|---|---:|---:|
| 0 | NG-001 | 2026-09-24 | Z26 | 10 | 3.100 |
| 1 | NG-002 | 2026-09-24 | Z26 | -4 | 3.150 |
| 2 | NG-003 | 2026-09-25 | F27 | 7 | 3.400 |
| 3 | NG-004 | 2026-09-25 | F27 | -12 | 3.350 |
| 4 | NG-001 | 2026-09-24 | Z26 | 10 | 3.100 |

Occurrence is internal row identity, not an additional worksheet input. Rows 0 and 4 both
count even though every supplied value is identical. `trade_id` is not a uniqueness key.
The ticket fields use the proposed instrument definition's `quantity` and `fixed_price`.

Any intersection between the template's supplied field names and row headers fails, even
when the values agree. For example, adding `quantity_unit = LOT` to these rows fails because
the template already supplies it. Duplicate headers within either input fail before a
dictionary or merge can discard one. Explicit blank cells fail; omission means absence of
the field, not a blank override. Field duplication and repeated trade occurrences are different
conditions: the former is invalid, the latter is preserved.

Every header must also exactly match the selected future definition. For example,
Fixed_Price, a padded fixed_price, or an undeclared desk_note column fails. Worksheet notes
can sit outside the supplied field/value ranges; they are not retained in the trade object.

## Creation: resolved terms become static arrays

For this fixture, every lot is 10,000 MMBTU and every row contains one monthly contract.
Each occurrence contributes `signed_quantity * (contract_price - fixed_price)` USD.
For futures, call the static subtraction an `entry_price_offset`; it is not a swap's fixed
leg or a claim that the entry amount was paid in cash.

```text
occurrence                  = [0, 1, 2, 3, 4]             # intp, shape (5,)
input_of_component          = [0, 0, 1, 1, 0]             # intp, shape (5,)
signed_lots                 = [10, -4, 7, -12, 10]       # float64
signed_quantity_mmbtu       = [100000, -40000, 70000, -120000, 100000]
entry_price_offset_usd      = [-310000, 126000, -238000, 402000, -310000]

market_inputs = [
    (retained_NG_index, "Z26", "own_contract_mark", "USD/MMBTU"),
    (retained_NG_index, "F27", "own_contract_mark", "USD/MMBTU"),
]
```

Arrays are owned or safely shared, immutable, and one dimensional where shown. Those local
input positions address the retained input list, not a future shortened price vector.
Changing as-of, history, or prices does not rebuild these static arrays.

The explanatory dense matrix has five occurrences and two contract inputs:

| Occurrence | Z26 coefficient | F27 coefficient | Entry-price offset, USD |
|---:|---:|---:|---:|
| 0 | 100,000 | 0 | -310,000 |
| 1 | -40,000 | 0 | 126,000 |
| 2 | 0 | 70,000 | -238,000 |
| 3 | 0 | -120,000 | 402,000 |
| 4 | 100,000 | 0 | -310,000 |
| Sum | 160,000 | -50,000 | -330,000 |

No production allocation of this dense matrix is required. The original occurrences remain
inspectable; compression does not erase source quantities, dates, or payment facts.

## Preparation and independent initial values

For an open-contract state before both fixture expiry dates, no required final contract
price has fixed. Preparation produces:

```text
history_fixed_input         = [False, False]
live_axis                   = [NG Z26 own-contract mark, NG F27 own-contract mark]
live_exposure_mmbtu          = [160000, -50000]
historical_price_amount_usd  = 0
entry_price_offset_usd       = -330000
```

Futures history before expiry does not fix a fraction of a bullet contract's exposure.
Each live input here is the current price of that actual contract. It is not a forecast
of remaining daily assessments or a final monthly average reconstructed from prints.

Supply the ordered live vector `[3.200, 3.500]` USD/MMBTU. The independent checks are:

| Occurrence | Hand calculation, USD | P&L, USD |
|---:|---|---:|
| 0 | `10 * 10000 * (3.200 - 3.100)` | 10,000 |
| 1 | `-4 * 10000 * (3.200 - 3.150)` | -2,000 |
| 2 | `7 * 10000 * (3.500 - 3.400)` | 7,000 |
| 3 | `-12 * 10000 * (3.500 - 3.350)` | -18,000 |
| 4 | `10 * 10000 * (3.200 - 3.100)` | 10,000 |
| Total | Sum of the five hand answers | 7,000 |

The compressed answer is independently `160000 * 3.200 - 50000 * 3.500 - 330000 = 7000`.
Amount delta is `[160000, -50000]` USD per one USD/MMBTU move, equivalently the corresponding
signed MMBTU exposures. A one-cent Z26 move changes P&L by USD 1,600; a one-cent F27 move
changes it by USD -500. These are neither lot counts nor percentage-price sensitivities.
This fixture does not establish a rate-risk convention or a DV01 output.

Two numerical tests are important: the five-row batch equals the sum of five singleton
calls, and deleting occurrence 4 decreases value by USD 10,000 and Z26 delta by 100,000.
The first four rows above alone therefore produce USD -3,000 at these marks.

### Existing market integration needs a wider static schedule

The current futures calendar uses its first scheduled contract only as its left boundary:
it starts on the day after that contract expires. Consequently, the two-contract static
fixture cannot also serve as a history fixture exposing Z26. Prepend an independently
reviewed preceding-contract row before using it in the actual calendar/market path.
Retain a later contract if testing fully fixed traded contracts within a still-live history.
This changes the static schedule positions, so assertions must resolve identities rather
than assuming every NG index uses positions `[0, 1]`.

Current `PriceVector` provides positional values and an index name. The product adapter
must establish the ordered live contract axis and its compatibility with preparation.
Two equal-length vectors with different contract order are not interchangeable. Do not
claim the current object can detect incorrectly labeled raw spreadsheet prices without
additional source identity. No dummy live contract or dummy quote may hide a terminal state.

## Explicit toy lifecycle: fixings are different from payments

Use a separate, approved test-only cash-settled future definition called `TOY_GAS` to exercise
these states. It has the same USD/MMBTU convention, 10,000 MMBTU lot size, five trade quantities,
entry prices, and Z26/F27 labels as above. It is not ICE, NYMEX NG, or a real payment convention.
Its single final price per monthly component is independently supplied, not inferred from a
daily average. Clearing identity `TEST_CLEARER` and `settlement_method = financial` are fixture
facts; no exchange metadata is implied.

Its library-owned product definition anchors payments to the following test last-trading dates.
The template supplies `payment_time_lag = "+2bd"` and a test payment calendar with Monday-Friday
business days excluding 26 November, 25 December 2026, and 1 January 2027. These inputs are disjoint
from the row headers. Payment dates are computed once, strictly after the anchor:

| Component | Test last trading date | Counted payment business days | Encoded payment date |
|---|---|---|---|
| Z26 | 2026-11-25 | 27 November, 30 November | 2026-11-30 |
| F27 | 2026-12-29 | 30 December, 31 December | 2026-12-31 |

For this test definition only, a final observation is required when its date is strictly
before as-of. It stays live on that date, matching the current futures calendar's daily cutoff.
If the required final price is absent, preparation fails. Final prices in the following rows
are fixture inputs, not externally sourced exchange values.

These final prices are only the observations consumed by this toy trade adapter, not a
complete input table for today's MarketHistory. Its futures-history constructor requires
all fixed, priced daily rows in the supplied calendar. An end-to-end fixture must provide
that complete history and select the final observations from their matched rows; it must
not pass these two sparse contract prints as though they were the entire history.

All five occurrences retain their payment groups. Group arrays in static contract order are:

```text
group_contract                   = [Z26, F27]
component_to_group               = [0, 0, 1, 1, 0]
group_entry_price_offset_usd      = [-494000, 164000]
group_original_exposure_mmbtu     = [160000, -50000]
group_payment_date               = [2026-11-30, 2026-12-31]
```

These dates group compatible components; they do not permit dropping payment identity before
cash classification. With no discounting, group amount is its entry-price offset plus its
historical-price amount plus its live-price amount. A fixed price can contribute to an unpaid
amount. A payment is classified as modeled cash when `payment_date <= as_of` and the required
final price is present, under the pipeline's proposed inclusive cutoff.

| State | As-of | Required historical final prices | Ordered live axis / coefficients | Group historical-price amounts, USD | Modeled mark, USD | Modeled cash, USD | Total P&L, USD |
|---|---|---|---|---|---:|---:|---:|
| Initial | 2026-11-24 | none | `[Z26, F27] / [160000, -50000]`, prices `[3.20, 3.50]` | `[0, 0]` | 7,000 | 0 | 7,000 |
| Price tick, same history | 2026-11-24 | none | Same coefficients, prices `[3.21, 3.50]` | `[0, 0]` | 8,600 | 0 | 8,600 |
| Z26 now fixed, unpaid | 2026-11-26 | Z26 = 3.22 | `[F27] / [-50000]`, price `[3.50]` | `[515200, 0]` | 10,200 | 0 | 10,200 |
| Correct Z26 fixing, same as-of | 2026-11-26 | Z26 = 3.23 | `[F27] / [-50000]`, price `[3.50]` | `[516800, 0]` | 11,800 | 0 | 11,800 |
| Z26 payment date | 2026-11-30 | Z26 = 3.23 | `[F27] / [-50000]`, price `[3.50]` | `[516800, 0]` | -11,000 | 22,800 | 11,800 |
| Both fixed; F27 unpaid | 2026-12-30 | Z26 = 3.23; F27 = 3.45 | `[] / []` | `[516800, -172500]` | -8,500 | 22,800 | 14,300 |
| Both payment dates reached | 2026-12-31 | Z26 = 3.23; F27 = 3.45 | `[] / []` | `[516800, -172500]` | 0 | 14,300 | 14,300 |

Check the later group amounts directly: Z26 is `160000 * 3.23 - 494000 = 22800`;
F27 is `-50000 * 3.45 + 164000 = -8500`. Historical final-price corrections do not carry
live forward-price delta. The full original-contract delta axis is `[0, -50000]` once Z26
has fixed and `[0, 0]` when both have fixed, even though the compressed live axis shrinks.
Retain the input mapping if readers present the original axis with zero entries.

For the three Z26 occurrences at final price 3.23, singleton amounts are `[13000, -3200, 13000]`,
totaling 22,800. For F27 at 3.45, they are `[3500, -12000]`, totaling -8,500. These checks also
show why equal and opposite live exposures do not justify discarding entry-price offsets.
Modeled cash is cumulative economic P&L assigned to settled fixture components. It is not an
assertion that these amounts are the actual final clearing transfers or a cash reconciliation.

## Work boundaries and acceptance

| Event | Work that must occur | Work that must not occur |
|---|---|---|
| Create five rows | Validate disjoint fields; resolve five occurrences/two input identities; encode static coefficients and applicable payment dates | Read history, build a market, or use live prices |
| Prepare first state | Bind input identities; prepare payment classification; aggregate compatible exposures | Reinterpret trade text or reconstruct static schedules |
| Price-only tick | Check compatible history/layout; consume aligned live prices; evaluate aggregate arrays | Re-resolve, re-encode, gather/fold fixings, or re-sum five trades |
| Fixing correction or date roll | Prepare afresh from original encoding and the complete new history | Mutate/append onto an old prepared amount or reuse stale payment classification |
| Read result | Read the stored aggregate result and supported metadata | Reprice or reconstruct individual trade values |

Count consumed trade inputs as two unique live marks in the initial fixture, one after Z26
fixes, and zero after both fix. Count distinct required final contract prices as zero, one,
and two respectively. These are logical work targets for the trade adapter; do not disguise
whole-history traversal or unrelated market-construction work by reporting only the targets.
Whether independent market creation does more work is measured separately. Instrument the
real boundaries before asserting exact low-level allocation or lookup counts.

Engineering acceptance also includes zero live exposure with fixed amounts remaining;
offsetting quantities with different entry prices; fixing absence; wrong source/units;
incompatible history; and payment-cutoff equality. An entirely fixed `MarketHistory` needs
an explicit integration solution because the current `Market` constructor requires an
unfixed period. The numerical empty-vector case above is valid but does not claim that
constructor gap is already solved. A still-live history containing no live exposure from
this batch is a separate, immediately testable case.

The [Excel binding proposal](excel-trade-input-binding.md) sets out the partial-field
transport and a proposed terminal market extension. Neither is implemented by this fixture.

Validate hand expectations independently before snapshotting production outputs. A small
arithmetic script can check these numbers, but its outputs are not production-library goldens.
Keep fixture inputs and expected answers under review; a batch/singleton equality test alone
cannot detect a shared incorrect lot size, schedule, price identity, or payment convention.
Use explicit tolerances for float64 USD amounts and sensitivities. Register reviewed snapshots
only after the production path exists, following the
[golden validation plan](../ethane-golden-validation-harness.md).
