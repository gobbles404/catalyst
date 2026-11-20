# A closed physical contract past its expiry, as cash

**Status:** Built in #258, from main after #253, agreed with the owner on 20 November 2026
for [issue #256](https://github.com/gobbles404/catalyst/issues/256), this page in its first
commit. It changes the one rule that refuses every physical `fixed_float` past its expiry,
and adds one rule at creation. No instrument, field or function is added.
[kernel.md](../../library/trades/kernel.md), [create-trades.md](../../library/trades/create-trades.md),
[prepare-trades.md](../../library/trades/prepare-trades.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the owners it updates.

## The issue

A physically settled futures contract that has expired fails `_PrepareTrades`, whatever the
batch holds: `trade 1001 at row 1 on Z26 expired 2026-11-25, before valuation date
2026-11-26; a physical fixed_float after its expiry is not supported`. That is right for a
position still open, which is a delivery. It is wrong for a position the desk closed before
expiry: the buy and the sell are both in the batch and nothing is left to deliver. Today the
desk deletes the rows and types a cashflow by hand to keep the profit or loss it locked in,
and deleting the rows deletes their brokerage and clearing, so the total moves on the day
the futures turn to cash.

## Decisions of 20 November 2026

| Decision | Agreed |
|---|---|
| The instrument | None new. A rule on the `fixed_float` the desk books: cleared, physical, one index, `lastday`. |
| Closed | For an expired contract, the quantities of each `quantity_unit` add to exactly zero. A quantity is a whole count, as the kernel already requires, and the counts are added as whole numbers: no unit conversion and no tolerance. |
| Two units on one contract | Each `quantity_unit` is counted by itself. Long 1 `NYMEX NG` against short 10,000 `MMBTU` reads as open. A futures position is closed in the lots it was opened in, and each product has its own template. |
| The clearing house | A physical batch names one, checked once, when the batch is made. A financial batch may name several, as today. |
| The amount | The entry-price sides alone, the fixed legs the batch already holds. The final price multiplies a quantity of zero and plays no part, so a corrected fixing moves nothing. |
| Brokerage and clearing | As booked. The reserves are made once from every row and the rows stay, so `_ReportReserves` reads the expired trades' fees in full before and after the expiry. Nothing moves into cash. |
| When | The calendar's own rule: a contract has expired when its expiry day is before the valuation date. On its expiry day it is live. |
| The trade date | No rule reads it. A close dated after the last trading day is a row like any other. |
| Still open | An expired contract whose counts do not add to zero fails the batch and publishes nothing, naming the contract, the count left and its unit. |

## The behaviour

| A contract in the batch | Result |
|---|---|
| Not yet expired, its expiry day included | As today: in the mark, with its delta |
| Expired and closed | Its fixed legs are `cleared_cash`; no mark and no risk from it |
| Expired with a count left | The preparation fails; nothing is published |

The rows stay as booked. The cash is made from them each time the batch is prepared, so
preparing or evaluating again adds nothing twice, and a result already held is the snapshot
it was.

## Calculation and retained state

At creation, for a physical batch, once:

```text
left[g, u]  = the sum of the component quantities of group g entered in quantity unit u
closed[g]   = every left[g, u] is zero
```

A group of a physical batch is one contract month. The component quantity is the count the
terms formed, the entered quantity under `month` and the entered quantity times its covered
days under `calday`, whole either way. The counts and their sums are exact while one
contract holds under 2^53 of one unit in all, buys and sells together: below it every
count, a quantity per day times its days among them, and every partial sum is a whole
number a number holds. A physical batch holding 2^53 or more is refused when it is made,
since past it a lot may be rounded away or in, and a position read closed that is not.
The encoding keeps `closed`, one flag per group, and nothing else; a financial batch keeps
none and does none of this.

At preparation, per group:

```text
expired[g]  = the calendar marks the contract's expiry day fixed
settled[g]  = expired[g], which requires closed[g], else the batch is refused
cash        = the sum over the settled groups of the group's fixed legs
```

A settled group's set amount, its exposure times the expiry's settle, enters neither the
cash nor the unsettled totals: the exposure is a quantity of zero. The history still holds
the expiry's settle, as it holds every fixed day's, and the slot reads it. The mark, the
deltas and every number of a contract not yet expired are made as they were. A tick does
nothing new.

## The refusals

In the words the build pins:

| Entered | Refused as |
|---|---|
| A second clearing house on a physical batch, at creation | `clearing_house of trade 1002 at row 2 is 'ICE Clear Europe', expected 'CME Clearing' as at row 1; a physical batch clears through one clearing house` |
| One contract holding 2^53 or more of one unit, buys and sells together, at creation | `Z26 holds 9007199254740992.0 of 'LOT' in all, buys and sells together, expected under 9007199254740992.0; a physical position is closed by its whole counts adding to zero, and past 2^53 a number does not add them exactly` |
| An expired contract with a count left, at preparation | `Z26 expired 2026-11-25, before valuation date 2026-11-26, with 16.0 of 'NYMEX NG' open, trade 1001 at row 1 among them; a physical position open past its expiry is a delivery, which is not modeled` |

The second replaces `a physical fixed_float after its expiry is not supported` on a batch.
A quote on a physical template past its contract's expiry keeps those words: a quote holds
no position to close.

## Hand-priced acceptance

A synthetic index quoted in USD per MMBTU, one specification, `LOT`, 10,000 MMBTU, charging
10.00 of brokerage and 4.00 of clearing a lot. Z26 expires 18 November 2026. A cleared
physical template naming one clearing house and a broker:

| Row | Lots | Entry price | Fixed leg |
|---|---:|---:|---:|
| Buy | 1 | 3.00 | -30,000 |
| Sell | -1 | 3.10 | 31,000 |

| Valuation date | cleared_mark | cleared_cash | Delta | Brokerage | Clearing | Mark + cash - fees |
|---|---:|---:|---:|---:|---:|---:|
| 18 November, the expiry day, live at any quote | 1,000 | 0 | 0 | 20 | 8 | 972 |
| 19 November, expired | 0 | 1,000 | 0 | 20 | 8 | 972 |
| 20 November | 0 | 1,000 | 0 | 20 | 8 | 972 |

A settle of 3.00 or of 9.00 on the 18th reads the same 1,000 on the 19th. The two prices
swapped lose 1,000.

With F27 beside it, 2 lots bought at 3.40 and still live at 3.50 on 19 November: the cash is
Z26's 1,000, the mark F27's 2,000 and the delta F27's 2 lots.

Also pin: the refusal of a long lot, of a short lot and of a buy entered twice against one
sell; long 1 `LOT` against short 10,000 of a one-MMBTU unit refused, the first unit with
a count left named;
one buy against two sells, a pair entered twice and the rows in any order closed; a quantity
per day against a quantity per month that count the same closed; a contract holding zero
rows alone closed and carrying nothing; one open expired contract failing a batch whose
other expired contract is closed; a later expiry judged on its own day; a correction that
leaves a count open refused and the same batch good again once the row is put right; a batch
that prepares where each row alone is refused; counts under 2^53 that close and that leave
one, exactly, and a contract holding 2^53 or more of a unit refused when the batch is made, a
quantity per day whose product with its days rounds among them; two clearing houses refused on a physical batch and made on a financial
one; and every existing refusal of a physical batch.

## Engineering boundaries and delivery

One pull request from main, this page and its index row in the first commit, the build in
the next. Inside it: the terms, one clearing house on a physical batch; the encoding, the
counts by group and unit and the flag; the preparation, the settled groups, the cash and the
refusal in place of the blanket one; the readback, where `is_settled` already stands; then
the tests, a host fact, a smoke block, a lifetime group and a block of the kept workbook;
the owning pages, a history row and a UAT item.

Measure before and after. A financial batch's work counts, numpy ledgers and pins stand;
its function ledger gains one call at creation, the one-house rule, which looks at the
settlement and returns. A physical batch gains, at creation, one sum over its components, whatever its rows; at
preparation it reads the flag per group and sums the settled groups' fixed legs, and no
longer runs the compensated sum of set amounts it had no settled group to use on. A tick is
as it was. The pull request states the counts it measured.

## Outside this ticket

Modeling a delivery. Netting across batches: `_AggregateResults` cannot close a position
whose batches each fail. Netting across units or clearing houses. A ledger of realized
profit and loss: the cash lasts as long as the rows stay in a batch whose schedule still
lists the contract and whose history still reaches back to it, as a paid financial trade's
cash does. Fees moved into cash, a bank transfer or daily variation margin. A bilateral
physical batch, which `_EvaluateTrades` refuses as before. Automatic closes or rolls, a
payment day for a physical contract, the named payment calendars of #255 and the cashflow
curves of #254.
