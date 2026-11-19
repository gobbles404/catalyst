# A float_float's spread price in its own unit, and the cracks

**Status:** Agreed with the owner, 19 November 2026, for
[issue #239](https://github.com/gobbles404/catalyst/issues/239). One pull request stacked on
#252, this page in its first commit. It is the second slice of two, above
[float-float-spread.md](float-float-spread.md): a `float_float` on two indexes that price in
different units, a crack, with the spread price's unit typed. It changes nothing a
`fixed_float` books, values or reads back, one index or two.
[kernel.md](../../library/trades/kernel.md), [create-trades.md](../../library/trades/create-trades.md),
[trade-template.md](../../library/trades/trade-template.md),
[show-instrument.md](../../library/instruments/show-instrument.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the owners it updates.

## The issue

A crack is one product less another at one agreed spread price: gasoline less crude, RB less
WTI. RB is priced in dollars a gallon and WTI in dollars a barrel, and the spread price is
agreed in dollars a barrel. The first slice books a `float_float` on two indexes that price
in one unit and refuses any other pair, so nothing books a crack. And nothing says what unit
a spread price is in: on a same-unit pair it is taken to be the indexes'.

## Decisions of 19 November 2026

| Decision | Agreed |
|---|---|
| The spread price's unit | Typed, never taken from an index: explicit over implicit. |
| Its form | Two codes, as an index's conventions are typed: `spread_price_currency_unit`, USD or CENT, and `spread_price_quantity_unit`, a unit of what the two indexes measure, BBL say. |
| Required | On every `float_float`, a same-unit pair included: a gas spread types USD and MMBTU. Every `float_float` template of the first slice gains the two fields. |
| The quantity | One rule for every pair, the one a pair follows today: the ticket's `quantity_unit` names a specification on each index and the two are one amount. Where the legs price in different units the two are compared after conversion. A `LOT` of 42,000 GAL on one index and of 1,000 BBL on the other is one amount and passes. No new field. |
| Refused | Two indexes that measure different things, a volume against an energy. Electricity against heat, a megawatt hour against an MMBtu. A ratio between the legs is no field and is not built. |
| Delivery | One pull request stacked on #252. |

## What converts

The payoff stands, `Q * (A - B - spread_price)`, now with each price in its own unit. No
price is converted. Each leg's quantity is restated in its own index's price unit, as it is
on one index today, where a price in dollars a gallon already takes a quantity in barrels at
42 gallons each. The spread price is given the same quantity restated in its own unit. The
issue words this as each leg's price converted to the spread's unit; the dollars are the
same, and nothing new is done to a price when a quote moves.

1,000 BBL of RB less WTI, RB at 2.10 USD a gallon, WTI at 70.00 USD a barrel, at a spread
price of 15.00 USD a barrel:

```text
RB leg        42,000 GAL * 2.10    =   88,200
WTI leg       -1,000 BBL * 70.00   =  -70,000
spread leg    -1,000 BBL * 15.00   =  -15,000
payment                            =    3,200
```

## Booking and worksheet contract

The function names and argument positions stand. The template names the spread price's
unit:

| Field | On a `float_float` |
|---|---|
| `spread_price_currency_unit` | Required. The currency unit the spread price is in, `USD` or `CENT`, a code of the unit tables as typed. |
| `spread_price_quantity_unit` | Required. The quantity unit the spread price is per, a unit of the measure the two indexes share: `GAL`, `BBL`, `L` or `M3` for VOLUME, and so on. |
| `spread_price` | As it is, now in that unit: 15.00 with USD and BBL is fifteen dollars a barrel. |
| `quantity_unit` | As it is: a specification name both indexes define, one amount on both. |

The two follow `spread_price` in the definition's order. Each is one for the batch, as the
route is: the template's value, or a ticket column every row agrees on, never both. Neither
is a field of a `fixed_float`, which refuses them as it refuses any unknown header.

A crack's template and ticket, with RB's index handle given first and WTI's second:

| spread_price_currency_unit | spread_price_quantity_unit |
|---|---|
| USD | BBL |

| trade_id | trade_date | contract_code | quantity | quantity_unit | spread_price |
|---|---|---|---:|---|---:|
| 12345 | 2026-11-19 | G27 | 1000 | BBL | 15.00 |

The pair's rules on a `float_float`, where the first slice held it to one unit:

- **The measure.** The two indexes have one quantity type, VOLUME, MASS or ENERGY.
- **The settlement.** The two indexes settle in one currency unit, the payment's.
- **The price units.** Each leg's quote currency unit and quote quantity unit are its own.
  The two legs' may differ from each other and from the spread price's.
- **Heat and electricity.** Of the ENERGY units, MWH and KWH are electricity and MMBTU, BTU,
  THERM and GJ are heat. The three quantity units, the two legs' and the spread price's, are
  all of one or all of the other. A megawatt hour is 3.412 MMBtu as energy, and a spread of
  power against fuel is struck at a heat rate, a ratio between the legs, which is not built.
- **The quantity.** Each row's `quantity_unit` is one amount on both indexes, the two sizes
  restated in the spread price's quantity unit and agreeing to the roundoff of their
  conversions.

Everything else of a `float_float` stands as the first slice left it: two distinct indexes,
bilateral, no broker, financially settled, monthly, nearby 1, a method per leg on its own
index's days, one net payment.

The refusals this slice adds or rewords, in the words the build pins:

| Entered | Refused as |
|---|---|
| No `spread_price_quantity_unit` | `spread_price_quantity_unit is missing, expected a value in the template or a column in the ticket` |
| A currency unit the tables lack | `spread_price_currency_unit is 'EUR', expected USD or CENT` |
| A quantity unit of another measure | `spread_price_quantity_unit is 'MMBTU', expected a VOLUME unit, GAL, BBL, L or M3` |
| Two values down a ticket column | `spread_price_quantity_unit row 2 is 'GAL', expected 'BBL' as at row 1; a batch has one spread_price_quantity_unit` |
| Two indexes of two measures | `index 2 'HH' measures ENERGY, expected VOLUME as index 1 'C3'; a spread across two measures needs a density or a heat content, which the unit tables do not carry` |
| Two indexes settling in two units | `index 2 'B' settles in CENT, expected USD as index 1 'A'; a spread is one payment in one currency unit` |
| Electricity against heat | `index 2 'HH' quotes per MMBTU and index 1 'PJM' per MWH, expected two units of heat or two of electricity; a spread of power against fuel is struck at a heat rate, a ratio between the legs, which is not built` |
| The spread price per MWH on two indexes of heat | `spread_price_quantity_unit is 'MWH', expected a unit of heat as the two indexes quote in, MMBTU, BTU, THERM or GJ` |
| A `quantity_unit` of two amounts | `quantity_unit 'LOT' of trade 12345 at row 1 is 1000.0 BBL on index 'RB' and 500.0 BBL on index 'WTI', expected one quantity per entered unit on both legs` |

The first slice's refusal that two legs' prices net in one unit goes; the three rows above
that name index 2 stand where it stood. A two-index `fixed_float` keeps its own, that two
legs' prices add in one unit.

## Calculation and retained state

For each monthly component, with Q the component's quantity and `word` the specification its
`quantity_unit` names:

```text
quantity_first  = Q * size of word on the first index, in the first index's quote quantity unit
quantity_second = Q * size of word on the second index, in the second index's
quantity_spread = Q * size of word on the first index, in the spread price's quantity unit

floating_first  =  quantity_first  * price_first    in the settlement currency
floating_second = -quantity_second * price_second
spread_leg      = -quantity_spread * spread_price
payment_amount  = spread_leg + floating_first + floating_second
```

Each product is scaled once from its own currency unit to the settlement currency unit, a
price in cents a gallon times 0.01 on an index that settles in dollars. The first two lines
and the floating amounts are the first slice's, each leg's arithmetic as on one index. The
third line is new: the first slice made the spread leg from the first leg's quantity, which
is the same number, to the last bit, when the spread price's unit is the first index's.

Everything is made once, at creation. The factors are read from the unit tables once for
each distinct `quantity_unit` of the batch, never per row and never on a tick. The NPV, the
DV01, the compensated sum of the payment's signed terms, each leg's set and live amounts,
its nominal delta in its own reporting lot, its delta and its cross gamma are the first
slice's with no change.

The created trades hold the spread price's two units beside the spread price. No leg holds
a converted price, and the floating spread in the spread price's unit, 18.20 in the example,
is not kept: it is each leg's price times the factor from its unit to the spread's, a
reader's arithmetic.

## Risk and readback

Ownership is the first slice's. Each index reports in its own reporting lot, so a crack's
two deltas are in two units and never summed: one lot of 42,000 GAL of RB, minus one lot of
1,000 BBL of WTI. The DV01 is the net payment's.

`_ShowInstrument("float_float")` lists the two fields after `spread_price`. The template's
readback shows them. The created-trades readback shows them on every row beside
`spread_price`; its `quote_quantity` and `coefficient` are each leg's in its own units, as
they are, and `offset` is the spread leg. The results readback already names each
observation's price unit, `USD/GAL` on one leg's rows and `USD/BBL` on the other's.

## Hand-priced acceptance

**RB less WTI.** A bought crack, every observation live. RB quoted in USD per GAL with a
reporting lot of 42,000 GAL; WTI in USD per BBL with a reporting lot of 1,000 BBL; both
defining `BBL`, one barrel. Valued 4 January 2027, G27, paying 4 January 2028 at a SOFR
factor of 0.95. Quantity 1,000 of `BBL`, spread price 15.00 USD per BBL, live prices 2.10
and 70.00:

| Measure | RB | WTI | Whole trade |
|---|---:|---:|---:|
| Spread price | none | none | 15.00 USD/BBL, entered |
| Quote quantity | 42,000 GAL | -1,000 BBL | none |
| Floating price | 2.10 USD/GAL | 70.00 USD/BBL | none kept |
| Floating contribution | 88,200 | -70,000 | none |
| Spread leg | none | none | -15,000 |
| Undiscounted payment | none | none | 3,200 |
| Mark | none | none | 3,040 |
| Nominal delta, each index's lots | 1 | -1 | no cross-index sum |
| Delta, each index's lots | 0.95 | -0.95 | no cross-index sum |
| DV01, USD per basis point | none | none | -0.304 |
| Cross gamma, each index's lots per basis point | -0.000095 | 0.000095 | no cross-index sum |

Times the factor the three amounts are 83,790, -66,500 and -14,250, which sum to 3,040, a
test's arithmetic over the readback as in the first slice.

The same trade entered other ways reads the same numbers:

- quantity 1 of `LOT`, where RB's `LOT` is 42,000 GAL and WTI's is 1,000 BBL;
- the spread price 1,500 with CENT and BBL.

A spread price of 21.00 with USD and BBL and one of 0.50 with USD and GAL are one trade,
paying -2,800. Sell the crack, quantity -1,000: payment -3,200, mark -3,040, deltas -1 and
1, DV01 0.304. Heating oil less WTI is this example under another index name and takes no
numbers of its own.

**C5 natural gasoline less WTI.** C5 quoted in CENT per GAL and settled in USD, WTI as
above. 1,000 of `BBL` bought at a spread price of -9.10 USD per BBL:

| C5 | WTI | C5 leg | WTI leg | Spread leg | Payment |
|---:|---:|---:|---:|---:|---:|
| 145 | 70.00 | 60,900 | -70,000 | 9,100 | 0 |
| 145 | 69.00 | 60,900 | -69,000 | 9,100 | 1,000 |

The C5 leg is 42,000 GAL at 145 cents at 0.01 dollars a cent.

**Averages.** A crack is the average of each leg over the month, each on its own index's
pricing days, which the first slice already prices: both legs `asian`, each day's prompt
contract under nearby 1. The build books a month in which one index prices a day the other
does not and pins that each leg's slots carry its own day count's share, that C5 averaging
145 and WTI averaging 70.00 pay zero at -9.10, that WTI averaging 69.00 pays 1,000, and
that a fixing on a day one leg alone prices moves that leg alone.

**The lifecycle.** Two futures indexes whose contracts fix on different days, A per GAL
with a lot of 42,000 GAL and B per BBL with a lot of 1,000 BBL. A less B, 1,000 of `BBL` at
a spread price of 15.00 USD per BBL:

| State | Payment amount | Nominal delta A / B |
|---|---:|---|
| Both live, at 2.10 and 71.00 | 2,200 | 1 / -1 |
| A fixed at 2.00, B live at 71.00 | -2,000 | 0 / -1 |
| Both fixed, B at 70.00 | -1,000 | 0 / 0 |
| Paid | cash -1,000, one amount | 0 / 0 |

Correct A's fixing to 2.05 and the payment is 1,100.

**Aggregation.** The RB crack beside a `fixed_float` on WTI alone, 2,000 BBL bought at
69.00, on the same payment and curve, WTI live at 70.00. RB totals 1 nominal and 0.95
delta, WTI 1 and 0.95, the SOFR DV01 -0.494. The membership rows:

| position | index | reporting_lot | nominal_delta | delta | dv01 | cross_gamma |
|---|---|---|---:|---:|---:|---:|
| 1 | RB-WTI | - | - | - | -0.304 | - |
| 1 | RB | LOT | 1 | 0.95 | - | -0.000095 |
| 1 | WTI | LOT | -1 | -0.95 | - | 0.000095 |
| 2 | WTI | LOT | 2 | 1.9 | -0.19 | -0.00019 |

**The first slice's pair.** Every number of
[float-float-spread.md](float-float-spread.md) stands, to the last bit, with USD and MMBTU
typed on its template. Its synthetic spread at a spread price of 10 with CENT and MMBTU
pays the same 500 and marks the same 475.

Also pin: every refusal in the table above; the two unit fields supplied by the template,
by a ticket column and by both; a strip, calday and a zero row on a crack; the two indexes
given in the other order with the quantity and the spread price both negated; a spread
price unit that is neither leg's. Every existing `fixed_float` test, one index and two,
passes unchanged.

## Desk inputs still to come

Asked for on the issue; the build does not wait for them:

- **The references.** The exact index each leg of the desk's cracks prices on and its roll,
  the C5 assessment and the crude reference above all.
- **The quantity.** Whether the desk enters a crack in barrels or in lots of one leg. Both
  book under the rule above where the specifications define them.
- **Rounding.** Whether a confirmation rounds a leg's average or the spread. Nothing here
  rounds.
- **Mixed methods.** Whether a deal with a different method on each leg is needed on day
  one. The pair takes a method per leg today.

They decide the indexes the kept workbook books a real crack on and its numbers.

## Engineering boundaries and delivery

One pull request stacked on #252, this page and its index rows in the first commit, the
build in the next. Inside it, in order: the definition, the two fields after `spread_price`;
the resolution, which reads each as the batch's one; the terms, the pair's rules by
instrument, a `float_float`'s measure, settlement and heat-or-electricity rules where the
one-unit rule stood, and the record's two units; the encoding, the spread leg's quantity in
its own unit and the quantity rule compared there; the readbacks; then every `float_float`
template of the first slice, in the tests, the host fact, the smoke block, the lifetime
group and the kept workbook, which gains its two cells; the crack's tests, a host fact, a
smoke block and a block of the kept workbook on two indexes made for it; the pages above, a
history row and UAT item 36. No stage after creation is expected to change, and the tests
say so.

A `float_float` template without the two fields is refused by name from this pull request
on, with no default and no reading of the indexes in their place.

Measure before and after. A `fixed_float`'s work counts, numpy ledgers and allocation pins
stand, one index and two. A `float_float` is expected to do the first slice's work at every
step, with one addition at creation: the unit factors of the spread price, a handful for
the batch whatever its row count. On a tick nothing is added: 2 live prices read, 1 curve
selected, 1 payment factor read, 1 group valued, 2 slots discounted and 2 weighted and 20
risk reductions. The pull request states the counts it measured.

## Outside this slice

A unit for the price of a two-index `fixed_float`, whose legs still share one. A ratio
between the legs: a heat rate, a 3:2:1, a density that would carry a spread from a mass to
a volume. A floating spread kept or read back in the spread price's unit. Rounding.

Outside both slices, as the first lists them: cleared or brokered spreads, a batch whose
rows each name their own two indexes, two separately executed swaps settled apart, physical
delivery, more than one currency, legs in different months, three-leg baskets, options, a
synthetic joint index, new data retrieval, and a quote or a request for quote on a spread.
