# Contract codes and dates on one trade ticket

[Pipeline overview](README.md) · [UAT item 4](surface-uat-notes.md#4-contract-codes-and-dates-on-one-ticket)

**Status:** Built in #172, one focused PR stacked on the reviewed prototype PR #171 at
`0803f6f`, the page as agreed on 10 October 2026 with the section at the end saying what
landed; this ticket does not decide how the stack lands on main.

**Suggested PR title:** `feat(trades): resolve codes and dates per ticket row`

## Outcome

Let one ticket keep `contract_code`, `start_date` and `end_date` columns together.
Ordinary monthly trades use the code; BALMO and other partial-month trades supply
precise dates. Choose the effective period independently for every occurrence after
combining its ticket fields with the template. Resolve and encode it once at creation.

Keep the existing signatures:

```text
_CreateTradeTemplate(instrument, fields, values) -> template handle
_CreateTrades(index, fields, trade_rows, template) -> trades handle
```

## Agreed period selection

| contract_code | start_date | end_date | Effective period |
|---|---|---|---|
| `V26` | blank | blank | 1–31 October 2026 |
| `V26` | 12-Oct-2026 | 31-Oct-2026 | 12–31 October 2026 |
| `V26` | 12-Oct-2026 | 20-Oct-2026 | 12–20 October 2026 |
| blank | 12-Oct-2026 | 20-Oct-2026 | Same explicit window |
| `BALV26` | 12-Oct-2026 | 31-Oct-2026 | Explicit window; the code is retained entry text |
| `V26` | 12-Oct-2026 | blank | Fail: incomplete date pair |
| blank | blank | blank | Fail: no period supplied |

Both dates supplied means use the inclusive date window. Neither supplied means
resolve the code with the existing period grammar. Exactly one supplied fails even
when a valid code is present. Reversed or invalid dates fail; there is no fallback.

A complete date pair always wins. Do not test whether it is narrower than the code,
intersect the two periods, or require their months to agree. The code does not constrain
or expand the dates. For example, a retained `V26` beside November dates books November.
The effective dates must still resolve against the supplied index and supported method.

When dates win, a populated code must pass the normal text type check, but is not
parsed or looked up in the schedule. Retain it as entry text, not as a resolved contract.
When dates are absent, an invalid code fails normally. `BALV26` alone does not acquire
an implicit reference date: BAL date-helper behavior is a separate work item.

## Unused cells and template ownership

A true blank cell and exact empty text, including a formula returning `""`, mean
**not supplied only for these three period fields**. An omitted column also supplies
no value. Whitespace is not absence. Nonempty dates use the existing Excel date type;
date text is not parsed and numbers or booleans are not converted to code text.
Excel errors remain errors. Other fields retain their current blank and empty-text
refusals; a zero-quantity row still needs a valid period and normal validation.

Apply this scoped absence policy to template values and ticket cells. Templates remain
partial records: a start date may come from the template and an end date from the ticket.
Assess completeness on the combined trade row, not on the partial template alone.

Field ownership remains based on supplied headers. If a field occurs in both template
and ticket, fail even when one side is blank or both values agree. An unused cell does
not authorize overlap or request inheritance. A template code and ticket dates are
different fields and may coexist; the date pair takes precedence for that row.

Template code grammar must wait until trade creation selects the period form: a reusable
template cannot know which rows will supply overriding dates. Check its populated code's
type at template creation; parse it only for code-selected rows at trade creation. This
deliberately moves a malformed template code's grammar refusal to `_CreateTrades` when
that code is active. Other template field validation stays as it is.

## Seam and resolution boundaries

The existing seam refuses blanks and empty text before binding a field table, and its
text extraction assumes every text column has one text value per row. Resolution then
chooses a single period form from the columns present. Neither assumption supports
this ticket; removing the two-form refusal alone is insufficient.

Extend the instrument-selected field-table path with typed per-cell presence for the
three fields. The library receives typed values and presence, not raw Excel cells,
handle text or sentinel dates that can enter arithmetic. Exact headers, shape checks,
handle resolution and unrelated table types retain their existing contracts. Presence
of a header and presence of a row's value must remain distinct facts.

Ensure absent code cells and empty-text date cells do not displace other text values
or reference cells. Exercise ordinary text and payment-calendar handles on both sides
of these columns. Keep the template's shape-first rule. Record and pin the necessary
schema-aware header/cell validation order in `docs/seam/inputs.md`; permission for an
unused cell must come from its identified field, never from guessing its position.

In resolution, select code or dates per occurrence, retaining original ticket row
identity. Parse only active codes, once per distinct text in first-occurrence order.
Construct effective date windows, expand them into monthly components, and join the
existing observation and encoding path. Preserve input occurrence order, duplicate
occurrences and component ownership when regrouping work by period form.

Refusals must identify the original row and relevant field, including an incomplete
date pair, no period, reversed dates, malformed active code or absent schedule month.
Filtering active rows must not renumber them. Pin failures with both row forms present;
no failed creation publishes a trades handle.

## Retained facts and readback

Retain entered code text separately from resolved component contracts. Keep the existing
trade readback's `contract_code` meaning: the resolved booked component, not the inactive
label and not an Asian's daily pricing reference. Expose the entered text with an
unambiguous label such as `entered_contract_code`, alongside effective component dates.
For absent entry text, use a documented display marker such as `(not supplied)` in the
debug table; it is display-only, never a library value or input default. Use the same
approach if an absent template period value is displayed. No general blank-output
extension or new reader is needed.

The resolved dates remain static as history, valuation date or prices change. Preparation
and evaluation consume the same encoded representation regardless of entry form. They
must not revisit codes, helper formulas or period-selection rules.

## Existing economic rules remain

Period selection is separate from `schedule_method`. A partial-month Asian uses its
eligible observation days and the calendar's pricing references. Expiry-based methods
and IFERC keep their existing whole-month restrictions. This adds no `exact` method.

`quantity_per = month` applies the entered quantity to each covered monthly component,
including a partial month, without prorating. `calday` multiplies by covered inclusive
calendar days, including weekends and holidays. Multi-month dates keep one component
per month; existing observation weights, payment anchors, payment calendars, unit
conversion, lot delta and gross reserves continue from those resolved components.

One index, instrument, route and settlement method per batch remain unchanged. Mixed
methods, units, quantity bases and payment terms retain their already-supported behavior.
Existing market/history identity checks and unsupported-product refusals still apply.

## Acceptance

Use independent worked expectations plus mixed-batch versus singleton comparisons.
Do not use agreement between two shared paths as the only proof.

For a synthetic financial Asian example, use USD/BBL, an index reporting lot of 1,000
BBL, weekday pricing with no holidays, and a schedule that prices all October
observations with V26. All observations are live at 72; every fixed price is 70:

| Row | Code | Dates | Entered quantity in BBL | quantity_per | Component BBL | Mark USD | Live lots |
|---|---|---|---:|---|---:|---:|---:|
| 1 | `V26` | absent | 100 | `month` | 100 | 200 | 0.10 |
| 2 | `V26` | 12–31 Oct | 100 | `month` | 100 | 200 | 0.10 |
| 3 | absent | 12–20 Oct | 10 | `calday` | 90 | 180 | 0.09 |
| Total | | | | | 290 | 580 | 0.29 |

October has 22 eligible weekdays, 12–31 October has 15, and 12–20 October has 7 under
this synthetic calendar. Each row distributes its component quantity over its own
observation days. With `+1bd` and the same weekday payment calendar, rows 1 and 2 pay
2 November and row 3 pays 21 October. Compression must preserve that ownership.

Also cover:

- The selection table with true blanks, formula-empty strings and omitted columns;
  alternating code/date rows and reordered headers, with neighboring text and handles.
- Complete dates with a malformed, unmatched or BAL text label succeed identically to
  dates alone; a nontext populated code still fails. Without dates, bad codes fail.
- A superseded code naming different months does not affect effective dates, contracts,
  observations, payment days, reserves, values or risks; readback distinguishes the text.
- Template code plus ticket dates, template dates plus ticket code, a date pair split
  across template and ticket, and overlap despite an absent period value.
- Both incomplete-pair directions, no period, invalid/reversed dates, missing schedule
  month, earliest original bad row, and unchanged refusals for blanks in other fields.
- Whole months by code and dates give identical economics; strips and a cross-month
  clipped window retain the existing `month` and `calday` quantity meanings.
- Mixed batches match the sum of valid singletons for values, cash, contract/daily risk
  and reserves. Duplicate and zero rows retain normal behavior. Fixing, payment and tick
  transitions match the equivalent explicitly dated trades, with no new tick work.

## Delivery and completion

One PR with the bounded seam extension and its probes followed by the row resolution
and integration changes. Keep private helpers responsible for one task; internal array
layout is an engineering choice. Update work counters and budget tests for creation,
pin unchanged preparation/evaluation work, and state retained-memory changes. Code-selected
rows alone incur code parsing; inactive labels incur none.

Update the instrument field help and `_ShowInstrument`, template and CreateTrades pages,
seam input decision, readback documentation, affected smoke/host fixtures and the kept
workbook together. Replace tests of the old exclusive batch form with the agreed cases;
preserve unrelated refusals. Follow the existing golden policy and run `./check.ps1`.
Add a worksheet block mixing monthly, BALMO and partial-month rows with all three headers,
including formula-empty cells and one clear incomplete-pair refusal.

Update the UAT item to implemented only after review. The original exclusive-form wording
in the earlier period and mixed-field tickets is historical and superseded by this ticket.
No implicit valuation context, BAL parser change, new schedule method, bilateral valuation,
new public signature or general relaxation of blank-cell handling belongs in this PR.

## As built

Built in #172. The pages are [create-trades.md](../../library/trades/create-trades.md),
[trade-template.md](../../library/trades/trade-template.md), the Show page's three period
cells, [read-handle.md](../../library/utilities/read-handle.md) and
[inputs.md](../../seam/inputs.md) decision 43.

The seam: `Field` carries `may_be_unsupplied`, true for the three period fields and no other,
and the field body crosses as it arrived, its cells checked after its headers so that the
field a header names says whether a blank or an empty text means a row that supplied nothing
or a cell that fails its type, `trade_rows cell (2, 4) is blank, expected number` where the
mixed range's words stood; the cells are placed among the body's texts by one count over
the cells, so an absent code or an empty-text date displaces no text and no handle, and
`FieldValues.supplied` carries a read-only mask per such field beside the values of the rows
that supplied one, never a sentinel. The template keeps `names`, the fields its row named and
owns, apart from `defaults`, so a blank period cell owns its header and supplies no row;
`contract_code` is text there, the grammar reading it at `_CreateTrades` for the rows that
book by it.

The resolution: `_the_periods` reads the three fields as each row holds them, the template's
value on every row or the ticket's cells, and chooses per row, a complete pair winning, a code
otherwise, half a pair or no period refused by the first such row from the top and named with
the field and the row; the codes of the rows that book by code are read once per distinct text
in first-occurrence order, the dated rows' months come from their dates, the components stand
in row order whichever form each row took, a missing schedule month is named by the row's own
form, and the dated components are clipped to their rows' dates; `ticket_codes_read` counts the
distinct codes read, none for a batch of dated rows. The batch keeps `code_entered` and
`entered_codes` apart from the contracts; the kernel, the encoding, the preparation and the
evaluation are untouched. The readback adds `entered_contract_code` before `start_date`,
`(not supplied)` where a row entered none, and the template's spill shows the same words under
an unsupplied period field; both are display and no value.

Pinned: the ticket's table on one ticket, Z26 for its V26, with a BAL label and a code naming
another month beside dates; the refusals by row, the earliest faulty row named; template and
ticket splits of the three fields and the overlap of an owned blank header; the seam's masks,
neighbouring text and handles, formula-empty cells, the blank elsewhere in its field's words;
the acceptance example valued end to end, 580 and 0.29 lots, the singletons summing and a
whole month by dates the code's own; the ledgers at five rows and two thousand; the smoke's
block, the host's fact and the kept workbook's block with its eleven older reads moved a
column. The UAT item stays as the owner left it, implemented only after review.
