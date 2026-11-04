# Compound date offsets for utilities and trade payments

[Pipeline overview](README.md) · [UAT item 9](surface-uat-notes.md#9-date-offsets-from-text) · [Original date utility](date-offset-utility.md)

**Status:** Built in #181 on `claude/compound-offsets`, stacked on PR #180 at `2d0e2f7`, the
reviewed surface, 12 October 2026, the page as the ticket; the [As built](#as-built-181)
section at the end says what was built and what was not. This extends #171's utility and
the existing trade payment rule together, and does not claim either has shipped.

## Outcome

Accept a sequence such as `+3em+25cd-1bd+1bd` in both `util_ShiftDate` and
`payment_time_lag`. Apply each instruction to the preceding result, strictly left
to right, using one shared library parser and date calculation. The worksheet
signatures and instrument field names stay unchanged.

```text
util_ShiftDate(date, offset, [holiday_calendar]) -> date

_CreateTradeTemplate(instrument, fields, values) -> template handle
_CreateTrades(index, fields, trade_rows, template) -> trades handle

payment_time_lag = "+3em+25cd-1bd+1bd"
payment_holiday_calendar = an existing holiday-calendar handle
```

The utility returns a date directly. Trade creation resolves and retains each
component's payment date once; preparation and evaluation consume that date.

## String and calendar rules

An offset contains one or more consecutive instructions. Each instruction is an
explicit `+` or `-`, a whole nonnegative count in ASCII digits, and `bd`, `cd` or
`em`. Suffixes are case-insensitive and leading zeros are accepted. Consume the
entire string: no spaces, unsigned instructions, decimals, unsupported suffixes,
parentheses or trailing text.

| Suffix | Operation on the preceding result |
|---|---|
| `bd` | Move the signed number of business days, excluding the starting date. Weekends and the supplied calendar's holidays are skipped. Zero leaves the date unchanged, even if closed. |
| `cd` | Add the signed number of calendar days. |
| `em` | Select the last calendar day of the month the signed count moves to. `+0em` means the current month's end; `+3em` means the end of the month three months ahead. |

The same supplied holiday calendar serves every `bd` instruction. `cd` and `em`
do not use it. Utility omission still means weekdays with no additional holidays;
the trade's existing required payment-calendar field remains required. A supplied
blank or invalid handle still fails, including for a rule containing no `bd`.

Order is part of the rule. Do not net, reorder or cancel instructions. In
particular, `-1bd+1bd` preserves an open date but moves a closed date to the next
business day. There is no automatic final roll: a chain ending in `cd` or `em`
may deliberately leave a weekend or holiday date. Use explicit `bd` instructions
when a roll is wanted; do not add a new refusal merely because the result is closed.

## Trade integration

Both entry points use the same grammar and operations, including signed and zero
instructions. This supersedes the old payment parser's positive-only `+Nbd`
restriction and the original utility ticket's exclusion of compound strings.
Single positive `+Nbd` payment rules retain their existing dates.

Preserve the current anchors:

- Futures-index components start from their last observation date, as resolved by
  their schedule method.
- IFERC components start from their publication date, their one observation, since
  [iferc-publication-payment-anchor.md](iferc-publication-payment-anchor.md); until then
  from their schedule's last trading date.

Apply the existing financial check to the **final payment date**: it must be
strictly after the group's last observation date. Negative or zero instructions
are valid steps; they do not permit a payment before its final price exists.
There is no new `as_of` dependency or implicit anchor selection.

Rules and payment calendars can already vary by trade row; retain that behavior
and the strict template/ticket overlap rules. A strip applies the chain separately
to each component's own anchor. Compression continues to use resolved payment
dates, not rule text: equivalent chains can share a group, different dates cannot.

Retain the entered rule text per occurrence and show it under `payment_time_lag`
in `util_ReadHandle`, beside the existing resolved `payment_date`. The current
`PaymentTerms.lag_days` integer and the spill's reconstructed `+Nbd` text cannot
represent a compound rule; replace that assumption consistently. Internal record
names and layout are engineering choices. No extra public handle or spill column
is needed.

## Worked acceptance

These are synthetic date examples, not exchange-calendar prescriptions. Calendar
**H** excludes weekends and **25 December 2026 only**. With H, the requested chain
from 12 August 2026 is:

| Step | Result |
|---|---|
| Start | 12-Aug-2026 |
| `+3em` | 30-Nov-2026 |
| `+25cd` | 25-Dec-2026, a holiday in H |
| `-1bd` | 24-Dec-2026 |
| `+1bd` | **28-Dec-2026** |

Additional independent expected answers:

| Start | Rule | Calendar | Expected |
|---|---|---|---|
| 12-Aug-2026 | `+3em+25cd-1bd+1bd` | Omitted | 25-Dec-2026 |
| 12-Aug-2026 | `+003EM+025cD-01BD+001bd` | H | 28-Dec-2026 |
| 9-Oct-2026, Friday | `-1bd+1bd` | Omitted | 9-Oct-2026 |
| 10-Oct-2026, Saturday | `-1bd+1bd` | Omitted | 12-Oct-2026 |
| 30-Jan-2026 | `+1cd+0em` | Omitted | 31-Jan-2026 |
| 30-Jan-2026 | `+0em+1cd` | Omitted | 1-Feb-2026 |
| 31-Jan-2028 | `+1em+1cd` | Omitted | 1-Mar-2028 |
| 10-Oct-2026 | `+0bd+0cd` | Omitted | 10-Oct-2026 |
| 9-Oct-2026 | `+1cd` | Omitted | 10-Oct-2026, with no automatic roll |

For trade acceptance, use a synthetic financial futures-index fixture with
last observation/anchor **9-Oct-2026** and an explicit weekday-only payment calendar:

- `+1bd` and `+3cd` both pay **12-Oct-2026** and compress together when the other
  group facts match. `+4cd` pays **13-Oct-2026** and remains a separate group.
- `+0em-1bd+1bd` pays **2-Nov-2026**.
- `+1cd` pays **10-Oct-2026**; creation does not silently move it to Monday.
- `+1bd-1bd` returns to **9-Oct-2026** and fails the existing payment-after-observation
  check. A utility may return that date; a payment for this fixture may not.

Also pin an IFERC example against its last-trading anchor and later publication
date, including a computed payment on publication day that remains refused. Check
mixed rule/calendar rows, a multi-month strip, template versus ticket entry,
duplicates, and batch versus singleton results. Use hand answers for payment
dates, then verify unchanged cash roll and bilateral DF lookup at those dates.
Also compare a compound utility call with the same single steps called in sequence;
this supplements the independent expected dates above.

## Validation and implementation boundaries

Parse syntax completely before date execution. Malformed later instructions must
fail rather than leaving a partial result. Name the full input and failing
instruction or character position; trade failures also identify the field and
original ticket row under the existing attribution conventions. Grouping by rule
or calendar must not replace the first offending ticket row with alphabetical or
group-processing order.

Keep the current protection against huge counts before integer conversion and
date arithmetic, allowing long leading-zero prefixes. Each explicit step's result
must remain within **1900-03-01 through 9999-12-31**. Reject an out-of-range step
even if a later step would return inside the range. Internal month-end arithmetic
may temporarily use the following month's first day: `9999-12-31` with `+0em`
still succeeds. Reject junk between valid tokens, trailing signs, non-ASCII digits,
overflowing counts and invalid intermediate dates without clipping or partial output.

Share parsing and execution in the neutral date helper, with trade-specific anchor
selection and payment validity kept in trades. No new seam type is required.
Resolve each distinct rule once per creation call and reuse its parsed steps within
that call. Apply steps to arrays of component anchors grouped as needed by rule
and calendar. Loops over instructions are appropriate; loops over individual
dates, calendar days or trades to perform the numerical shifts are not.

Measure parsing work and date operations against the number of distinct rules,
instructions, calendars and affected components. Preserve one path for one/many
trades. A quote or discount-curve tick must perform no parsing or date shifts;
neither should re-preparation against a new history rebuild static payment dates.

## Delivery

Ship the shared helper and both consumers in one focused PR. Update instrument
rule/help text, utility and trade pages, debug readback, relevant tests and work
budgets. Add the requested holiday chain to the kept workbook and smoke/host
coverage, plus a trade using it. Update this ticket, the pipeline README and UAT
item 9 when implemented. Run the full gate; report meaningful work counts before
and after, leaving existing goldens untouched.

This PR does not choose or merge exchange, clearing or currency holiday calendars;
change payment anchors or same-day fixing policy; introduce named rolling
conventions, custom weekends or intraday rules; or change BAL helpers, risk reports
or support for mixed routes. Calendar contents remain explicit caller inputs.

## As built (#181)

Built on `claude/compound-offsets` above #180's `2d0e2f7`, one pull request; [shift-date.md](../../library/utilities/shift-date.md) is the utility's page and [create-trades.md](../../library/trades/create-trades.md) the payment rule's.

**The shared helper.** `src/catalyst/index_definitions/date_offsets.py`: `read_offset(where, offset)` reads an offset whole into its instructions, text, unit and signed count each, one instruction at a time from the start; where none begins, past the first, the refusal names the character reached and the text from there, `offset is '+1bd+2xd', expected one or more of a sign, a whole count and bd, cd or em, such as +1bd, -1bd, +7cd, +0em or +3em+25cd-1bd+1bd; from character 5, '+2xd' begins with no instruction`; a count of more than seven significant digits is refused by its digits, the instruction named when the offset has more than one. `shift_days(days, steps, holidays)` applies the instructions in turn to an array of days, one numpy operation each, and after each one look at the sheet's calendar, keeping per day the first instruction that left it and the day it made; nothing is netted, reordered, rolled or clipped. `shift_date` is the utility's one-day call, refusing a stray day with its instruction when the offset has more than one.

**The two consumers.** `util_ShiftDate` reads and applies through the helper, its help naming the chain. `payment_rule_of` in `trades/template.py` reads a payment rule through `read_offset` in the field's words, so `+0bd`, `+01bd`, `+2BD` and chains read; the template's bound of 2,113,146 business days is gone, the seven-digit rule standing in its place. `_the_payment_terms` in `trades/resolution.py` reads each distinct rule once, groups the components by rule and by calendar object, applies each rule to each group's anchors at once through `shift_days`, and refuses the first component in ticket order whose rule left the sheet's calendar, naming the row, the anchor, the day and the instruction when the rule has more than one, whatever order the groups were made in. The anchors stand: a futures index's last observation day by its method, an IFERC index's last trading day. The kernel's rule that every final payment day follows its group's last observation stands, so `+1bd-1bd` and an IFERC `+1cd` onto publication day are refused there. `PaymentTerms.lag` keeps the rule as written per occurrence where `lag_days` kept an integer, and `util_ReadHandle` shows it under `payment_time_lag` beside `payment_date`. Two counters: `payment_rules_read`, the distinct rules, and `payment_shifts`, the instructions applied, each over one rule's components on one calendar.

**Where it is checked.** `tests/unit/test_date_offsets.py`: the requested chain through H instruction by instruction, the ticket's nine answers, an offset read into its instructions, digits in a later instruction, an instruction leaving the sheet refused though the next returns, eleven chains malformed late, and a property that any chain of up to six instructions is its instructions applied one by one. `tests/unit/test_utilities.py`: the chain through the seam on a calendar closing Christmas Day and without. `tests/unit/test_trade_template.py`: the grammar's refusals in the field's words and six forms accepted. `tests/unit/test_create_trades.py`: the ticket's fixture with V26 expiring Friday 9 October 2026, `+1bd` and `+3cd` one group on the 12th, `+4cd` the 13th apart, `+0em-1bd+1bd` 2 November, `+1cd` the Saturday kept, `+1bd-1bd` refused by the kernel; rules and calendars by row, a strip per component, template against ticket, a repeat, batch against singleton; the first offending row named across groups made in another order; the IFERC chain from last trading, `+3cd` one group with `+3bd`, `+1cd` onto publication day refused. `tests/unit/test_trade_valuation.py`: the chain read back as written beside its day. Budgets: `test_seam_budgets.py` reads once and applies once with one look per instruction, the chain four, the same numpy at one day and two million; `test_seam_allocation.py` within three slacks, the chain four; `test_trade_creation_budgets.py` the rule read once and applied once per calendar, the two counters. The smoke, the host and the kept workbook hold the chain and a trade paying by it.

**Not here.** No exchange, clearing or currency calendar chosen or merged; no change to the anchors or to same-day fixing; no named rolling convention, custom weekend or intraday rule; no change to the BAL helpers, the risk reports or mixed routes. The host counts no business-day arithmetic, numpy's `busday_offset` being dispatched in C where the ledger cannot see it, as before.
