# A signed CVA reserve on the fixed_float

**Status:** Built in #244, agreed with the owner on 8 November 2026 for
[issue #243](https://github.com/gobbles404/catalyst/issues/243), this page in its first commit;
one pull request on `feat/cva-reserve`, stacked on `feat/two-index-one-price`, the branch of
[two-index-one-price.md](two-index-one-price.md), #242. It follows
[booking-fields-and-marketing-reserve.md](booking-fields-and-marketing-reserve.md), #175, which
added the marketing reserve, field for field. [report-reserves.md](../../library/trades/report-reserves.md)
owns the reserves; [show-instrument.md](../../library/instruments/show-instrument.md),
[trade-template.md](../../library/trades/trade-template.md),
[create-trades.md](../../library/trades/create-trades.md),
[evaluate-trades.md](../../library/trades/evaluate-trades.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the other owners it updates.

## The issue

The desk books a credit valuation adjustment, CVA, against a trade: a reserve for the chance
that the counterparty does not pay what it owes, entered as an amount in the settlement
currency, which the desk sets positive, zero or negative as its own method decides. The library
books three reserves, brokerage, clearing and marketing, each a cost of zero or more, and
`_ReportReserves` shows them; there is no field for this one. The system of record carries it on
the trade, so a batch carries it too, beside `marketing_reserve`, and shows its signed total.

## Decisions of 8 November 2026

| Decision | Agreed |
|---|---|
| The field | `cva_reserve`, a number, optional, from the template or the ticket as `marketing_reserve` is, on either route: the issue says to follow the marketing reserve, and the system of record decides what is booked, not the route. Omitted from both, zero. |
| The rule | A finite amount of either sign: a negative amount and zero are kept as entered, NaN and the infinities refused, the rule the cashflow instrument's `amount` already reads by, in its words. Nothing is rounded or converted. |
| Once per row | Booked once per ticket row whatever its months, quantity, days or direction, a strip once and a two-index swap once; the batch's total is the rows' amounts summed with their signs, and a duplicate row counts again. |
| Where it shows | In the catalog after `marketing_reserve`, `settlement_frequency` still last; in the trades readback after `marketing_reserve`, where the batch has the field; in `_ReportReserves` and the results readback as `cva_reserve` after `marketing_reserve` and before `currency`, so the results readback's later columns, `currency` to the four observation columns, move one to the right. |
| Value and risk | Unchanged: a reserve enters no number. |
| Counting | `reserved_occurrences` counts once per ticket row per reserve field booked, as `reserved_fee_components` counts once per component per fee charged since #188; no new counter. |

## Calculation

```text
cva_total = sum over the ticket's rows i of cva_reserve[i]      # signs kept, once per row
```

Each amount is finite by the rule that read it; the total is held finite the way the marketing
total is, summed with numpy's flags down and refused for the batch when amounts each finite sum
past the largest number in either direction. The example is on the fee index of
[report-reserves.md](../../library/trades/report-reserves.md), LOT at 10 of brokerage and 4 of
clearing a lot, under the cleared template naming ION as broker:

| Row | Quantity | Period | CVA | Brokerage | Clearing |
|---|---:|---|---:|---:|---:|
| 1001 | 2 LOT | Z26 | 25 | 20 | 8 |
| 1002 | -2 LOT | Z26-F27, two components | -40 | 40 | 16 |
| 1003 | 0 LOT | Z26 | 0 | 0 | 0 |
| **Batch** | | | **-15** | **60** | **24** |

The strip books its -40 once though it makes two components, the zero-quantity row its 0, and
the marketing reserve, no field here, is 0. A duplicate of row 1001 books 10. A template's -40
on the four plain rows of the reserve example, 2 LOT, -2 LOT, 1,000 BBL and 0 LOT, books -160
over 50 and 20. The marketing ticket's four rows with both columns, 15, 20, 25 and 5 of marketing
and 25, -40, 0 and 5 of CVA, book 65 and -10 side by side. Two rows of 9e307 sum to infinity and
the batch is refused; two rows of -9e307 the same. The mark, the cash and every risk are the
same with the column and without, through a tick, a fixing and a payment.

## Ownership

| Fact | Owner |
|---|---|
| The field: name, description, type, options and rule | `instruments/definitions.py`, after `marketing_reserve` |
| The rule, finite of either sign | `cashflows/rules.py`'s `finite_amounts`, the cashflow amount's rule, read by `trades/template.py`'s `cva_reserve_of` for a template's value and by the resolution for a ticket's column |
| The reading | `_Fields.amounts(name, rule)` in `trades/resolution.py`, the one reader for both reserve fields, each handing it its own rule |
| The amounts per row | `ResolvedTrades.cva_reserve` in `trades/terms.py`, one per occurrence, `None` as a whole when neither the template nor the ticket supplied the field, after `marketing_reserve` |
| The total | `Reserves.cva` in `trades/reserves.py`, after `marketing`: the rows' amounts summed once, 0.0 when the field is absent, refused for the batch when not finite, `reserved_occurrences` hit once per row |
| The report | `_ReportReserves` in `excel/trades.py`: `brokerage_reserve`, `clearing_reserve`, `marketing_reserve`, `cva_reserve`, `currency` |
| The readbacks | `excel/utilities.py`: the trades readback where the batch has the field, the row's signed amount on each of its components and no allocation; the results readback on the first slot row and a dash below, as the other three |

## Readbacks and refusals

| What | Words |
|---|---|
| A ticket row refused by the rule | `cva_reserve row 2 is inf, expected a finite amount` |
| A template refused by the rule | `cva_reserve is nan, expected a finite amount` |
| The total refused | `the batch has inf of cva reserve in all, expected a finite amount of USD; the rows' amounts, each finite, sum past the largest number`; `-inf` in the same words |
| The field from both | `cva_reserve is supplied by the template and by the ticket, expected by one of them` |
| A blank or a text cell | the seam's, `trade_rows cell (1, 7) is blank, expected number` |
| A quote template | `cva_reserve is a field of booking alone, expected ...`, as every booking field |
| `_ShowInstrument("fixed_float")` | ten rows by twenty-three columns, `cva_reserve` the twenty-second field, options `a finite amount of either sign` |

## Also pin

- A pair books the amount once per row, though it has two legs.
- The results carry the encoding's record by reference; nothing is reserved again at
  preparation, evaluation or reading.
- The ledgers: `_Fields.has` and `FieldValues.has` one more each, the field looked for;
  `_Fields.amounts` twice; the shown instrument 230 cells where it laid out 220;
  `reserved_occurrences` N for a batch booking one reserve field and 2N for both; the
  encoding's and the creator's ledgers gain the sum's helper twice.

## Delivery

One pull request: the field, the rule, the terms, the reserves, the report, the readbacks, the
unit and performance tests, the host fact, the smoke's block, the pages and the kept workbook's
block; every positional pin on the results readback's later columns moves one to the right, and
the refusal that lists the instrument's fields gains a name. The full gate before the pull
request is opened.

## Outside this slice

- No CVA calculation: the desk enters the amount; nothing here reads a counterparty, a curve
  or a probability of default.
- No release, accrual, discounting or move to cash; the amount is booked, as the other three.
- No route condition: a cleared batch may book one as a bilateral may.
- No column in a collection's report or readback: `_AggregateResults` carries no reserve, as
  before.
- No change to brokerage, clearing or marketing.
