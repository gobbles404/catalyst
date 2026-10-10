# Add counterparty and marketing reserve to fixed_float

[Pipeline overview](README.md) · [Bilateral plan](bilateral-discounting-and-dv01.md) ·
[UAT notes](surface-uat-notes.md) · [Existing reserve totals](reserve-totals.md)

**Status:** Built in #175, 10 October 2026, stacked on PR #174 at `29fe38f`, awaiting review.
[As built](#as-built) at the foot records what the build settled. This ticket does not
authorize landing the prototype stack.

**Suggested PR title:** `feat(trades): add counterparty and marketing reserve`

## Outcome

Let a bilateral trade name its counterparty, and let either route book an optional
one-time marketing cost. Retain those facts at trade creation and carry the saved
marketing total through the existing reserve summary and `_ReportReserves`.

This PR completes these booking fields. Bilateral valuation remains refused until
the following kernel and integration slices add discounting and DV01.

## Field contract

Add two fields to the existing library-owned `fixed_float` definition:

| Field | Type | Requiredness | Meaning |
|---|---|---|---|
| `counterparty` | Text | Required for `route = bilateral`; absent for `route = cleared` | The named counterparty, retained per original trade occurrence. |
| `marketing_reserve` | Number | Optional on either route; omission gives zero | One finite, nonnegative amount in the index's settlement currency unit, per original trade occurrence. |

Place `counterparty` after `clearing_house`, and append `marketing_reserve` after
`payment_holiday_calendar`. The definition grows from 16 to 18 fields; `_ShowInstrument`
keeps its transposed seven-row layout, now with 19 columns including the row labels.
Describe conditional requiredness, currency and the once-per-occurrence basis there.

Both fields use the existing template/ticket mechanism. Exact headers and the refusal
of overlap remain, even if both sources supply equal values. No new argument, field
type, instrument, handle kind or public function is needed:

```text
_CreateTradeTemplate(instrument, fields, values) -> template
_CreateTrades(index, fields, trade_rows, template) -> trades
_ReportReserves(results) -> existing reserve table
```

A template is still a partial record. Validate supplied field values when building
it; resolve route-dependent presence when `_CreateTrades` combines template and ticket.
Keep the existing `clearing_house` rule: required for cleared, absent for bilateral.

Counterparty uses the current text-cell rules and is retained as entered. It may vary
by row; do not introduce a batch-uniformity requirement, registry, curve selection,
credit treatment or counterparty netting. One index and one route per batch remain.

## Marketing amount and ownership

- Accept finite numbers greater than or equal to zero, including fractional amounts.
  Refuse negative values, NaN and infinities. Do not round or convert the amount.
- Omit the field from both template and ticket for zero. In a supplied column, enter
  explicit numbers, including zero: blank, empty text, numeric text and booleans keep
  the existing seam refusals. The period fields' special absence rule does not apply.
- Count the amount **once per original ticket row**. A strip does not multiply it by
  months, quantity, days, observations or payment groups. A template amount applies
  once to each resulting row. Duplicate rows and repeated trade IDs each count.
- Quantity sign, entry unit and quantity basis do not scale this manually booked cost.
  A zero-quantity row with an explicit positive marketing amount retains that amount;
  its commodity exposure and quantity-based brokerage/clearing remain zero.
- The amount never runs off, accrues, discounts or moves to cash. It affects none of
  mark, cash, delta or DV01. Existing brokerage and clearing calculations stay unchanged.

The settlement currency unit comes from the index, as for the existing reserve totals.
It is not the commodity quote unit or the reporting-lot unit. No currency field or FX
conversion is introduced.

## Pipeline and saved state

Use the current validation boundaries: cell type in the seam, field meaning in the
library, shared intrinsic validation for template and ticket inputs. Route conditions
belong beside the existing conditional fields. Fail before publishing a handle;
invalid ticket values name the field and first offending original row in sheet order.
An aggregate overflow names the batch's marketing reserve rather than blaming a row
whose entered amount was valid.

Retain counterparty and the resolved marketing amounts per original occurrence in
the static trade terms. Compute the batch total once during creation:

```text
marketing_reserve_total = sum(marketing_reserve_by_original_row)
```

Populate the existing `Reserves.marketing`. Sum the original-row array, not an array
expanded through component ownership. Refuse a nonfinite aggregate even when every
entered amount is finite. Preserve the immutable reserve summary shared through
encoding, preparation and results; no reserve arithmetic occurs on history refresh,
evaluation, a commodity tick or a reader call.

`util_ReadHandle(template)` shows supplied values normally. The trades debug spill is
component-based: expose counterparty and the source marketing amount with the existing
original `row` attribution. A strip repeats its source fields on component rows; make
clear in its help that marketing is the original trade amount, not an allocated
component cost to sum down that spill. Do not invent an allocation to the first month.
The result reserve summary and `_ReportReserves` show the saved aggregate once.

Keep `_ReportReserves`' existing shape and columns:

```text
brokerage_reserve | clearing_reserve | marketing_reserve | currency
```

Its marketing value can now be nonzero. Value and risk readers have no changes in this
PR. A cleared example exercises the complete reporting path; bilateral examples verify
construction, retention and the existing evaluation refusal without bypassing it.

## Worked acceptance example

Use a valid USD-settled cleared financial template and an index covering these months,
with the other required terms held constant and `quantity_per = month`:

| Original row | trade_id | contract_code | quantity | marketing_reserve |
|---|---|---|---|---|
| 1 | 1001 | Z26 | 2 | 15 |
| 2 | 1002 | Z26 | -2 | 20 |
| 3 | 1003 | X26-Z26 | 1 | 25 |
| 4 | 1004 | Z26 | 0 | 5 |

The four rows create five monthly components, but marketing totals **65 USD**.
The opposing Z26 trades still contribute both costs. The two-month strip contributes
25 once, and the zero-quantity row contributes its manually entered 5.

Adding a duplicate of row 1, with the same ID, gives 80. Supplying 7 in the template
instead of a ticket marketing column gives 28 for the original four rows. Omitting
marketing entirely gives zero. Brokerage/clearing use their unchanged formulas in
every case, with their expected totals checked independently for each set of rows.

For a bilateral template, supply counterparty instead of clearing house. Test both a
shared counterparty and a ticket with two different names. Retain both names without
altering the existing financial components or enabling bilateral evaluation.

## Acceptance and delivery

1. Cover both field sources and both routes, missing bilateral counterparty, forbidden
   cleared counterparty, invalid supplied cells and duplicate template/ticket headers.
   Preserve source-aware refusal order; update quoted messages wherever they appear.
2. Pin the hand totals above, a fractional reserve, finite inputs overflowing in the
   sum, strips, duplicate occurrences and zero quantities. Reordering rows preserves
   totals; a batch equals the sum of its singletons. Changing quantity, unit, method or
   month/calday basis must not scale an unchanged entered marketing amount.
3. Compare otherwise identical cleared bookings with zero and positive marketing:
   all valuation and risk results remain identical, including through partial fixing,
   price ticks and payment. Only the reserve state/readback changes. Retained old
   results keep their original booked costs after a trade amendment.
4. Count marketing aggregation work in original occurrences, separately from existing
   component-based brokerage/clearing work. Report counts and retained-memory changes;
   prove no reserve recomputation after creation. Use array operations and the existing
   work-counter framework, without a cache or timing gate.
5. Update catalog/help, template and trade/readback pages, reserve documentation,
   smoke/host fixtures and the kept workbook, including shifted column references.
   Include a working cleared marketing
   example and bilateral booking/refusal example. Clarify any old zero-quantity wording:
   zero removes quantity-based economics, not an explicitly entered manual cost.
6. Run the full `check.ps1` gate. Follow the repository's separate-review rule for
   existing golden updates. Hand expectations establish correctness; workbook caches
   and generated snapshots do not establish it independently.

Update this ticket, the overview and UAT items 8/11 with the implementation revision.
Carry forward the latest agreed bilateral plan when syncing these drafting documents:
optional curve at evaluation, analytic signed DV01, and both `nominal_delta`/`delta`
columns. Those valuation and reporting changes belong to the next slices, not this PR.

No discount-curve argument or association, rate calculation, new payment convention,
reserve release schedule, counterparty risk or cross-results aggregation is included.

## As built

PR #175 on `claude/booking-fields`, stacked on #174. The library pages are
[show-instrument.md](../../library/instruments/show-instrument.md),
[create-trades.md](../../library/trades/create-trades.md),
[trade-template.md](../../library/trades/trade-template.md) and
[report-reserves.md](../../library/trades/report-reserves.md); the seam's record is the #175 row of
[history.md](../../seam/history.md).

- The fields as specified: `counterparty` after `clearing_house`, text, `route = bilateral` its condition,
  through the same conditions table as the clearing house; `marketing_reserve` last, a number, optional,
  options `a finite amount of zero or more`. Eighteen fields; the Show spills seven rows by nineteen columns.
- The rule, `marketing_reserves` in `trades/terms.py`, shared by the template (`marketing_reserve_of`) and
  the resolution's ticket column: `marketing_reserve row 2 is -5.0, expected a finite amount of zero or
  more`, the template's `marketing_reserve is -5.0, ...`; the conditions' words as the clearing house's,
  `counterparty is missing, expected it when route = bilateral` and `counterparty is 'ACME Trading',
  expected none unless route = bilateral`. The seam refuses a blank, text or boolean cell as any number's.
- The terms carry `counterparty` and `marketing_reserve` per occurrence, `None` as a whole when neither
  supplied the field; `reserves()` sums the amounts once over the occurrences, with numpy's flags down and
  the finiteness rule the judge: `the batch has inf of marketing reserve in all, expected a finite amount
  of USD; the rows' amounts, each finite, sum past the largest number`. `Reserves.marketing` is that sum,
  0.0 when the field is absent; brokerage and clearing are untouched.
- Readback: `counterparty` between `clearing_house`'s place and `broker`'s, `marketing_reserve` after the
  payment columns and before `entered_contract_code`, each only where the batch has the field, so every
  existing spill and positional read is unchanged; the strip's components each show the row's one amount.
- Counts: the resolution's ledger three looks more for the two fields and the condition and one `amounts` read, the same at five rows
  and at two thousand; the reserves one sum and one finiteness check where a batch has the field, `reserved_occurrences` one per
  row, nothing where it has not; the Show 133 cells classified where 119 were; no other ledger or pin moved. The Python tests
  2,514 to 2,528, the smoke 937 formulas to 976, the host's 314 to 314, the lifetime's 128 unchanged; the workbook 466
  cells changed, 414 added in rows 1976 to 2016 and 52 in the Show spill, two columns wider.
- Where it is pinned: `tests/unit/test_instruments.py`, `test_trade_template.py`, `test_create_trades.py`,
  `test_trades.py` and `test_trade_valuation.py`, `tests/performance/test_trade_creation_budgets.py`
  (`reserved_occurrences`), the smoke's OR32:OW62, the host's reserves and Show facts, and the kept
  workbook's rows 1976 to 2016.
- Not done, as the ticket keeps separate: no discount-curve argument, discounting, DV01 or delta-basis
  change; no payment, schedule or report-layout change; bilateral evaluation refuses as before; the
  value and risk readers are untouched. No golden file changed.
