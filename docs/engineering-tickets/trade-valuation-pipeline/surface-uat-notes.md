# Trade surface UAT notes

[Pipeline overview](README.md) · [Bilateral discounting and DV01](bilateral-discounting-and-dv01.md)

Running list started 8 October 2026 while testing the trade prototype in Excel.
Record observations and decisions here before turning them into implementation tickets.

| Item | Owner direction | Status |
|---|---|---|
| 1. Delta reporting | Report delta in **lots**, using one explicitly designated specification per index, independently of trade entry units. | Agreed; [engineering ticket](lot-delta-reporting.md) drafted |
| 2. `trade_id` | Treat it as an **alphanumeric identifier**, rather than a quantity. | Proposed; entry details to confirm |
| 3. Start/end date helper inputs | Keep the worksheet arguments unchanged; allow dates as well as period labels to feed the trade's date fields. Preserve case-insensitive BAL entry. | Requested; date passthrough interpretation below; BAL labels already supported |
| 4. Ticket period fields | Allow `contract_code`, `start_date` and `end_date` together; complete dates take precedence over the code. | Requested UX; proposed row-level rules below |
| 5. Asian pricing references | Average the daily nearby reference supplied by the index schedule/calendar; it need not match the booked month. | Agreed; [engineering ticket](calendar-driven-asian-references.md) drafted |
| 6. Readable index names | Keep the existing short `name` and add a human-readable `display_name` on the index. | Agreed direction; implementation ticket pending |
| 7. Delta by observation time | Retain day, month and year lot-delta vectors across methods and payment groups; select the bucket in `_ReportDelta`. | Agreed, updated 9 October; [engineering ticket](daily-risk-vector.md) revised; quarters excluded |

## 1. Delta reporting

For the fully live ETE example, `1 LOT`, `1000 BBL` and `42000 GAL` each represent
one lot of exposure. Three positive trades entered together represent three lots.

With a CENT/GAL quote and USD settlement, the current encoding produces a coefficient
of 420 USD per one-cent/gallon move per equivalent trade. That coefficient is useful
for valuation, but it is not the lot delta the owner expects to read. Preserve the
pricing arithmetic and distinguish its monetary sensitivity from the requested lot view.

The agreed reporting basis is one designated existing specification on the index.
Each entry specification already has its own size and unit; the reporting selection is
independent of which row a trade uses. Remaining Asian lot delta follows the live
observation weights. See [Report trade delta in index-defined lots](lot-delta-reporting.md)
for the recommended selection mechanism, calculation and acceptance cases.

The relationship to discounted monetary sensitivity remains a bilateral design choice.
The pending bilateral ticket's report contract must incorporate that distinction before
it is finalized.

## 2. Trade identifiers

In the reviewed prototype through #163, `trade_id` already accepts alphanumeric text,
text containing only digits, and punctuation. A numeric Excel cell is rejected as
the wrong type; accepting that cell would be a separate surface decision.

The proposed meaning of `trade_id` is an identifier that can contain letters and digits,
for example `ETE001`. Do not infer a letters-and-digits-only restriction, uniqueness rule
or automatic numeric-cell conversion from this note. Numeric Excel cells versus text
identifiers, preservation of leading zeros, and any character restrictions remain to
be clarified if relevant to UAT.

## 3. Dates and period labels through the same helpers

Keep the existing worksheet call shapes:

```text
util_StartDate(period, [reference_date]) -> date
util_EndDate(period, [reference_date])   -> date
```

Interpret the requested date support as accepting an actual Excel date in the first
argument and returning that date unchanged from either helper. Period labels keep their
existing meanings. This widens accepted input types without adding or reordering arguments;
engineering must provide the seam support rather than assume date-or-text is supported today.
Do not introduce parsing of date strings such as `10/08/26`.

