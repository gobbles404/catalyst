# A cashflow is booked under payment_day

**Status:** Built in #NNN, from main after #260, agreed with the owner on 20 November 2026
for [issue #261](https://github.com/gobbles404/catalyst/issues/261), this page in its first
commit. The `cashflow` instrument's booking field is renamed from `payment_date` to
`payment_day`, the header a `fixed_float` and a `float_float` already book under. A name
changes and nothing else: no number, no worksheet function, no argument and no refusal's
sentence. [show-instrument.md](../../library/instruments/show-instrument.md),
[create-cashflows.md](../../library/cashflows/create-cashflows.md) and
[read-handle.md](../../library/utilities/read-handle.md) are the owners it updates.

## The issue

A sheet that books trades types `payment_day` over the day a row pays. The same sheet
booking a cashflow had to type `payment_date`, a second header for the same thing.

## The two names

Kept as the trades already have them, the owner's words of 20 November 2026:

| Name | What it is | Where it reads |
|---|---|---|
| `payment_day` | What a row enters | A ticket's header, a template's field, the instrument's table, and the readback of what was booked |
| `payment_date` | The calendar date a payment falls on, as the library reports it | The resolved date beside `payment_day` in the booked trades' readback, and every results readback |

After this change every instrument is booked under `payment_day`, and every resolved date
reads as `payment_date`.

## Decisions of 20 November 2026

| Decision | Agreed |
|---|---|
| The field | `payment_day` on the `cashflow` instrument, where it was `payment_date`: required, from the template or a ticket column, never both, in the same place among the fields. |
| A date only | A cashflow's `payment_day` is a date, used as entered and never rolled. The trades' `payment_day` takes a date or a rule such as `+1bd`; a cashflow has no observation day for a rule to count from, and no rule is added. |
| No alias | The old header is refused as any header that is no field of the instrument. A stale sheet fails by name. |
| The booked readback | Its column is renamed in place, `payment_day`, the fifth of the definition's fields. |
| The results readback | Keeps `payment_date`: it is the resolved date, as the other instruments' results name theirs. |
| The refusals | No sentence is reworded. Only the field's name inside a sentence changes. |

Decided after the review of the issue's first draft: a rule under the field is refused by
the seam's existing sentence for a cell of the wrong kind, which names the cell and not the
field. Naming the field there would reword the refusal of every typed cell of every
instrument, which is no rename. The sentence stays, and the field's own description, which
`_ShowInstrument("cashflow")` shows, says a date only.

## What every existing cashflow sheet changes

One edit, and it fails by name until it is made: the header `payment_date` becomes
`payment_day`, in the ticket or in the template, wherever the sheet has it. A formula that
reads the booked readback by a column's place reads what it read. A formula that finds the
column by its heading looks for `payment_day`. The results' readback is as it was.

## The refusals

In the words the build pins. The first four are the existing sentences under the new name;
the last two are unchanged.

| Entered | Refused as |
|---|---|
| The old header in a ticket | `fields cell (1, 3) is text 'payment_date', expected a field of cashflow: trade_id, trade_date, amount, currency, payment_day, counterparty, description, discount_curve_key` |
| The old header in a template | the same sentence, from `_CreateTradeTemplate` |
| No payment day, in template or ticket | `payment_day is missing, expected a value in the template or a column in the ticket` |
| A payment day in both | `payment_day is supplied by the template and by the ticket, expected by one of them` |
| A rule in a ticket's column | `cashflow_rows cell (1, 3) is text '+5bd', expected date` |
| A rule as a template's value | `values cell (1, 3) is text '+5bd', expected date` |

## Acceptance

- A date under `payment_day` books from the template or from the ticket.
- Every existing example gives the same mark, cash, DV01 and curve columns.
- No readback column moves. The booked readback's fifth field reads `payment_day`; the
  results' first column reads `payment_date`.
- Each refusal above is pinned by a test.
- No work count moves: the field keeps its type, so the seam and the booking take the path
  they took.

## Engineering boundaries and delivery

One pull request from main, this page and its index row in the first commit, the build in
the next. The definition's name and its description; the booking's read of the field; the
booked readback's heading; then every cashflow header in the tests, the host's facts, the
smoke, the lifetime group and the kept workbook cut over; the owning pages, a history row
and a UAT item.

`payment_date` stays a name in use: the trades' resolved date and every results readback
keep it, and the batch's record keeps its own word for the dates it holds. So the cut-over
changes a cashflow's booking header where it finds one, and never a name wholesale.

## Outside this ticket

A rule such as `+1bd` on a cashflow, a payment calendar or an anchor for one; a refusal that
names the field of a wrongly typed cell; any change to a trade's `payment_day`; and the
earlier ticket pages, which describe the header as it was when they were built.
