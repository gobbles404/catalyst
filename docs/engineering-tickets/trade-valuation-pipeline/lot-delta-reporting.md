# Report trade delta in index-defined lots

[Pipeline overview](README.md) · [Running UAT notes](surface-uat-notes.md) ·
[Mixed trade fields](mixed-trade-fields.md) ·
[Bilateral planning](bilateral-discounting-and-dv01.md)

**Status:** Built in #164 on the prototype stack above #163, the page as a ticket; the
[As built](#as-built-nn) section at the end says what was built and what was not. Written
8 October 2026, following Excel UAT of the prototype through PR #163, reviewed at
`14130240`. Reporting delta in lots and designating a reporting specification per index are
agreed. The concrete index-creator argument below is the recommended implementation, and
the one built.

**Suggested PR title:** `feat(trades): report delta in index-defined lots`

## Problem and outcome

The current `delta_total` is monetary sensitivity to a move of one quoted price unit.
The owner expects delta in lots. These quantities can have very different numbers:
one ETE lot of 1,000 BBL is 42,000 GAL; with CENT/GAL quotes and USD settlement its
current sensitivity is 420 USD per one-cent/gallon move. Its fully live lot delta is 1.
With USD/BBL quotes, the sensitivity is 1,000, coincidentally equal to the barrel
quantity. That coincidence made the distinction less apparent in WTI and Brent UAT.

Expose **signed remaining exposure in lots of the index's designated specification**.
Preserve the monetary coefficients used by valuation, the monetary sensitivity vector,
and the existing mark/cash economics. One trade and many use the same path. This is a
reporting and risk-representation change, not an alteration of prices, quantities,
observation weights or payment amounts.

Initial scope is the supported cleared linear path. Existing bilateral evaluation
remains refused until its own implementation and risk conventions are ready.

## One reporting lot per index

Every specification already has a `lot_size` and `lot_unit`. Those fields describe
the quantity represented by one entry unit of that specification:

| Specification name | `lot_size` | `lot_unit` | Meaning of entered quantity 1 |
|---|---:|---|---|
| LOT | 1000 | BBL | 1,000 barrels |
| BBL | 1 | BBL | One barrel |
| GAL | 1 | GAL | One gallon |

Add an explicit selection of **one existing specification name** as the index's
reporting lot. In this example select `LOT`. The name is an identifier, not a new
unit in the global conversion tables. A differently named row, such as `NYMEX`, is
equally valid when explicitly selected.

The recommended worksheet signature is:

```text
_CreateIndex(
    name, schedule, index_conventions, contract_specifications,
    [holiday_calendar], [reporting_lot]
)
```

`reporting_lot` is an optional final text argument, naming a row in the supplied
contract specifications. This optionality serves indices used only to build/read
markets; they do not need a reporting-lot definition. It is not an automatic default.

- When supplied, match the specification name exactly at index creation and retain
  its resolved selection and lot conversion facts. Unknown names fail there.
- An omitted selection remains explicitly unset. A blank is not omission and keeps
  the seam's existing failure behavior.
- `_CreateTrades` requires a designated reporting lot before numerical encoding,
  because every supported evaluation must produce a complete risk result. Refuse
  an unset selection there; do not publish a trade that fails only when its risk is read.
- Do not infer the selection from the index name, exchange, clearing house, schedule
  method, first specification row, a literal `LOT` name, or a trade's quantity-unit choice.
- The reporting specification need not appear among the specifications selected by
  the batch's entry rows. A BBL-only ticket can still report against `LOT`.
- Define the lot once on the index. Keep the specifications table's existing size/unit
  columns; no repeated reporting-lot fields on its rows, templates or tickets are needed.

Use the existing unit tables and index/specification compatibility rules. Validate
newly derived reporting-lot quantities and divisors as finite and strictly positive;
overflow must not turn an exposure into zero or NaN. Resolve and convert once, with
no specification search or conversion lookup during preparation, ticks or reporting.

The selection describes **equivalent reporting lots**, not necessarily how many exchange
contracts the trader entered. For example, with a 10,000-MMBTU reporting lot, a position
entered using a 2,500-MMBTU specification is 0.25 reporting lots. Changing the reporting
lot to 2,500 MMBTU makes the same position 1 reporting lot. Neither changes its economics.

## Normalization and retained state

For the designated specification, resolve once:

```text
reporting_lot_quote_quantity =
    lot_size * quantity_conversion(lot_unit -> index.quote_quantity_unit)

reporting_lot_price_coefficient =
    reporting_lot_quote_quantity
    * currency_conversion(index.quote_currency_unit -> index.currency_unit)
```

The coefficient means settlement-currency P&L per one quoted price-unit move for a
fully live reporting lot. For ETE quoted in CENT/GAL and settled in USD it is 420.
For the same physical lot quoted in USD/GAL it is 42,000; in USD/BBL it is 1,000.

On the existing stable contract axis, for the current cleared model:

```text
lot_delta[r] = monetary_price_sensitivity[r] / reporting_lot_price_coefficient
lot_delta_total = sum(lot_delta)
```

Use the unique retained contract vector, not a sum of debugging spill rows. If a
dated lot-exposure view is retained, apply the same normalization to each existing
live slot. Fixed slots contribute zero; dates and payment-group ownership stay intact.

Do not divide by the physical lot size alone: that misses quantity-unit and currency
scaling. Do not substitute lot delta for the coefficients that multiply current prices,
fixings or fixed prices. In particular, multiplying a CENT/GAL quote by `1` instead of
`420` would change the economics by the wrong factor.

Prepare the lot-delta vector and its total alongside the existing history-dependent
risk. Retain the monetary price-sensitivity vector under an unambiguous name. Share
immutable prepared risk with results; a commodity tick changes neither vector in this
cleared linear model. A history/as-of change updates which observation weights remain
live and therefore updates both. Signed and fractional deltas are valid and unrounded.

For an Asian, one fully live reporting lot has lot delta 1. Once half of its total
observation weight has fixed, lot delta is 0.5. Count the remaining **weights**, not
calendar days unless those weights actually implement calendar-day weighting. A fully
fixed but unpaid amount can still have mark, while its commodity lot delta is zero.

## Reporting and inspection

`_ReportRisk(results)` retains its scalar report shape:

- `delta_total` now reports the stored lot-delta total.
- `delta_unit` identifies lots of the designated reporting specification, including
  enough context to read the basis, for example `LOT (1000 BBL; specification LOT)`.
- DV01, its units and as-of keep their current supported meaning. This ticket does
  not implement bilateral rate risk.

Retain the lot-delta vector by contract in the result. Keep the monetary sensitivity
available with its own units for diagnostics and later valuation work. Do not use one
field name to mean monetary sensitivity in one record and lot delta in another without
making that boundary explicit in code and documentation.

`util_ReadHandle` should make the following inspectable:

| Object | Required facts |
|---|---|
| Index | Designated specification, lot size/unit and resolved normalization facts, or explicit absence for a market-only index |
| Prepared trades | Dated remaining exposure in reporting lots alongside clearly identified monetary pricing coefficients |
| Results | Contract lot delta and monetary sensitivity with their units and reporting basis |

Store dated lot exposures during preparation if required by the prepared/result spills;
the readers should not perform risk conversion or reconstruct risk from trade rows.
Existing slot-level `live_exposure` is a monetary pricing coefficient. Rename or label
that meaning clearly when adding the lot view; do not simply label its old value as LOT.

The current debug `contract_delta` repeats a contract total on each observation row.
If that layout remains, identify its unit as reporting lots and keep the repeated-total
meaning explicit. The scalar comes from the stored unique contract vector, never by
summing this repeated column. Readers access no current prices or fixing data.

Each batch remains one index with one reporting basis. Do not silently combine lot
counts from different indices or reporting definitions into a universal exposure total.

## Independent acceptance cases

Use the public creators, preparation, evaluation and reports for the main ETE example.
Assume positive quantities, one month, all observations live, CENT/GAL quotes, USD
settlement, and a designated reporting specification of 1,000 BBL:

| Trade entry or collection | Physical quantity | Monetary price sensitivity | Reported lot delta |
|---|---:|---:|---:|
| 1 LOT | 1000 BBL | 420 USD per CENT/GAL | 1 |
| 1000 BBL | 1000 BBL | 420 USD per CENT/GAL | 1 |
| 42000 GAL | 1000 BBL | 420 USD per CENT/GAL | 1 |
| All three positive rows in one batch | 3000 BBL | 1260 USD per CENT/GAL | 3 |
| Equivalent three-row partial Asian fixture, two of four equally weighted observations still live | 1500 BBL of remaining equivalent exposure | 630 USD per CENT/GAL | 1.5 |

For the last row, use a synthetic partial Asian period of 14–17 December 2026 with
four weekday observations and valuation date 16 December. The two earlier observations
have fixed and the other two remain live. Each entered monthly quantity applies to that
partial component under the existing quantity rule; this is not a four-day full-month
exchange averaging convention.

For the fully live ETE rows, fixed price 25 and live price 28 CENT/GAL give mark
1,260 USD per equivalent trade and 3,780 USD for all three together, with zero cash.
Changing the delta presentation must preserve those independently priced amounts.

Further coverage should establish:

- **Quote and settlement units:** restate the same ETE economics in CENT/GAL,
  USD/GAL, USD/BBL and CENT/BBL. One lot's monetary coefficients are respectively
  420, 42,000, 1,000 and 10 with USD settlement; lot delta is 1 throughout.
  Convert all price inputs consistently when comparing valuation. Include settlement
  in CENT as well to catch a hidden USD-only normalization.
- **Reporting basis:** explicitly select a specification that is not the first row,
  not named `LOT`, and absent from the batch's entry selections. With a 10,000-MMBTU
  reporting lot, 10,000 MMBTU reports 1 and 2,500 MMBTU reports 0.25. Changing only the
  reporting lot to 2,500 MMBTU scales the first result to 4 and the second to 1,
  leaving mark, cash and monetary sensitivity unchanged.
- **Schedules and quantity basis:** fully live `lastday`, `penultimate`, `last3day`
  and `asian` positions with equivalent total quantity report the same lot delta.
  For a 1,000-BBL reporting lot, 20 BBL/calday across five covered calendar days
  reports 0.1 while all observations are live, regardless of how many pricing days
  lie in that period: 16–20 December 2026 supplies five covered days but three weekday
  observations under a weekday-only calendar. One lot/month over a two-month strip gives vector `[1, 1]`
  and total 2.
- **Lifecycle:** retain the existing observation-day fixing cutoff. Partial fixing
  removes exactly the applicable observation weights; fully fixed unpaid groups have
  zero lot delta, and paid groups stay zero. Include mixed methods and payment dates.
- **Aggregation:** negatives keep their sign, fractional reporting lots remain
  fractional, valid zero rows contribute zero, duplicates count, and reordered batches
  equal the aligned sum of singleton vectors and totals. Stored totals equal the sum
  of the unique contract vector, not duplicated readback rows.
- **Failures:** unknown reporting name, supplied blank, missing selection at trade
  creation and unusable derived normalization fail at their owning boundary. A
  market-only index with no selection still supports the existing market path.
- **Economics and work:** independent hand-priced mark/cash expectations stay unchanged.
  Conversions occur once at index creation; normalized risk is prepared once per history.
  Ticks share that risk, read each distinct live quote once, and do no lot conversion,
  trade/schedule expansion or fixing fold. Readers only spill stored values. Old results
  keep their original basis and arrays when a new index/preparation is built.

Use existing example/property/work-budget patterns and stated numerical tolerances.
Do not generate the expected lot answers from the normalization helper being tested.

## Delivery and boundaries

Deliver one focused prototype PR with the index selection, normalized risk, surface
readbacks and their tests together. The likely touch points are index definitions and
their Excel creator, trade creation's index compatibility check, preparation/results,
the risk report and debugging spills. Keep numerical operations vectorized; no per-trade
valuation path, extra market read or persistent cache is required.

Update affected index fixtures, workbook formulas, smoke/host assertions, help and
current pipeline/library pages. Cut over the report semantics and explain them in the
PR; no legacy monetary interpretation hidden behind the same unit label. Follow the
repository's separate-review rule for existing golden updates. Run `check.ps1`, report
before/after work counts and the additional retained risk-array memory.

This ticket does not change `trade_id`, instrument entry units, specification fees,
unit-conversion definitions, fixing history or settlement rules. It does not require
every market-only index to have an exchange lot.

The bilateral ticket must separately settle how reported lots relate to discounted
monetary sensitivity. Dividing discounted NPV sensitivity by the above coefficient
produces PV-weighted equivalent lots; that is not automatically nominal remaining
volume. Preserve both meanings and resolve their presentation before enabling bilateral
evaluation. This ticket leaves that bilateral reporting choice open.

## As built, #164

Engineering's record of what landed, in the ticket's terms.
[index.md](../../library/index-definitions/index.md),
[report-risk.md](../../library/trades/report-risk.md),
[prepare-trades.md](../../library/trades/prepare-trades.md),
[evaluate-trades.md](../../library/trades/evaluate-trades.md) and
[kernel.md](../../library/trades/kernel.md) are the pages.

- **The reporting lot.** `_CreateIndex` takes the recommended sixth argument, `reporting_lot`,
  optional text in the seam's decision 39 form: the name of one of the specifications, matched
  exactly, resolved once when the index is made into the kernel's `ReportingLot`, the row, its size
  and unit, the lot in the quote quantity unit, `lot_size * factor(lot_unit -> quote_quantity_unit)`,
  and the coefficient, that quantity times the currency factor, the settlement currency a fully live
  lot makes per unit of quote price, 420 for a thousand barrels quoted in cents a gallon and settled
  in dollars, 42,000 in dollars a gallon, 1,000 in dollars a barrel, 10 in cents a barrel and
  42,000 in cents a gallon settled in cents; both finite, else refused, `reporting_lot 'LOT' is inf
  GAL a lot, expected a finite quantity; the lot size outruns the largest number`. A name the
  specifications lack is refused naming them, `reporting_lot is 'LOT', expected one of the
  specifications: 'lots', 'gal'`; left out, the index has none and builds markets as before; a blank
  is the seam's refusal. Nothing is inferred from the index's name, the first row, a literal LOT or
  the rows' units, and the specifications table is unchanged.
- **The kernel.** `resolved_trades` refuses an index without a lot, as the resolution does before any
  row is read, `index 'ETHANE' has no reporting_lot, expected one of its specifications named when
  the index was made; a batch's delta is reported in lots of it`, and the terms carry the lot. The
  preparation forms `price_sensitivity` by reference, the monetary vector under its own name, and
  `lot_delta`, the sensitivity over the lot's coefficient, with `lot_delta_total`, and
  `dated_live_lots` by slot, one division each, the coefficient the index's; the monetary `delta` and
  `delta_total` are gone from both records, so a stale reader fails rather than reads lots as dollars
  or dollars as lots. The results hold both vectors with their units, `price_sensitivity_unit`,
  `USD per CENT/GAL`, and `lot_unit`, `lots of LOT (1000 BBL)`; a tick shares all of them and makes
  none again. Every live lot, every lot delta and their total are finite before anything is
  published, else the preparation refuses the first that is not by its slot, then by its contract,
  then for the batch, `trade 'H' at row 1 observes Z26 on 2026-11-25 with inf live lots, expected a
  finite number of lots of BTU (1 BTU); the exposure in lots outruns the largest number`: a BTU lot
  against 10^303 MMBTU keeps a finite sensitivity, 10^301 dollars a cent, and divides it past the
  largest number in lots, and two contracts of 10^302 MMBTU each keep finite lots, 10^308 apiece,
  that sum past it.
- **The surface.** `_ReportRisk` keeps its five columns: `delta_total` is the lot total and
  `delta_unit` the lot's words. `util_ReadHandle` on an index adds `reporting_lot` and, with a lot
  named, `lot_size`, `lot_unit`, `lot_quote_quantity` and `lot_coefficient`, or the word `unset`; on
  prepared trades `live_coefficient`, the column `live_exposure` was, and `live_lots`; on results
  `live_coefficient`, `live_lots`, `live_contribution`, `contract_sensitivity` and
  `contract_lot_delta`, the two contract columns the stored vectors read by each slot's reference
  and so the same number on every slot of the contract, then `sensitivity_unit` and `lot_unit`,
  the two units those numbers are in, the batch's on every row so that a row reads whole, the
  readers converting nothing. The trades spill and the templates are as #163 left them.
- **The numbers pinned.** The ticket's ETE rows, a lot, a thousand barrels and 42,000 gallons, each
  1,260 of mark, 420 of sensitivity and one lot, three together 3,780, 1,260 and three; the partial
  Asian period of 14 to 17 December valued on the 16th with the 14th at 26 and the 15th at 27,
  2,835 of mark, 630 of sensitivity and 1.5 lots; the five quote and settlement units, one lot
  each; 10,000 and 2,500 MMBTU one and a quarter NYMEX lot, four and one ICE lot, the mark and the
  sensitivity unchanged; every method fully live one lot, a strip `[1, 1]`, twenty barrels a day
  over 16 to 20 December a tenth; the lots gone once fixed and after payment; signed, fractional,
  additive, reordered, duplicated and kept rows as the ticket lists. Every fixture names its lot and
  every pinned delta of the earlier tickets is restated in lots by hand: 110,000 dollars per dollar
  an MMBTU reads 11 lots of NYMEX NG, the pen's 5,000 two ICE lots, the smoke's 2,000 two
  thousand-barrel lots, the lifetime's two barrels 0.002 of one. The same through the seam, on the
  host, in the smoke and in the kept workbook, whose risk cells now read lots.
- **The work.** The preparation's numpy ledger freezes two arrays more, `ndarray.setflags` 8 to 10,
  looks twice more, `ndarray.any` 1 to 3 and `ufunc.reduce` 5 to 7, whether the lots and the lot
  delta are finite, and sets the error state once, `numpy._make_extobj`, the overflow the rule's to
  catch; its functions are unchanged; the resolution's ledger has `reporting_lot_of` twice, the
  resolution's check and the kernel's; the seam validates six declared arguments for
  `_CreateIndex`, `_validate` 5 to 6, the lot left out validated as missing; the tick's ledger is
  unchanged, reading each distinct live quote once and converting nothing. Memory: eight bytes a
  slot and eight a contract more retained, the daily batch of 360 slots preparing at 33,964 bytes,
  30,972 before, the pin 90 to 98 bytes a slot with the reason beside it, the two-day and mixed
  batches under the same ceiling; the index record one reference larger.
- **After review.** The owner's review at 55e2734 found two P3s and a cleanup, fixed on the branch.
  The results spill showed `contract_sensitivity` without the unit it is in, so equal ETE positions
  quoted in cents and in dollars a gallon read 420 and 42,000 under one heading: it ends with
  `sensitivity_unit` and `lot_unit` on every row. A finite sensitivity could divide to an infinite
  lot delta and be published, the risk reader failing after: the preparation refuses it first, by
  the slot and by the contract, the fourth rule above, and, a second look finding the total
  unguarded, two finite contract deltas summing past the largest number, for the batch, the sum
  formed and checked before the record is made. The pipeline's 05-results.md and 06-readers.md
  said monetary sensitivity where the reported delta is lots; they distinguish the two now.
- **Not in this slice.** No bilateral lot reporting: how reported lots relate to a discounted
  sensitivity is left to the bilateral ticket, as this one says; no DV01 beyond zero; no exposure
  total across indices; the trades spill, the templates and the specifications table unchanged;
  the older tickets' as-built records keep the monetary deltas they were written with.
