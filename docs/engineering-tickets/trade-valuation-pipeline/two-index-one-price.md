# One outright price on a two-index fixed_float

**Status:** Agreed with the owner, 8 November 2026, for
[issue #241](https://github.com/gobbles404/catalyst/issues/241). One pull request from
main, this page in its first commit. It replaces the two entered leg prices of
[two-index-fixed-float.md](two-index-fixed-float.md), built in #215, #216 and #217, with the
one outright price the system of record books, and retires the leg values and leg DV01s
that split invented; everything else of that ticket stands as built.
[kernel.md](../../library/trades/kernel.md), [create-trades.md](../../library/trades/create-trades.md),
[evaluate-trades.md](../../library/trades/evaluate-trades.md),
[report-risk.md](../../library/trades/report-risk.md),
[aggregate-results.md](../../library/trades/aggregate-results.md),
[show-instrument.md](../../library/instruments/show-instrument.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the owners it updates.

## The issue

The system of record books a fixed price swap on a composite index, Henry Hub plus Waha
basis, at one outright fixed price. The October build takes a fixed price per leg and adds
them. Every whole-trade number is already independent of the split: a test moves 3.30 and
-0.30 to 3.20 and -0.20 and the mark, DV01, deltas and cross gammas stand. What the split
invented is a second entered price, a derived combined price, and each leg's amount, NPV,
DV01, mark and cash, numbers the record cannot confirm, because nothing in a single price
says how much of it is Henry Hub's.

## Decisions of 8 November 2026

| Decision | Agreed |
|---|---|
| The price | One `fixed_price` per row, the outright, in the quote unit the two indexes share. `second_fixed_price` leaves the definition; `combined_fixed_price` leaves the readback. |
| The methods | `second_schedule_method` stays, required with two indexes and refused with one: each component index keeps its own observation method. |
| The fixed-price index | The composite the record quotes the price on is no third index object. The swap's name is its handle's descriptor, `HNG+WAH`, the legs' index names joined by `+` in leg order, and that name stands wherever the swap's DV01 is attributed. |
| DV01 | The swap's whole: one number per month's payment and one per curve, counted once against the discount curve. No leg share anywhere. |
| Delta | Per component index, in that index's reporting lot, as built. |
| Cross gamma | Per component index and curve, as built. No outright column. |
| Delivery | One pull request; this page first. |

## Why the risks fall where they do

A month's payment is one amount: the quantity times Henry Hub plus Waha minus the outright
price. A one-cent move in Henry Hub moves it by the quantity in cents whatever the fixed
price is, so Henry Hub's delta is the quantity in Henry Hub lots and Waha's the quantity in
Waha lots, each clean on its own. Discounting the one payment gives one NPV and one DV01; a
share for Henry Hub would need a share of the outright price, which the booking does not
state. Henry Hub's cross gamma is how Henry Hub's discounted delta changes when the curve
moves one basis point, made from Henry Hub's live lots and the month's time to payment and
nothing of the fixed price, so it stays with Henry Hub, and Waha's with Waha. An outright
cross gamma is not defined once one leg has fixed and the other is live, the outright then
having no single floating price; the per-index view always is.

## Booking and worksheet contract

The three function names and argument positions stand, `indexes`, `histories` and `markets`
as #217 built them. The `fixed_float` definition:

| Field | One index | Two indexes |
|---|---|---|
| `fixed_price` | The fixed price agreed | The outright price agreed, the price of the sum of the two indexes, in the quote unit they share |
| `schedule_method` | The method | The first index's method |
| `second_schedule_method` | Absent, refused by name | Required, the second index's method under its own kind |

`second_fixed_price` is no field of the instrument. A template or a ticket naming it is
refused as any unknown header is, by its cell and in the seam's words, for a ticket
`fields cell (1, 6) is text 'second_fixed_price', expected a field of fixed_float: trade_id, ...`,
the list no longer carrying it. No alias, no default and no silent zero. The description of
`fixed_price` says its two-index meaning; `second_schedule_method` keeps `two indexes` under
`required_when`. Fields may be supplied in either template or ticket, never both, as before.

The October ticket's row with one price, the index handles in B2:B3:

| trade_id | contract_code | quantity | fixed_price |
|---|---|---:|---:|
| 12345 | F27 | 10000 | 3.00 |

```excel
=_CreateTrades(B2:B3, TicketHeaders, TicketRows, TemplateHandle)
```

Everything else of the pair's entry stands: two distinct indexes of distinct names, the same
quote currency, quote quantity and settlement currency units, a financial settlement, one
quantity per entered unit on both indexes, each row's months resolved against each schedule,
the payment anchor the later of the two legs' last observations, the first leg's
specification supplying the fees.

## Calculation and retained state

For each monthly component, after quantity conversion and observation weighting, with Q the
common quantity in the shared quote unit and K the outright price:

```text
fixed_leg = -Q * K                          the trade's, booked once per component
floating_A = Q * price_A                    the leg's: fixed slots at their settles, live slots at their quotes
floating_B = Q * price_B
payment_amount = fixed_leg + floating_A + floating_B
```

For an unpaid bilateral payment with its selected factor DF and
`tau = calendar_days(as_of, payment_date) / 365`:

```text
NPV = payment_amount * DF
DV01 = -tau * NPV / 10000
```

Cleared valuation stays undiscounted with zero DV01 and cross gamma. On payment the amount
becomes cash, one amount. A fixed but unpaid payment still has DV01 and no commodity delta.
The two legs' coefficients, Q in the settlement currency per unit of quote price, agree to
within the pair rule's roundoff; the first leg's makes the fixed leg, as the first leg
supplies the fees and the first word of the handle.

Ownership after the change; the implementation chooses record names:

| Record | Shared state, the trade's | Per-leg state |
|---|---|---|
| Created trades | Rows, periods, quantities, the fixed price and the fixed leg per component and per payment group, payment dates and keys, reserves | Index, method, observations, quote quantities, coefficients, slots and exposures |
| Prepared trades | Valuation date, settled groups, the set amounts summed, cash and unsettled totals, rate-date preparation | Exact history, fixed slots and their settles, set amounts, live exposures, nominal delta and lots on the index's axes |
| Evaluated trades | Payment amount, NPV, DV01 and factor per group, mark, cash, DV01 by curve, reserves | Exact market, live contributions and quotes, delta, discounted lots, cross gamma by curve |

A leg retains no price, no fixed leg, no amount, no NPV, no DV01, no mark and no cash. Its
floating side stays inspectable slot by slot through the observation columns of
[observation-prices-readback.md](observation-prices-readback.md).

## Risk grouping and readback

`_ReportRisk` is unchanged for a pair: the deltas one column per index in its lot, the DV01
one column per curve and currency, the cross gamma one column per index and curve, by day,
month or year, the layout the collection of two single-index results would have. Any split
of the outright between two single-index trades on the same rows reads the same, every
column being independent of the split; the build keeps that test.

The collection groups as before: index groups per index object, rate groups per curve and
currency, cross groups per index and curve. The membership readback, `util_ReadHandle` on
the collection, changes for a pair: a row named by the swap's descriptor carries its DV01 and
dashes under the commodity columns, and a row per leg carries its index's nominal delta, delta
and cross gamma with a dash under `dv01`. A one-index source keeps its one row, its descriptor
being its index's name. The pair beside an A-alone trade of 5,000 MMBtu at 3.40:

| position | index | reporting_lot | nominal_delta | delta | dv01 | cross_gamma |
|---|---|---|---:|---:|---:|---:|
| 1 | A+B | - | - | - | -0.095 | - |
| 1 | A | LOT | 1 | 0.95 | - | -0.000095 |
| 1 | B | LOT | 4 | 3.8 | - | -0.00038 |
| 2 | A | LOT | 0.5 | 0.475 | -0.0475 | -0.0000475 |

The created-trades readback shows `fixed_price` and `offset` once, the trade's, and
`second_schedule_method` after `schedule_method`; `second_fixed_price`,
`combined_fixed_price` and `second_offset` go. The results readback keeps one row per slot
with `leg` and `index`, the factor on every row and the payment's amount, NPV and DV01 once
per group on its first row of all, the swap's and under no index; `leg_amount`, `leg_npv`,
`leg_group_dv01`, `leg_mark`, `leg_cash` and `leg_dv01` go. A one-index batch reads back as
it does today, column for column.

## Hand-priced acceptance

The October ticket's indexes and dates: A's reporting lot 10,000 MMBtu, B's 2,500, both live
on 4 January 2027, paying 4 January 2028 at a SOFR factor of 0.95. Quantity 10,000 MMBtu,
outright price 3.00, live prices 3.50 and -0.40:

| Measure | A | B | Whole trade |
|---|---:|---:|---:|
| Fixed price | none | none | 3.00, entered |
| Floating price | 3.50 | -0.40 | 3.10 |
| Undiscounted payment | none | none | 1,000 |
| Bilateral mark | none | none | 950 |
| Nominal delta, each index's lots | 1 | 4 | no cross-index sum |
| Delta, each index's lots | 0.95 | 3.8 | no cross-index sum |
| DV01, USD per basis point | none | none | -0.095 |
| Cross gamma, each index's lots per basis point | -0.000095 | -0.00038 | no cross-index sum |

The cleared version: mark 1,000, delta equal to nominal delta, zero rate risk. A sold pair
reverses every value and risk. Change the outright price alone to 2.90: payment 2,000, mark
1,900, DV01 -0.19, every delta and cross gamma unchanged, the outright price moving the value
and the rate risk and never the commodity risk. This replaces the reallocation case of the
October ticket, which has no meaning under one price.

The F27 lifecycle of the October ticket: A observes 29 December 2026 at 3.55, B publishes
4 January 2027 at -0.35, `+2bd` on weekends-only holidays pays 6 January 2027:

| State | Payment amount | Nominal delta A / B | Value |
|---|---:|---|---|
| 28 December, live at 3.50 and -0.40 | 1,000 | 1 / 4 | mark 1,000 times the day's factor; DV01 from the remaining days |
| 30 December, A fixed, B live at -0.40 | 1,500 | 0 / 4 | mark 1,500 times the day's factor; DV01 remains |
| 5 January, both fixed | 2,000 | 0 / 0 | mark 2,000 times the day's factor; DV01 remains, no delta |
| 6 January, paid | 2,000 | 0 / 0 | mark and DV01 zero; cash 2,000, one amount |

Correct A's fixing or move B's quote and only that leg's floating side and the one payment
move. `util_BumpDiscountCurve` up and down checks the analytic DV01 against the whole mark
and each index's cross gamma against its own delta.

Aggregation: the pair beside the A-alone trade above, A totals 1.5 nominal and 1.425 delta,
B 4 and 3.8, SOFR DV01 -0.1425, the membership rows as the table above shows; a cashflow on
SOFR moves that column alone; a repeated pair counts twice.

Also pin: every refusal of the October ticket that stands, the pair rules, the
count-dependent `second_schedule_method`, histories and markets matched by identity;
`second_fixed_price` refused as an unknown field in a template and in a ticket; a
single-index batch unchanged in numbers, reports and readback; a batch equal to its
singleton rows; index reversal keeping values and risks and moving fees; strips, calday and
zero rows on both legs. Gone with the split: the refusals of a combined price or of a leg's
fixed leg, amount, mark or DV01 summing past the largest number; the trade's fixed leg,
payment and totals keep theirs.

## Engineering boundaries and delivery

One pull request from main, this page and its index rows in the first commit, the build in
the next. Inside it, in order: the definition and the template readers; the terms, the fixed
price and the fixed leg moving from the leg to the trade and `combined_fixed_price` going;
the encoding, the trade's offset made once and summed by group; the preparation, whose set
amounts stay per leg and summed; the evaluation, each group's amount the fixed leg plus both
floating sides, the per-leg amounts, NPVs, DV01s, marks and cash gone with their rules; the
results, the two readbacks and the collection's membership; then the tests, the host fact,
the smoke's pair block, the lifetime `pairs` group and the kept workbook's pair block from
row 3100, every ticket of a pair booked at one price. The pages above, a history row, UAT
item 30 and the status line of the October ticket.

Measure before and after: the one-leg path's work counts, numpy ledgers and allocation pins
stand; the function ledgers move where the fixed leg's helper moves and the leg values'
helpers go; the pair's work counts stand too, eight risk reductions a leg and four for the
trade as before, since the per-leg NPVs and DV01s were elementwise products and never
reductions; the pull request states the counts. No shim: a kept sheet typing
`second_fixed_price` fails at the header until the column is removed.

## Outside this slice

Subtraction or a sign selector, a third index object, the system of record's index name on
the handle, an outright cross-gamma column, a DV01 column per fixed-price index in a
collection's report, two-index quoting, separately paying legs, independent leg quantities,
physical two-index settlement and cross-currency legs.
