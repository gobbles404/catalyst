# Payment day as a date or a rule

**Status:** Built in #214, 21 October 2026, one feature PR against main implementing
[issue #213](https://github.com/gobbles404/goosedove/issues/213) in four commits: the
shared validation first, then the field, then the host, the smoke, the lifetime and the
kept workbook, then the pages. The quoting and named-curve stack is merged. This work is
independent of issues #211 and #212.

## Purpose

Allow a financial `fixed_float` to specify payment either as an exact date or as
the existing date-offset rule. The desk can compute or agree a payment date
outside the library when a confirmation's terms do not fit the rule grammar.

Replace the field `payment_time_lag` with `payment_day`. This is one field with
two accepted input forms. Creation resolves either form to the existing
`payment_date` arrays; preparation, evaluation and risk arithmetic continue to
consume those dates.

No worksheet function signature changes. The instrument field name and type
change, and existing templates and tickets migrate without an alias.

## Field and entry contract

| Field | Type shown by `_ShowInstrument` | Required when | Meaning |
|---|---|---|---|
| `payment_day` | `date or text` | `settlement_method = financial` | An exact date for every component of the row, or a rule applied separately to each component |
| `payment_holiday_calendar` | Existing holiday calendar handle type | `settlement_method = financial` | Used by business-day instructions; retained but unused for an exact date |

An exact date is an Excel date or a whole-day serial within the existing sheet
date range. Text is always a rule, never parsed as a date. Rules use the current
grammar unchanged, including chains such as `+3em+25cd-1bd+1bd`.

The seam distinguishes the forms by cell type, once. It refuses booleans,
fractional-day serials, invalid dates, blanks and empty text using the existing
cell-qualified errors. Text such as `25-Feb-2027` fails the rule grammar. The
library receives typed date values, rule texts and their row positions; numerical
code does not repeatedly inspect cell types or parse mixed object arrays.

The field belongs to either the template or the ticket, never both. There is no
override or fallback. A shared rule or date can live in the template. A batch
mixing rules and dates supplies the whole `payment_day` column in the ticket,
with a value in every row. Supplying the field under physical settlement remains
an error, as supplying a lag is today.

`payment_date` remains the name of the resolved date in readback. Show the entered
`payment_day` beside it, preserving a date as a date and a rule as text. Apply the
same field contract to trade templates and quote templates.

## Payment semantics

| Booking | Entered `payment_day` | Resolved payments |
|---|---|---|
| One month | `+2bd` | Two payment-calendar business days after its last observation |
| `CAL27` | `+2bd` | The rule applied to each month's last observation, normally twelve monthly payment dates |
| One month | 25 February 2027, entered as a date | That exact date |
| `CAL27` | 18 January 2028, entered as a date | All twelve monthly components pay together on that date |

A rule's anchor stays each component's last observation: expiry under futures
`lastday`, the penultimate observation under `penultimate`, the last observation
under `last3day` or `asian`, and publication under IFERC `lastday`.

An explicit date must be strictly after every observation of the row. For a strip
this means after its final observation across all months. Equality is refused.
Name the offending row, entered date and relevant last observation in the error.
An exact Saturday, Sunday or holiday remains exactly that date; do not roll it
using the payment calendar.

A valid date on or before `as_of` follows the existing paid treatment. Observation
dates, fixing state, monthly quantities and contract exposures do not move when a
payment is deferred. A strip with an exact date retains its monthly components;
their amounts become cash together, and the total is their sum, not twelve times
one selected month's amount.

Payment groups keep today's keys: contract and resolved payment date, plus
`discount_curve_key` for bilateral groups. The input form is not a grouping key.
A rule and a date that resolve to the same day can group together when those
economic keys match. Different curve keys remain separate even when contract and
payment date match.

To specify different exact payment dates for the months of a strip, book one row
per month. A per-component payment schedule attached to one row is outside this
ticket.

## Worked valuation acceptance

Use a synthetic futures index quoted in USD/MMBtu, with a quantity specification
of one MMBtu per unit. F27 expires Friday 29 January 2027 under `lastday`; these
are synthetic schedule dates, not NYMEX contract specifications. The payment
calendar closes weekends only.

Value on 15 December 2026. Both bilateral rows receive 10,000 MMBtu of F27,
fixed at 2.65 and quoted at 3.10, and select SOFR. The curve starts on the
valuation day and supplies factors 0.990 on 2 February and 0.985 on 25 February.
The undiscounted amount per row is `10,000 * (3.10 - 2.65) = 4,500`.

| Row | Entered `payment_day` | Resolved date | Mark | Signed DV01, USD per bp |
|---|---|---|---:|---:|
| 1 | `+2bd` | 2 February 2027 | 4,455.00 | `-49 / 365 * 4455 / 10000`, approximately -0.0598068493 |
| 2 | 25 February 2027 as a date | 25 February 2027 | 4,432.50 | `-72 / 365 * 4432.5 / 10000`, approximately -0.0874356164 |

The batch mark is 8,887.50 and cash is zero. The second row has larger DV01
in absolute magnitude; both signed DV01s are negative.

After F27 fixes at 3.10, value on 3 February with a new history and a curve
anchored on that day. Row 1 has cash 4,500 and mark zero. Row 2 remains unpaid:
its mark is `4,500 * DF(3 February, 25 February)` and it still has DV01. Both
rows have zero live commodity delta. Test the cash cutoff immediately before,
on and after an explicit payment date; on the date, the amount is cash, with no
remaining DV01 on that payment.

## Quoting acceptance

An exact date in a quote template applies to every month requested and must
follow the request's last observation. Reuse the existing curve selection,
coverage and past-payment rules; payments on or before `as_of` use factor one
in quoting.

A quote template holding an exact date can be reused for any request whose last
observation is strictly before that date; refuse a request whose last observation
is on or after it. The comparison is with the observation date, not the end of
the delivery period. State this limit on the quote-template page; the template
is not restricted to a single deal.

Use two synthetic months with prices 3 and 5, equal monthly quantities, and one
common future payment date with DF 0.98 on the selected curve. The fair quote is:

```text
(0.98 * 3 + 0.98 * 5) / (0.98 + 0.98) = 4
```

The common factor cancels; do not discount the returned price itself. Book the
same two-month strip at 4 with that payment date and verify zero mark. As an
independent off-market example, at fixed price 3.5 and 10,000 MMBtu per month,
the total undiscounted amount is 10,000 and the mark is 9,800. Its mark and DV01
still depend on the payment date and curve. Preserve the existing normalized
weight arithmetic, including its behavior for very small positive factors.

## Implementation boundaries

| Owner | Work |
|---|---|
| Instrument definition and Excel binding | Add the date-or-text field type and its one-pass column binding; rename the field and its required conditions; retain row positions for mixed columns |
| Template field reader | Accept either typed form, validate rule text with the existing grammar, retain the entered value for readback |
| Trade resolution | Broadcast exact dates onto their rows' components; shift only rule-based components with the existing helper; validate dates against observations before publishing |
| Payment terms and readback | Retain entered instructions and calendars, and the resolved date per component; fill the mixed column using its per-cell kinds, preserving dates and text; label it `date or text` in the read-handle page's type table and cover both cell kinds in the host's typed readback tests |
| Quoting | Resolve either form under the quote template and feed existing payment factors and price weighting |
| Preparation and evaluation | Consume the existing resolved dates and group ownership; no new payment representation or valuation path |

Make the shared after-the-last-observation validation a separate first commit
within this feature PR. Booking and quoting should call one owner for that rule,
while retaining their caller-specific error context and existing failure order.
This first commit preserves current behavior, answers and work counts and is
reviewable on its own. Implement the new field and its migration in the following
commit or commits of the same PR.

Keep the extraction limited to the shared validation; do not introduce a general
payment-rule framework. Internal names and retained types may change where they
describe the new input, while resolved date semantics remain unchanged.

Work counters continue to describe actual work. A date-only batch reads zero
payment rules and performs zero payment shifts. A mixed batch counts only the
distinct rules and rule/calendar applications it uses. Rule-only counts remain
as today. A price tick must not parse, resolve or shift payment instructions.

## Acceptance and delivery

Use the worked cases above, plus focused checks for:

- Mixed date/rule cells in one ticket, and each form supplied by a template;
  typed readback, exact field names, and template/ticket overlap refusal.
- Equivalent rule/date entries coalescing under the same contract, date and curve
  key; the same contract and date staying separate under different curve keys.
- A monthly strip paid by rule and by one exact date, preserving its contract
  exposures; one row versus a batch, duplicates counted, and reordered rows.
- An IFERC publication anchor and an Asian component's last observation, using
  existing fixtures where possible; no special anchor for literal dates.
- Exact weekend/holiday dates; equality with the final observation; an earlier
  date on a strip; physical settlement; invalid cell types and date-like text.
- Unchanged rule-only values, risks and work counts; date-only and mixed counts;
  missing curve coverage still refused by the existing evaluation or quote path.

Migrate the old header in source, current help and documentation, test fixtures,
host replay, smoke, lifetime formulas and the kept workbook. The old
`payment_time_lag` header fails as unknown; no compatibility alias. Historical
tickets remain historical rather than being rewritten to claim the new field
already existed.

Keep the workbook demonstration small: the mixed two-row example with its
readback and values, plus the monthly-versus-common-date strip comparison. Pin
the quote and lifecycle arithmetic in tests. Extend a lifetime scenario only if
the implementation introduces a transition not already covered.

Update the owning instrument, creation, quoting, readback and seam pages for
their changed contracts, and add the packet README and UAT entry. Link to owners
instead of copying the same rules across pages. Run the full repository gate and
state the work counts before and after in the PR.

## Outside this ticket

No second payment field, conditional date grammar, modified-following operator,
invoice logic, payment-schedule handle, per-component date list on one ticket
row, cashflow-instrument change, or multi-index trade support. The existing
`util_ShiftDate` signature and grammar stay as they are.

## Completion

The desk can book or quote a financial fixed_float using either form of
`payment_day`, inspect the entered instruction and resolved dates, and follow
the existing preparation, evaluation and reporting pipeline. The acceptance
numbers hold, current callers are migrated, and rule-only behavior is unchanged.