| First input | Reference date | Start helper | End helper |
|---|---|---|---|
| Excel date 8-Oct-2026 | omitted | 8-Oct-2026 | 8-Oct-2026 |
| `v26` | omitted | 1-Oct-2026 | 31-Oct-2026 |
| `balv26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |
| `BALV26` or `BalV26` | 8-Oct-2026 | 8-Oct-2026 | 31-Oct-2026 |

BAL already works case-insensitively in the prototype. Preserve that behavior and its
explicit reference requirement. A valid reference supplied with an ordinary label or an
explicit date does not change the result; supplied arguments still undergo normal validation.
Keep the helpers deterministic and nonvolatile, with existing missing/blank distinctions.

The helper outputs populate the ticket's `start_date` and `end_date` columns. Today's
prototype requires omitting `contract_code`; item 4 proposes allowing it alongside them.
A BAL label can feed both helpers; independently entered start and
end dates feed their respective helpers. The booking reference stays fixed as market
`as_of` advances. These formulas do not snapshot a changing reference cell.

Acceptance should cover the table, existing BAL refusals, date validation through the seam,
and one worksheet example containing ordinary labels, BAL labels and explicit dates. This
is a helper-input extension; the separate ticket-period change is specified below.

## 4. Contract codes and dates on one ticket

The ticket should support all three period columns together. Resolve the period **per
row**, after combining the template and ticket, without changing `_CreateTrades`' arguments.
This replaces the prototype's requirement for one exclusive period form across the batch.

| `contract_code` | `start_date` | `end_date` | Proposed resolution |
|---|---|---|---|
| `V26` | blank | blank | Full October 2026 from the code |
| `V26` | 8-Oct-2026 | 31-Oct-2026 | Explicit dates take precedence |
| blank | 8-Oct-2026 | 31-Oct-2026 | Explicit dates |
| `V26` | 8-Oct-2026 | blank | Fail: incomplete date pair |
| blank | blank | blank | Fail: no period supplied |

A complete date pair selects the period; the code does not constrain or expand it.
Invalid or reversed dates fail rather than falling back to the code. With neither date,
the code must resolve normally. Missing columns can still supply neither date; retaining
all three columns requires a bounded allowance for unused period cells, not a general
relaxation of required-field validation.

Proposed inactive-code handling: require text when populated, but skip code parsing and
schedule lookup when dates select the period. This lets a BAL entry label stay on the
ticket beside its helper-generated dates. Any retained entered code must be clearly
distinguished from the resolved component contracts; readback must make the effective
dates and contracts unambiguous.

Before implementation, settle one worksheet detail: whether formula-generated empty text
(`""`) counts as absent in these three fields as well as a truly blank cell. They are
different inputs today; do not silently broaden blank handling throughout the seam.

Keep the refusal of duplicate fields across template and ticket. Dates still resolve
against the supplied index; partial-month method restrictions and zero-quantity validation
still apply. Resolution and encoding happen once at creation, with no new market-date
dependency. Mixed code/date rows must match their separately created singletons, including
the same dates entered with and without a superseded code.

## 5. Asian crude observations across a futures roll

The general correction is specified in [Calendar driven Asian pricing references](calendar-driven-asian-references.md):
one calendar-driven rule across supported commodities, independent of the booked month.

UAT of a December 2026 Asian fails at creation: the trade's December component is Z26,
but 1 December is a day of F27 prices in its index calendar. The downstream results
error propagates that creation failure.

The requested economics are supported by the exchange examples. [ICE WTI 1st Line](https://www.ice.com/products/6753542/WTI-1st-Line-Future)
averages NYMEX front-month WTI settlement prices over the production month.
[CME WTI Financial Futures, chapter 510](https://www.cmegroup.com/rulebook/NYMEX/5/510.pdf)
likewise averages first-nearby settlements over the calendar month. December names the
averaging period; its observations can reference January futures and then February futures.

In prototype `14130240`, `encoding._the_references` already derives the reference from
each observation date, then refuses it when it differs from the component's named contract.
The [first Asian slice](asian-trades.md) deliberately restricted support to a month whose
observations all reference that same contract. This UAT case requires extending that scope.

Agreed approach for this daily-prompt Asian:

- Keep the booked month/window, quantity, fixed leg and payment ownership together.
- Resolve each observation's pricing reference from the index calendar, even when that
  differs from the booked month. Preserve the own-contract checks for expiry-based methods.
- Apply history by observation date; project live observations from their resolved futures
  references. Attribute contract delta to those references, not the averaging-month label.
- Retain the date/reference mapping at creation. A tick reads the distinct live references
  and does no observation expansion or fixing work.

The existing dated slots already distinguish payment groups from pricing references.
The one-settle-per-day history can support this case when its daily reference convention
matches the swap's. Pin the roll boundary explicitly: today's calendar includes the
expiring contract on its expiry day and switches the following day. Do not apply that
convention indiscriminately to other products: the
[Brent leg of ICE's WTI/Brent BALMO specification](https://www.ice.com/products/31687082/Crude-Diff---WTI-1st-Line-vs-Brent-1st-Line-Balmo-Future)
explicitly rolls on expiry day.

Acceptance needs a calendar-month example spanning a real futures roll: observations on
both sides and on expiry day, separate forward prices and deltas, partial fixing, payment
and cash, and mixed batches with existing futures and month-aligned Asians. Readback must
distinguish the booked period from its pricing references. No signature change is indicated
by this research; this note records the extension, not an implemented fix.

## 6. Human-readable index names

Retain the index's existing `name` as the short label used by the current market and
price-vector matching. Add a separate `display_name` supplied when creating the index,
stored on the index and exposed alongside `name` through `util_ReadHandle`.

| `name` | Illustrative `display_name` |
|---|---|
| `WTI` | West Texas Intermediate crude oil - NYMEX |
| `NG` | Henry Hub natural gas - NYMEX |

Readers or selectors can present both together so a user unfamiliar with another desk's
shorthand can identify the market. This is descriptive metadata; pricing and binding
continue to use the existing identifiers and object references. Do not infer conventions
or product behavior from the display text, or rename the existing `name` field as part of
this addition. Exact argument placement and whether the new value is required remain for
the implementation ticket; no creator signature has changed in this note.

## 7. Observation dates appear out of order in the results readback

Corroborated on PR #165 head `f1f1b916` through `_CreateTrades`, `_PrepareTrades`,
`_EvaluateTrades` and `util_ReadHandle`. The result readback preserves the encoded slot
order: booked contract in schedule order, then payment date, then observation date within
that payment group. `schedule_method` is not a sort key. Different methods often resolve
different payment dates, which can make the displayed order look method-driven.

Synthetic reproduction: Z26 expires 31 December 2026; the pricing/payment calendar closes
25 December and 1 January as well as weekends. Book a 22-BBL December Asian and a 3-BBL
penultimate, both with `+1bd`. The pen observes 30 December and pays 31 December; the Asian
observes the month's 22 pricing days and pays 4 January 2027. The readback begins:

| Observation date | Payment date | Source in this example | Live exposure in BBL |
|---|---|---|---:|
| 30-Dec-2026 | 31-Dec-2026 | Penultimate | 3 |
| 1-Dec-2026 | 4-Jan-2027 | Asian | 1 |
| 2-Dec-2026 | 4-Jan-2027 | Asian | 1 |

The source labels above explain the example; the compressed result does not contain a
method column. Reversing the ticket rows leaves the spill identical. Giving the pen a
`+2bd` lag makes both trades pay 4 January, creates one payment group, and produces 22
chronologically ordered observation rows; the 30 December exposure is then 4 BBL.

This corroborates the displayed ordering, not a valuation or risk error. The owner clarified
the desired view: one observation date with its net live delta, irrespective of source
method or payment group. An Asian contribution of 1 lot and a pen contribution of 3 lots
on one day should appear as 4 lots on that day. Sorting the existing rows alone is insufficient.

Agreed direction, refined 9 October: retain the daily vector and its calendar-month and
calendar-year aggregates at preparation, carry all three into results, and select the
saved view with `_ReportDelta(results, [bucket = "day"])`. Allowed buckets are `day`,
`month` and `year`; quarters are excluded. Sum each slot's own live lots, never the
repeated contract-total columns from the debug spill. The reader selects and formats
saved values, without numerical aggregation or reading the debug table.

Buckets follow observation dates, independently of payment dates, booked months and
pricing-contract labels. Preserve references on the daily axis and payment ownership
for valuation/cash. Keep zero entries as dates fix and the axes stable for the batch.
This is reporting aggregation; there is no new index-level or valuation-parameter
resolution setting. The [revised ticket](daily-risk-vector.md) retains the existing
aggregate reports and raw debug layout, and replaces its earlier daily-only reader
proposal. This note and ticket specify the next change; they do not implement it.
