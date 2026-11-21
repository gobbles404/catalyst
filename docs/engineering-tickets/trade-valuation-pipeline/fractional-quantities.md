# A financially settled trade takes a fractional quantity

**Status:** Built in #NNN, agreed with the owner on 21 November 2026 for
[issue #262](https://github.com/gobbles404/catalyst/issues/262), this page in its first commit;
one pull request on `feat/fractional-quantities`, stacked on `refactor/dollar-unit`, the branch of
[currency-and-currency-unit.md](currency-and-currency-unit.md), #266. It follows
[zero-quantities.md](zero-quantities.md), #146, which made zero a quantity, and
[expired-physical-cash.md](expired-physical-cash.md), #258, which is why a physical quantity stays
whole. [kernel.md](../../library/trades/kernel.md) owns the rule;
[show-instrument.md](../../library/instruments/show-instrument.md),
[trade-template.md](../../library/trades/trade-template.md) and
[create-trades.md](../../library/trades/create-trades.md) are the other owners it updates.

## The issue

`fixed_float` and `float_float` refused a `quantity` that was not a whole number. UAT met a
bilateral crude swap of a lot and a half, and the owner expects more of them in metals. The only
way to book such a trade was to change its quantity, and a booked quantity must be the trade's
own. A request for quote already took fractions, so a trade could be quoted at 1.5 and then not
booked.

## Decisions of 21 November 2026

| Decision | Agreed |
|---|---|
| The rule follows the settlement method | A financially settled row takes any finite quantity, positive, negative or zero. A physically settled row takes a whole number, exactly as before, in the words it always gave. |
| Any route | Cleared and bilateral alike. Fractions have only been seen on bilateral deals; a clearing house has its own rules on size, and the library enforces none of them. |
| Nothing is rounded | The quantity is used and read back as entered. No precision, increment or tolerance is introduced. |
| A number that is not finite | Refused under either settlement, named by its trade: in the financial rule's words under a financial settlement, and in the whole-number words, unchanged, under a physical one. |
| What stays whole | A trade ID, a `nearby` and a lot size. A fraction is a quantity's alone. |

## Why the split is safe

The whole-number rule does necessary work in one place. A physical position is closed when its
signed counts per contract add to exactly zero, `position_counts` in `trades/encoding.py` since
#258, and that sum is exact only for whole numbers. A financially settled trade is never asked
whether it is closed: its quantity is multiplied, by prices, weights and discount factors, which
a fraction does as well as a whole number.

So no rule is needed for a residue such as `0.1 + 0.2 - 0.3`, which is not zero in binary. Three
financial rows with those quantities book, each as entered, and are worth the residue's few
thousandths of a billionth of a lot. The question of when a position is closed arises only for
physical trades, which stay whole.

## Where the rule is read

A batch has one settlement, from the template or from a ticket column every row agrees on, and
the kernel knows it when it reads the quantities. So the kernel is the one place the rule is
chosen:

```text
settled_quantities(quantity, settlement, where)
    financial -> finite_quantities    any finite number
    physical  -> whole_quantities     a whole number, as before
```

A ticket's quantity column is read there and nowhere else, as it always was. A template reads
its own quantity when it is made, and there are two cases:

| The template holds | When the rule is read | Words on a refusal |
|---|---|---|
| `quantity` and `settlement_method` | when the template is made, by that settlement's rule | `quantity is 1.5, expected a whole number` |
| `quantity` alone, the ticket to supply the method | the part every settlement shares, finite, when the template is made; the rest when the batch is made, by the kernel | `quantity of trade 1001 at row 1 is 1.5, expected a whole number`, from `_CreateTrades` |

This is the one change a sheet can meet without entering a fraction on a financial row: a
template of `quantity` and nothing about settlement used to refuse 1.5 when it was made. It is
now made, and the refusal comes from `_CreateTrades` if the ticket then settles physically.

## Worked example

A bilateral swap on one index, bought, its one observation still live.

- Quantity: 1.5 lots of 1,000 BBL, per month, one month.
- Floating price 70.00 dollars a barrel; fixed price 68.00.
- One payment exactly one ACT/365F year away; discount factor 0.95.

| Measure | At 1.5 | At -0.25 |
|---|---:|---:|
| Net undiscounted amount | 3,000 | -500 |
| NPV | 2,850 | -475 |
| Nominal delta, lots | 1.5 | -0.25 |
| Discounted delta, lots | 1.425 | -0.2375 |
| Curve DV01, dollars a basis point | -0.285 | 0.0475 |
| Index by curve cross gamma, lots a basis point | -0.0001425 | 0.00002375 |

By hand: 1,500 barrels at 2.00 is 3,000, and at 0.95 it is 2,850. The DV01 is one year times
2,850 times 0.0001, falling as rates rise. The cross gamma is the discounted lots, 1.425, times
one year times 0.0001, falling too. Each figure is 1.5 times the same trade at a quantity of 1,
and the row at -0.25 gives each figure times -1/6. The quantity comes from a ticket row or from
the template with the same result, and the booked readback shows 1.5.

## Each quantity basis

`quantity_per`, `quantity_unit`, unit conversion and the paired legs mean what they did. A
fraction is a fraction of the selected specification, not another unit.

| Shape | Basis | Entered | Gives |
|---|---|---|---|
| `fixed_float`, one index | `month` | 1.5 lots of 1,000 BBL | the worked example |
| | `calday` | 1.5 lots a day over February 2027 | 42 lots, 84,000 undiscounted, 79,800 of NPV |
| | `period` | 1,000.5 barrels over the WTI trade month of [onetime-averaging.md](onetime-averaging.md) | a mark of 1,000.5 times -8/11, -727.64, the barrels 19/22 to N26 and 3/22 to Q26 |
| `fixed_float`, two indexes | `month` | 12,345.5 MMBTU at the outright 3.00 against 3.10 | 1,234.55; 1.23455 lots of 10,000 and 4.9382 of 2,500 |
| | `calday` | 100.5 MMBTU a day over February | 281.40; 0.2814 and 1.1256 lots |
| `float_float` | `month` | 12,345.5 MMBTU, 0.15 apart against a spread price of 0.10 | 617.275; 4.9382 lots received and as many paid |
| | `calday` | 100.5 MMBTU a day over February | 140.70; 1.1256 lots a side |

`period` belongs to `settlement_frequency = onetime`, which is one futures index's average. On
two indexes it is not built, for a `fixed_float` pair and for a `float_float` alike, and a
fraction changes nothing about that: the refusal is the one a whole number gets.

## Reserves

The fees follow the size of the quantity, as before; the two entered reserves do not depend on
it. On an index charging 100 of brokerage and 50 of clearing a lot, a cleared, brokered row:

| Quantity | Brokerage | Clearing | Marketing | CVA |
|---:|---:|---:|---:|---:|
| 1 | 100 | 50 | 15 | -40 |
| 1.5 | 150 | 75 | 15 | -40 |
| -0.25 | 25 | 12.50 | 15 | -40 |
| 0 | 0 | 0 | 15 | -40 |

## Ownership

| Fact | Owner |
|---|---|
| Which rule a quantity is held to | `settled_quantities` in `trades/terms.py`, by the batch's `Settlement`, one `match` with `assert_never` |
| The financial rule | `finite_quantities`, beside it: finite, zero and fractions included |
| The physical rule | `whole_quantities`, unchanged |
| A ticket's quantities | `_the_components` in `trades/terms.py`, which takes the settlement and names each refusal by its trade |
| A template's quantity | `trade_template` in `trades/template.py`, once, after every field's own rule; the per-field reader `quantity_of` is gone, the rule being two fields' |
| The field's words | `instruments/definitions.py`: `fixed_float`'s `quantity` says a whole number when settled physically; `float_float`'s, which settles financially and nothing else, says fractions are included |

## Readbacks and refusals

| What | Words |
|---|---|
| A fraction on a physical row | `quantity of trade 1002 at row 2 is 2.5, expected a whole number`, unchanged |
| A number that is not finite on a physical row | `quantity of trade 1002 at row 2 is nan, expected a whole number`, unchanged |
| A number that is not finite on a financial row | `quantity of trade 1 at row 1 is nan, expected a finite quantity` |
| A physical template holding a fraction | `quantity is 1.5, expected a whole number`, unchanged |
| A template holding a number that is not finite, financial or with no method | `quantity is inf, expected a finite quantity` |
| A blank or a text cell | the seam's, as before |
| The readbacks | `quantity` as entered, a `float64` as it always was; no column added, moved or renamed |
| `_ShowInstrument("fixed_float")` | `quantity`'s options read `a signed number, zero included; whole when settled physically` |
| `_ShowInstrument("float_float")` | `quantity`'s options read `a signed number, zero and fractions included` |

## Also pin

- Any finite quantity is kept to the last bit and scales every figure of the worked example, a
  property test over quantities to a billion either side of zero.
- A zero row beside fractions is kept and adds nothing.
- A request priced at a barrel and a half and a quarter of one, and the same months booked at
  that price, mark zero on either route, the existing comparison at fractional quantities.
- Every physical test passes as written, the expiry cash lifecycle of #258 among them.
- The work: no `WorkCounter` count moves. The kernel's function ledger for a financial batch
  reads `settled_quantities` once and `finite_quantities` once where it read `whole_quantities`
  once, and its one `ndarray.round` is gone; a physical batch reads `settled_quantities` once
  more and is otherwise as it was. The same at 5 rows and at 2,000.

## Delivery

One pull request: the rule, the template's reading, the two descriptions, the unit, performance
and host tests, the smoke's block, the pages and the kept workbook's block. The full gate before
the pull request is marked ready.

## Outside this slice

- Fractional physical quantities, and with them any rule for when a fractional position is
  closed.
- Enforcing an exchange's or a clearing house's rules on size.
- A precision, an increment, a minimum charge or a tolerance of any kind.
- `period` on two indexes, which waits for a onetime pair.
- Cashflow amounts and request-for-quote quantities, which already took fractions and are not
  touched.
