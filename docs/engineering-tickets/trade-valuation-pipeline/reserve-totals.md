# Brokerage and clearing reserve totals

[Pipeline overview](README.md) · [UAT item 8](surface-uat-notes.md#8-clearing-brokerage-and-marketing-reserves)

**Since #NN:** `marketing_reserve` is a field of the `fixed_float`, booked once per ticket row, [booking-fields-and-marketing-reserve.md](booking-fields-and-marketing-reserve.md); the zero marketing below is this slice as built.

**Status:** Built in #170 on the prototype stack above #169, the page as a ticket; the
[As built](#as-built-170) section at the end says what was built and what was not. Ready
for engineering, 9 October 2026. Inspected baseline: prototype PR #168 at `d1633d7`. One
focused PR on its current successor. Marketing reserve inputs and calculations are deferred
until after bilateral valuation.

## Outcome

Calculate the batch's booked brokerage and clearing reserves once during trade creation,
retain the totals on evaluated results, and expose them through `_ReportReserves`.
Always include marketing in the output as zero for this slice, with no marketing field
required in a template or ticket.

Reserves are positive cost amounts in the index's settlement currency. They do not
affect mark, cash, delta, DV01 or the existing value and risk reports. They are static
booked amounts, not a balance that runs off with fixing, expiry or payment.

## Calculation

Use each component's resolved count of its selected entry specification, after the
existing `month` or `calday` quantity calculation, before exposure netting:

```text
spec[k] = the entry specification selected by component k's trade occurrence
q[k]    = abs(resolved component_quantity[k])

brokerage[k] = q[k] * specifications.brokerage_rate_per_lot[spec[k]]
clearing[k]  = q[k] * specifications.clearing_rate_per_lot[spec[k]]

brokerage_reserve = sum(brokerage)
clearing_reserve  = sum(clearing)
marketing_reserve = 0
currency = index.conventions.currency_unit
```

Here a specification's "lot" means one count of that specification row. A row named
`BBL`, with size 1 BBL, has rates per barrel; a row named `LOT`, with size 1000 BBL,
has rates per thousand-barrel lot. Use the selected row's rates directly. Do not
multiply by its lot size again or convert through the risk-reporting lot, price
coefficient or quote currency. The rates are already in settlement currency.

Count every occurrence, including repeated trade IDs and identical trades. A buy and
sell can cancel exposure while both incur reserves. A strip contributes once per
monthly component, not once per ticket and not once per pricing observation. Zero
quantity contributes zero. Use the rates as supplied; do not infer a missing rate,
reconcile different specification rows' rates or substitute a rate from another row.

Preserve existing quantity rules: `month` counts the entered quantity for each covered
month, including a partial month; `calday` multiplies by the component's inclusive
covered calendar days. No additional proration, observation weighting or rounding.

Refuse nonfinite component amounts and nonfinite batch totals at creation, before a
trade handle is published. Name the reserve category and original trade row for a
component failure. A zero-quantity row must not hide an invalid nonfinite rate through
a shortcut. Keep the current nonnegative specification-rate rules.

## Worked example

Illustrative specifications for one USD-settled index:

| Specification | Size | Brokerage per specification lot | Clearing per specification lot |
|---|---|---:|---:|
| LOT | 1000 BBL | 10.00 | 4.00 |
| BBL | 1 BBL | 0.01 | 0.004 |

All trades below cover one month with `quantity_per = month`:

| Trade | Quantity | Specification | Brokerage | Clearing |
|---|---:|---|---:|---:|
| 101 | 2 | LOT | 20 | 8 |
| 102 | -2 | LOT | 20 | 8 |
| 103 | 1000 | BBL | 10 | 4 |
| 104 | 0 | LOT | 0 | 0 |
| **Batch** | | | **50** | **20** |

The first two trades net to zero exposure and still reserve 40 brokerage and 16 clearing.
One LOT and 1000 BBL reserve the same amounts here because the supplied rates agree on
that basis. Marketing is zero throughout.

## Pipeline and reader

Create the immutable reserve summary in the static creation/encoding path, using the
resolved quantities and specification selection already available. Preparation retains
access to it. Evaluation carries the summary into `TradeResults` without traversing
trades or repeating the sums. Internal record layout is engineering's choice; no new
creator argument, preparation stage or handle kind is required.

```text
_ReportReserves(results) -> mixed table
```

One required trade-results handle; the normal handle validation applies. Spill the
saved scalars in the existing report style: headers, types and one values row:

| brokerage_reserve | clearing_reserve | marketing_reserve | currency |
|---|---|---|---|
| float64 | float64 | float64 | str |
| 50 | 20 | 0 | USD |

The reader only formats stored values. It performs no aggregation, pricing, fixing or
market access. Expose the summary once in result debug readback as well, without
repeating these batch totals on each dated slot. Existing report layouts remain intact.

Keep current pipeline refusals, including unsupported bilateral valuation and expired
physical positions. This feature does not make an otherwise invalid result publishable.

## Acceptance and delivery

- Pin the worked example through creation, evaluation and the reader. Singletons sum
  to the batch; row reordering preserves totals and duplicate occurrences add again.
- Pin mixed entry specifications, zero quantities and zero rates. Changing only the
  reporting-lot selection or pricing-observation count does not change reserves when
  booked quantities and rates remain the same.
- For the example's BBL rates, a `X26-Z26` strip of 2 BBL per calendar day counts
  `2 * (30 + 31) = 122` BBL: brokerage 1.22 and clearing 0.488. A partial-month
  Asian of 1000 BBL on the `month` basis still reserves 10 and 4.
- Price ticks, fixing corrections and valuation dates before/after financial payment
  leave reserve totals unchanged for the same created batch. Recreating trades with
  changed quantities or specification rates updates them. Existing value/risk answers
  remain unchanged.
- Test nonfinite component amounts and sum overflow; no partial handle is published.
  Pin work at creation and no reserve recomputation at preparation, evaluation or reading.
- Update Excel registration/help, report and pipeline documentation, result inspection,
  host replay, smoke and the kept workbook example. Run the full gate, update affected
  work/allocation budgets, and keep existing golden changes separately reviewed.

No nonzero marketing reserve, reserve release schedule, fee payment lifecycle, reserve
discounting, rate lookup by broker/clearing-house name, per-trade report or cross-index
aggregation is included. Marketing follows bilateral as a separate ticket.

## As built, #170

Engineering's record of what landed, in the ticket's terms.
[report-reserves.md](../../library/trades/report-reserves.md) is the page.

- **The record.** `Reserves` in `src/goosedove/trades/reserves.py` holds the batch's
  `brokerage`, `clearing`, `marketing` and `currency`, the conventions' `currency_unit`.
  `encoded` makes it once, when `_CreateTrades` makes the batch: each component's count is its
  component quantity without its sign, after the `month` or `calday` rule, and its rates are its
  occurrence's selected specification's, as given, with no lot size, coefficient or quote unit
  applied; the amounts are summed per category and not kept. Marketing is 0.0, no field
  entering it. The preparation reaches the record through its encoding, and `TradeResults`
  holds the same object by reference: nothing sums again.
- **Refusals.** At creation, before any handle is published, brokerage before clearing: an
  amount that is not finite, `brokerage reserve of trade 101 at row 1 is inf, expected a finite
  amount of USD; 2.0 of 'LOT' at 1e+308 a lot`, naming the category, the trade and its row, the
  count, the specification and the rate, a zero count included, since nought times an infinite
  rate is not a number; and a total past the largest number, `the batch has inf of brokerage
  reserve in all, expected a finite amount of USD; the components' reserves, each finite, sum
  past the largest number`. The specifications' rule of zero or more is unchanged. A sheet cell
  holds no NaN or infinity and takes no number above 9.99999999999999E+307 typed, so on a sheet
  only the overflow reaches these rules.
- **Reader.** `_ReportReserves(results)` in `src/goosedove/excel/trades.py`: one required
  results handle, validated by the seam; headers `brokerage_reserve`, `clearing_reserve`,
  `marketing_reserve`, `currency`, types `float64` three times and `str`, and one row of the
  stored values, formatted and nothing else. Its help: `Reports the batch's reserves from its
  results, as creation stored them: brokerage and clearing, each trade's monthly quantity
  without its sign times its specification's rates per lot, summed, marketing at zero until
  built, and their currency.`
- **Result inspection.** `util_ReadHandle(results)` ends with the same four columns: the values
  on the first slot row and a dash, `-`, in all four on every later row, since the totals are
  the batch's and no slot's and the seam's way out has no blank cell. The trades readback is
  unchanged: the UAT notes moved the reserve view off the trade handle onto evaluated results.
- **Counts.** The creator's ledger gains one call, `reserves`, and one counter entry,
  `reserved_components`, one per component; preparation, evaluation and the other reports run
  nothing new. `_ReportReserves` resolves one handle and lays out one row of three numbers and
  a text, with no day.
- **On a sheet.** The smoke's block in OR1:OW30, the host's fact and the kept workbook's rows
  1848 to 1881 carry the worked example. Every results readback in the kept workbook widens
  by four columns; B1355's would have spilled into the toy's fixings in O, so `TAKE` keeps it
  to its twelve.
- **Not built.** No nonzero marketing, reserve release schedule, fee payment lifecycle,
  discounting, rate lookup by broker or clearing-house name, per-trade report or cross-index
  aggregation, as the ticket bounds it.
