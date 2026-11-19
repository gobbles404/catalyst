# A float_float swap on two indexes at one spread price

**Status:** Agreed with the owner, 18 November 2026, for
[issue #239](https://github.com/gobbles404/catalyst/issues/239). One pull request from
main, this page in its first commit. It is the first slice of two: a pair of indexes quoted
in one unit. It adds an instrument beside the two-index `fixed_float` of
[two-index-one-price.md](two-index-one-price.md), built in #242, and changes nothing a
`fixed_float` books, values or reads back.
[kernel.md](../../library/trades/kernel.md), [create-trades.md](../../library/trades/create-trades.md),
[evaluate-trades.md](../../library/trades/evaluate-trades.md),
[report-risk.md](../../library/trades/report-risk.md),
[aggregate-results.md](../../library/trades/aggregate-results.md),
[trade-template.md](../../library/trades/trade-template.md),
[list-instruments.md](../../library/instruments/list-instruments.md),
[show-instrument.md](../../library/instruments/show-instrument.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the owners it updates.

## The issue

The system of record books a float-for-float swap on two indexes at one agreed spread price;
the trade found is NTO against PAN. The library books a pair of indexes one way today, as a
`fixed_float` paying the sum of the two against one outright price. Nothing books the
difference of two indexes against a spread.

## Decisions of 18 November 2026

| Decision | Agreed |
|---|---|
| The booking | Two indexes and one agreed spread price, the system of record's form. Not one named differential with fixings of its own. |
| The instrument | A new one, `float_float`, with its own price field, `spread_price`. The two-index `fixed_float` stays as it is, so no instrument means two payoffs behind a flag. |
| The name | The handle reads as a difference, `NTO-PAN`, the legs' index names joined by `-` in leg order. |
| The batch | One pair of indexes per batch. A sold spread is a negative quantity in the same batch, never a second batch. Each index's history and market are made once and shared by every batch naming the index. |
| The fields | The fields of a `fixed_float`, with `spread_price` where `fixed_price` stood and `second_schedule_method` always required. What this slice does not build is refused by name: a cleared route, a named broker, a physical settlement, a onetime period, a nearby above 1 and one index. |
| The other instrument's price | `spread_price` on a `fixed_float` and `fixed_price` on a `float_float` are refused as any unknown header is, by the cell and with the instrument's own fields listed. No message of their own. |
| Leg values | No leg keeps an amount, an NPV or a DV01, as #242 decided for the pair. The issue's three contributions to NPV are checked in a test from the slot readback and the payment's factor. |
| Delivery | Slices. This one, a same-unit pair, is one pull request; unit conversion and the cracks are a second slice above it. |

## The payoff

```text
two-index fixed_float:   Q * (A + B - fixed_price)
float_float:             Q * (A - B - spread_price)
```

Q is the signed quantity, A and B each leg's floating price for the month, and
`spread_price` the one agreed number. A positive quantity buys the spread: it receives the
first index and pays the second index and the spread price. A negative quantity reverses the
whole trade. The spread price may be positive, zero or negative and must be finite. It is a
constant of the contract and never a market price.

The first index is the one given first to `_CreateTrades`, as the first leg of a pair is
today.

## Booking and worksheet contract

The three function names and argument positions stand: `_CreateTrades(indexes, fields,
trade_rows, template)`, `_PrepareTrades(trades, histories)` and `_EvaluateTrades(prepared,
markets, discount_curve_set)`, the index, history and market cells in leg order. The template
names the instrument:

```excel
=_CreateTradeTemplate("float_float", TemplateHeaders, TemplateValues)
=_CreateTrades(B2:B3, TicketHeaders, TicketRows, TemplateHandle)
```

With NTO's index handle in B2 and PAN's in B3, a ticket row:

| trade_id | trade_date | contract_code | quantity | spread_price |
|---|---|---|---:|---:|
| 12345 | 2026-11-18 | F27 | 10000 | 0.10 |

and the cell shows a handle such as `30512:trades:NTO-PAN:41`.

The `float_float` definition, each field as on a `fixed_float` unless the table says
otherwise:

| Field | On a `float_float` |
|---|---|
| `spread_price` | Required. The spread price agreed, a finite number of either sign or zero in the quote unit the two indexes share, the same for every month of a strip. |
| `fixed_price` | No field of the instrument. |
| `quantity` | As it is. A positive quantity receives the first index and pays the second and the spread price. |
| `schedule_method` | The first index's method. |
| `second_schedule_method` | Always required: the second index's method under its own kind. |
| `route` | `bilateral`. `cleared` is refused by name. |
| `clearing_house` | Listed, and refused with any value, since its condition, a cleared route, never holds. |
| `broker` | Left out, or `none`. A named broker is refused by name. |
| `settlement_method` | `financial`. `physical` is refused, the pair's rule. |
| `settlement_frequency` | `monthly`. `onetime` is refused, the pair's rule. |
| `nearby` | `1`. A later nearby is refused, the pair's rule. |

No field of a `float_float` is one a quote may hold, so a quote template on it is refused by
the rule that refuses one on a `cashflow`. Fields may be supplied in the template or the
ticket, never both, as before.

Everything else of a pair's entry stands: two distinct indexes of distinct names; the same
quote currency, quote quantity and settlement currency units; one quantity per entered unit
on both indexes; each row's months resolved against each schedule; each leg observing by its
own method on its own index's days, so two legs that fix on different days are within this
slice; the payment day found from the later of the two legs' last observations; the first
leg's specification supplying the fees, which are zero here.

The refusals this slice adds, in the words the build pins:

| Entered | Refused as |
|---|---|
| One index with a `float_float` template | `indexes are 1, expected two with a float_float; a spread is the first index's price less the second's` |
| `route = cleared` | `route is 'cleared', expected 'bilateral' on a float_float; a cleared spread is not built` |
| A named broker | `broker of trade 12345 at row 1 is 'ICAP', expected none on a float_float; a brokered spread is not built` |
| `fixed_price` in the template or the ticket | `fields cell (1, 5) is text 'fixed_price', expected a field of float_float: trade_id, ...` |
| `spread_price` on a `fixed_float` | `fields cell (1, 5) is text 'spread_price', expected a field of fixed_float: trade_id, ...` |
| A spread price that is not finite | `spread_price of trade 12345 at row 1 is inf, expected a finite price` |
| A template of another instrument | `template is of instrument 'cashflow', expected fixed_float or float_float, the instruments whose trades are built` |

The pair's own refusals stand in their words. One says the two legs' prices add in one unit;
on a `float_float` it says they net in one unit. Where a refusal names the price or the
trade's own side of the payment, a `float_float` reads `spread_price` and `spread leg` where
a `fixed_float` reads `fixed_price` and `fixed leg`.

## Calculation and retained state

For each monthly component, after quantity conversion and observation weighting, with Q the
common quantity in the shared quote unit and S the spread price:

```text
spread_leg = -Q * S                         the trade's, booked once per component
floating_first = Q * price_first            the leg's: fixed slots at their settles, live slots at their quotes
floating_second = -Q * price_second
payment_amount = spread_leg + floating_first + floating_second
```

For an unpaid payment with its selected factor DF and
`tau = calendar_days(as_of, payment_date) / 365`:

```text
NPV = payment_amount * DF
DV01 = -tau * NPV / 10000
```

The second leg takes its sign once, at creation: its quote quantity and its coefficient are
the first leg's negated, and every number made from them afterwards carries the sign with no
step of its own. Its exposures, its set amounts as observations fix, its live amounts, its
nominal delta, its lots and its cross gamma are the arithmetic a pair runs today. Nothing
about sign is worked out when a history or a quote moves.

The payment is its signed terms summed with compensation, the spread leg and each leg's set
and live amounts kept apart until the one sum, as #242's review left it. Two prices far
larger than their difference is the ordinary case of a spread, so the build pins it: one
MMBtu, both indexes at 1e16 and a spread price of -1, paying 1.

Ownership is the pair's, the spread leg where the fixed leg stood; the implementation
chooses record names:

| Record | Shared state, the trade's | Per-leg state |
|---|---|---|
| Created trades | Rows, periods, quantities, the spread price and the spread leg per component and per payment group, payment dates and keys, reserves | Index, method, observations, signed quote quantities and coefficients, slots and exposures |
| Prepared trades | Valuation date, settled groups, cash and unsettled totals, rate-date preparation | Exact history, fixed slots and their settles, set amounts, live exposures, nominal delta and lots on the index's axes |
| Evaluated trades | Payment amount, NPV, DV01 and factor per group, mark, cash, DV01 by curve, reserves | Exact market, live contributions and quotes, delta, discounted lots, cross gamma by curve |

A leg retains no price, no amount, no NPV, no DV01, no mark and no cash.

## Risk and readback

| Result | Owner |
|---|---|
| Mark and cash | The net payment, counted once |
| Nominal delta and delta | Each original index, in its own reporting lot, the second index's of the opposite sign |
| DV01 | The net payment's curve and currency, counted once, no share per leg |
| Cross gamma | Each original index against the curve |
| The spread price | Value and DV01 only; no commodity risk |

`cross_gamma` keeps the library's meaning: a delta's sensitivity to a one basis point move in
the discount curve. It is no derivative of one index against the other, which is zero for
this payoff.

`_ReportRisk` reads a `float_float` in a pair's layout: the deltas one column per index in
its lot, the DV01 one column per curve and currency, the cross gamma one column per index
and curve, by day, month or year.

`_AggregateResults` groups it as a pair: each leg with its own index's group, the payment
with its curve's. Collected with ordinary positions the spread nets on each original index
and on the curve, no total counted twice and no joint index made. On the membership
readback its own row is named by its descriptor, `NTO-PAN`, and carries the DV01, and a row
per leg carries that index's deltas and cross gamma.

The created-trades readback shows `spread_price` where a `fixed_float` shows `fixed_price`,
and `offset`, the spread leg, once. The prepared and results readbacks keep their columns;
the second leg's exposures, coefficients and floating contributions read with their sign.

`_ReportReserves` reads zero brokerage and zero clearing, and the marketing and CVA reserves
as entered.

## Hand-priced acceptance

A synthetic bought spread, every observation live. Two indexes named NTO and PAN for the
handle's sake, each with a reporting lot of 2,500 MMBtu, the example's assumption. Valued
4 January 2027, G27, paying 4 January 2028 at a SOFR factor of 0.95. Quantity 10,000 MMBtu,
spread price 0.10, live prices -0.25 and -0.40:

| Measure | NTO | PAN | Whole trade |
|---|---:|---:|---:|
| Spread price | none | none | 0.10, entered |
| Floating price | -0.25 | -0.40 | 0.15, the first less the second |
| Undiscounted payment | none | none | 500 |
| Mark | none | none | 475 |
| Nominal delta, each index's lots | 4 | -4 | no cross-index sum |
| Delta, each index's lots | 3.8 | -3.8 | no cross-index sum |
| DV01, USD per basis point | none | none | -0.0475 |
| Cross gamma, each index's lots per basis point | -0.00038 | 0.00038 | no cross-index sum |

Read back slot by slot, the floating contributions are -2,500 on NTO and 4,000 on PAN and
the spread leg -1,000; times the factor they are -2,375, 3,800 and -950, which sum to 475.
That is a test's arithmetic over the readback, not a number a leg keeps.

Change the spread price alone: at 0.00 the payment is 1,500, the mark 1,425 and the DV01
-0.1425; at -0.10 they are 2,500, 2,375 and -0.2375. Every delta and cross gamma stands.
Sell the spread, quantity -10,000 at 0.10: payment -500, mark -475, DV01 0.0475, deltas -4
and 4 nominal and -3.8 and 3.8, cross gammas 0.00038 and -0.00038. A zero quantity is a row
kept with nothing on it.

The lifecycle, on the October ticket's indexes and dates, where the legs fix on different
days: A, a futures index with a lot of 10,000 MMBtu, observes F27 on 29 December 2026 at
3.55; B, an IFERC index with a lot of 2,500, publishes on 4 January 2027 at -0.35; `+2bd` on
weekends-only holidays pays 6 January 2027. A less B, 10,000 MMBtu at a spread price of 3.80:

| State | Floating spread | Payment amount | Nominal delta A / B | Value |
|---|---:|---:|---|---|
| 28 December, live at 3.50 and -0.40 | 3.90 | 1,000 | 1 / -4 | mark 1,000 times the day's factor; DV01 from the remaining days |
| 30 December, A fixed, B live at -0.40 | 3.95 | 1,500 | 0 / -4 | mark 1,500 times the day's factor; DV01 remains |
| 5 January, both fixed | 3.90 | 1,000 | 0 / 0 | mark 1,000 times the day's factor; DV01 remains, no delta |
| 6 January, paid | 3.90 | 1,000 | 0 / 0 | mark and DV01 zero; cash 1,000, one amount |

B's fixing above its quote lowers the payment, where on a `fixed_float` pair it raises it.
Correct A's fixing to 3.60 and the payment is 1,500; only that leg's floating side and the
one payment move. `util_BumpDiscountCurve` up and down checks the analytic DV01 against the
whole mark and each index's cross gamma against its own delta.

Aggregation: the synthetic spread beside a `fixed_float` on NTO alone, 5,000 MMBtu at -0.30,
on the same payment and curve. NTO totals 6 nominal and 5.7 delta, PAN -4 and -3.8, the SOFR
DV01 -0.07125. The membership rows:

| position | index | reporting_lot | nominal_delta | delta | dv01 | cross_gamma |
|---|---|---|---:|---:|---:|---:|
| 1 | NTO-PAN | - | - | - | -0.0475 | - |
| 1 | NTO | LOT | 4 | 3.8 | - | -0.00038 |
| 1 | PAN | LOT | -4 | -3.8 | - | 0.00038 |
| 2 | NTO | LOT | 2 | 1.9 | -0.02375 | -0.00019 |

A sold NTO position of the spread's size beside it leaves NTO at zero and PAN at -4; a
cashflow on SOFR moves that column alone; a repeated spread counts twice.

Also pin: the dollar that survives two prices at 1e16, with both legs live, with one fixed,
with both fixed and as cash; the refusals in the table above and every pair rule that
stands; histories and markets matched by identity; a batch equal to its singleton rows;
strips, calday and zero rows on both legs; the two indexes given in the other order, with
the quantity and the spread price both negated, reading the same mark and the same risk on
each index; `counterparty`, `marketing_reserve` and `cva_reserve` as on any bilateral batch.
Every existing `fixed_float` test, one index and two, passes unchanged.

## Desk inputs still to come

Three facts of the NTO/PAN trade, asked for on the issue:

- **Leg order.** Which of the two a positive quantity receives, so which handle stands first.
- **The two indexes.** Their kind and quote unit, and how each leg fixes for the month.
- **Payment.** The payment date or rule and its holiday calendar.

They decide the trade's own numbers in the acceptance and the block the kept workbook books
as the real trade. The build does not wait for them, with one exception: a batch takes a
futures or an IFERC index, so a leg on a Gas Daily index would wait for that kind to be
built.

## Engineering boundaries and delivery

One pull request from main, this page and its index rows in the first commit, the build in
the next. Inside it, in order: the definition, `float_float` in the catalog; the resolution,
which takes either instrument's template, reads the instrument's price field and holds a
`float_float` to two indexes, a bilateral route and no broker; the terms, the second leg's
sign, the descriptor and the refusals' words; the encoding, the second leg's quote quantity
and coefficient signed once and the spread leg made from the first leg's; then the
preparation, the evaluation, the reports and the collection, where no arithmetic is expected
to change and the tests say so; the readbacks; then the tests, a host fact, a smoke block, a
lifetime group and a block of the kept workbook. The pages above, a history row and UAT
item 35.

Measure before and after. A `fixed_float`'s work counts, numpy ledgers and allocation pins
stand, one index and two; its function ledgers move only where a shared step gains or
renames a helper. A `float_float` is expected to do a `fixed_float` pair's work at every
step: on a tick, 2 live prices read, 1 curve selected, 1 payment factor read, 1 group
valued, 2 slots discounted and 2 weighted and 20 risk reductions, whatever the ticket's row
count. The pull request states the counts it measured.

## Outside this slice

The second slice, on the issue: a `spread_price_unit`, each leg's price converted to it
once at creation, a quantity entry for indexes whose lot sizes differ, and the cracks the
issue hand-prices, RB, heating oil and C5 natural gasoline against WTI.

Outside both: cleared or brokered spreads, a batch whose rows each name their own two
indexes, two separately executed swaps settled apart, physical delivery, more than one
currency, unequal ratios between the legs, legs in different months, three-leg baskets,
options, a synthetic joint index, new data retrieval, and a quote or a request for quote on
a spread.
