# Expose fixed and live observation values in evaluated-trade readback

**Status:** Agreed 28 October 2026 as issue #228 and built in #229 from main; [evaluate-trades.md](../../library/trades/evaluate-trades.md) is the page, and the records are [prepare-trades.md](../../library/trades/prepare-trades.md)'s and [kernel.md](../../library/trades/kernel.md)'s.

## Outcome

Expose the historical fixings and live projections already used by valuation when calling
`util_ReadHandle` on an `_EvaluateTrades` result.

A desk holding an October COMEX HG Asian swap should be able to inspect each observation's
price and contribution, including the days that have already fixed. This is a visibility
change: preserve and display existing calculation facts, without changing pricing, risk, or
payment behavior.

Here, "fixed" means the already-fixed portion of the floating leg. It does not mean the
trade's agreed `fixed_price`.

## Current gap

The calculation already includes both sides:

- Preparation reads each fixed observation's fixing and calculates its contribution, then
  retains the sums by payment group. The individual fixing prices and contributions are
  discarded.
- Evaluation reads the live quotes and retains the live contributions, but discards the
  gathered quote vector.
- The evaluated readback shows `live_coefficient`, `live_lots`, and `live_contribution`. These
  correctly show zero on fixed observations, leaving the user unable to inspect those
  observations' historical prices or amounts in this readback.

The static coefficient for every observation is already retained in the encoding.

## Requested behavior

Append these columns to the existing evaluated-trades readback:

| Column | Meaning |
| --- | --- |
| `observation_coefficient` | The observation's signed pricing coefficient, whether fixed or live; expressed in the existing sensitivity unit. |
| `observation_price` | The actual historical fixing or live projection used for that observation. |
| `price_unit` | The index's configured quote unit, such as USD/LB or CENT/LB. |
| `floating_contribution` | The observation's already-calculated floating-leg contribution, in settlement currency, before the agreed fixed leg and discounting. |

Preserve all existing columns and their meanings. In particular, the live columns must
continue to show zero once an observation fixes. Append the new columns so existing column
positions stand.

Keep the existing rows and ownership: leg/index, pricing contract, booked contract,
observation date, payment group and discount curve. Do not expand back to individual trades
or combine groups with different payment terms.

## Small worked example

A synthetic copper-style average over four observations, with total quantity 25,000 lb and
quotes configured as USD/LB. This is a short teaching example, not a claim about October's
actual observation calendar.

| Observation | Fixed? | Coefficient | Price used | Floating contribution, USD |
| --- | --- | ---: | ---: | ---: |
| 1 | TRUE | 6,250 | 4.10 | 25,625 |
| 2 | TRUE | 6,250 | 4.20 | 26,250 |
| 3 | FALSE | 6,250 | 4.30 | 26,875 |
| 4 | FALSE | 6,250 | 4.30 | 26,875 |

The floating amount is 105,625 USD. For this simple example it corresponds to 4.225 USD/LB.
At a fixed price of 4.00 USD/LB, the value before discounting is 5,625 USD while unpaid.

The feature exposes the observation facts; it does not introduce a new averaged-price
calculation.

## Implementation boundaries

- Retain the fixed prices and per-observation contributions already produced during
  preparation. Evaluated results reach them through their existing preparation reference.
- Retain the live quotes already gathered during evaluation, preferably by distinct live
  reference. Live contributions are already retained.
- Keep retained arrays immutable. Do not copy the fixed information again on every tick.
- The reader only selects and formats saved data. It must not reread fixings, call the market
  for prices, or repeat pricing multiplication.
- Do not reconstruct a price by dividing contribution by coefficient: zero quantities and
  perfectly netted exposures are valid, and the actual source price must remain visible.
- Keep existing finiteness checks and failure behavior.
- Record the retained-memory change and readback work. No additional fixing reads or pricing
  multiplications are required by this change.

## Acceptance

- Hand-check mixed fixed/live observations, all live, all fixed but unpaid, and paid.
  Historical contributions remain inspectable after payment; they are not presented as
  remaining NPV.
- Verify a quote tick changes only the live prices/contributions and reuses the fixed arrays.
  A corrected history supplies a new preparation and the corrected fixed facts.
- Verify zero and offsetting exposures retain their actual prices without division by zero.
- Preserve existing single- and two-index behavior, multiple payment dates/curves, and Asians
  whose pricing reference changes during the period.
- Existing mark, cash, delta, DV01 and cross-gamma remain unchanged.
- Update the affected readback tests, work/memory budgets, host facts, smoke and kept-workbook
  spills. Check the wider spills do not overlap adjacent cells.
- Update the owning readback/record documentation and UAT note. Run the full repository gate.

## Scope

One focused PR. No new worksheet function or signature, no new pricing methodology, no
prepared-readback expansion, and no quote/RFQ or aggregate-result changes.

Defer group-level "fixed share" and blended-price summaries. Signed, mixed-schedule batches
can have zero net quantity but nonzero fixed/live value, so a universally meaningful group
average is a separate question.

## As built

The owner's two decisions, 28 October: `price_unit` is spelled as the quote currency over the
quote quantity unit, `USD/LB`, `USD/MMBTU`, `CENT/GAL`, and the four columns are appended at
the end of the readback, after `discount_curve`, so that a one-index result spills 30 columns
where it spilled 26 and a pair 38 where it spilled 34.

Retained where the kernel reads them, each array frozen and shared by every tick:

- `PreparedLeg.settle[k]`, the settle the preparation reads for its k-th fixed slot, in slot
  order and aligned with the fixed slots alone, eight bytes a fixed slot; and
  `PreparedLeg.fixed_contribution[s]`, each slot's exposure times its settle where it has fixed
  and zero where it is live, eight bytes a slot, the array the set amounts were already summed
  from, handed back by `_the_set_amounts` beside the sums instead of dropped.
- `LegResults.quote[q]`, the quote the evaluation reads for the preparation's q-th live
  reference, eight bytes a live reference, the array `_the_contributions` already gathered
  onto the live slots, handed back beside the contributions.

The reader, `_observation_facts` in `excel/utilities.py`, places them: the coefficient is the
encoding's `slot_exposure`; the price is the settle scattered onto the fixed slots and the
quote gathered onto the live ones by the preparation's `reference_of_live_slot`; the unit is the
leg's conventions' words; the contribution is the preparation's fixed contributions with the
evaluation's live ones in the live slots' places. No fixing or quote is read again, nothing is
multiplied and nothing is divided.

The work: the preparation freezes two arrays more, `ndarray.setflags` 21 where it was 19, and
every tick one more, 2 where it was 1 on the cleared path and 20 where it was 19 on the
bilateral one; no other count, peak or byte pin moved. The readback's call profile holds no
fixing, quote, preparation or product.

Tests: `tests/unit/test_observation_prices.py`, the copper example through its states, the
tick, the corrected fixing, exposures of nothing, the crossed expiry and the bilateral path;
the pair's leg rows in `tests/unit/test_two_index.py`; the NG example's four columns in
`tests/unit/test_trade_valuation.py`; the bytes and the readback's profile in
`tests/performance/test_trade_budgets.py`; the host's payment-groups fact, the smoke's KA14 and
WJ24 pins and the kept workbook's nine results spills, grown by four columns with every other
cell as it was.
