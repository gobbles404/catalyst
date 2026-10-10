# Numeric trade IDs

[Pipeline overview](README.md) · [UAT item 2](surface-uat-notes.md#2-trade-identifiers)

**Status:** Built in #NN on the prototype stack above #167, the page as a ticket; the
[As built](#as-built-nn) section at the end says what was built and what was not. Engineering
ticket, 9 October 2026. The owner confirmed that source-system
trade IDs are whole integers of at most 15 digits, without meaningful leading zeros.
Inspected prototype: PR #167 at `9117a39`. One focused PR on the current prototype
successor; this ticket does not decide how the prototype lands.

## Outcome

Accept the source system's numeric `trade_id` cells directly in templates and trade tickets,
retain them as integer identifiers and return numeric cells in readback. Users should not
need `TEXT()` or an apostrophe to book a trade with its existing ID.

This replaces the earlier alphanumeric proposal. Cut `trade_id` over to numbers; do not
add a number-or-text field or silently parse text containing digits. The worksheet creator
signatures and exact `trade_id` header stay the same.

## Field contract

| Property | Contract |
|---|---|
| Field | `trade_id` |
| Description | External numeric identifier of the executed deal |
| Instrument type row | `number` |
| Library value | Whole integer; integer scalar in a template, immutable integer values per occurrence in a resolved batch |
| Required | No, preserving current optionality |
| Accepted value | A finite whole number with `abs(value) <= 999999999999999` |
| Source | Template or ticket, with the existing refusal when both supply it |
| Missing field | No external ID; diagnostics continue to identify the ticket row |
| Present blank cell or empty text | Fail under the existing seam rules; never invent an ID |
| Duplicate IDs | Allowed; every trade occurrence still contributes |

Do not add a positive-only or uniqueness rule: zero and signed whole values within the
range are identifiers, not quantities or missing-value sentinels. There is no arithmetic
tolerance for fractional input, and no rounding, truncation, ID generation or remapping.

The 15-digit bound matches the confirmed source-system scope. Microsoft documents
[15-digit Excel number precision](https://support.microsoft.com/en-us/excel/excel-specifications-and-limits).
Validate finiteness, integrality and range before conversion to integer storage. Do not
claim to recover digits Excel already altered. Text IDs, longer IDs and preservation of
leading zeros are outside this field contract.

## Worksheet example

Using an otherwise valid existing template and index:

| trade_id | trade_date | contract_code | quantity | fixed_price |
|---:|---|---|---:|---:|
| 123456 | 9-Oct-2026 | Z26 | 1 | 3.00 |
| 123457 | 9-Oct-2026 | F27 | -2 | 3.10 |
| 123456 | 9-Oct-2026 | Z26 | 1 | 3.00 |

All IDs above are numeric Excel cells. The repeated `123456` remains two occurrences;
it does not replace the first row or cause deduplication. Readback returns these IDs as
numbers. A strip repeats its occurrence's ID on each resolved component row, alongside
the existing original-row attribution.

| Input in an ID cell | Result |
|---|---|
| Numeric `123456` or numeric formula `=123456` | Accept |
| Numeric `123456.0` | Accept as the whole ID `123456` |
| Numeric `999999999999999` | Accept and preserve exactly |
| Numeric `1000000000000000` | Fail: outside the 15-digit range |
| Numeric `123456.5` | Fail: not a whole number |
| Text `"123456"` or `"NG-001"` | Fail: expected a number |
| Boolean, blank cell or formula returning `""` | Fail; no coercion or default |

## Implementation boundaries

Today `instruments/definitions.py` declares `trade_id` as text. Resolution reads it
through `_Fields.labels`, `ResolvedTrades.labels` retains strings, `named_trade` formats
those strings in errors, and `excel.utilities.trades_table` spills them as text. All of
those uses must move together; changing the catalog alone leaves an inconsistent pipeline.

1. **Definition and seam:** change this field to the existing `FieldType.NUMBER`.
   Reuse the numeric column binding already supported by `FieldRow` and `FieldRows`;
   no new general seam type or coercion is required. Keep other textual fields such as
   broker and clearing house unchanged.
2. **Meaning at creation:** use a shared trade-ID rule for supplied template values and
   ticket columns. Check finite whole values and the range, naming the field and original
   offending row when supplied by the ticket. A template containing an invalid ID fails
   at template creation. Respect existing validation order and avoid revalidating trusted
   template values on each use.
3. **Retained state:** keep one integer ID per original occurrence, or an absent optional
   collection. Use immutable integer storage for resolved IDs (`int64` covers the accepted
   range), with an integer scalar for a supplied template ID. Excel's numeric binding may
   initially deliver a floating-point number; validate before converting it once at creation.
   Do not leave IDs as text merely to reuse the label path. Preserve component-to-occurrence mapping and
   distinguish external IDs from internal row positions and handle identity.
4. **Diagnostics and readback:** errors show the full whole ID and original row, for
   example `trade 123456 at row 2`, without a `.0` suffix or scientific notation.
   Template and trade readbacks return numbers, not text made to look numeric. Existing
   numeric output machinery can carry the accepted range exactly; do not create a new
   result reader or change report layouts.

An ID supplies attribution. It does not affect payment grouping, exposure compression,
valuation or risk. No preparation or tick should parse, validate or convert trade IDs.
Keep one batch path for one or many trades, including duplicate IDs and zero-quantity rows.

## Acceptance and delivery

- Exercise the example and input table through registered worksheet functions. Pin
  `_ShowInstrument("future")`'s type and rule, template readback, trade readback and
  numeric output cell kinds. Include a 15-digit round trip and a numeric formula cell.
- Verify the range boundary on both signs, zero, fractional and nonfinite inputs through
  the applicable public/library boundaries; never cast first and discover overflow later.
- Keep omission optional, refuse supplied blanks, and reject a template/ticket overlap
  even when the two numeric IDs agree. A template ID broadcasts using the existing
  template semantics; equal values do not erase occurrences.
- Check a strip's component rows retain the same ID and original row. Trigger a refusal
  on a later ticket row after an earlier strip expands, proving attribution still names
  the original numeric ID and ticket row.
- Changing only the IDs leaves economic outputs identical. Duplicate occurrences still
  double their contributions; reordering preserves aggregate values and aligned risks.
- Migrate kept examples, smoke/host expectations, tests and workbook IDs from labels such
  as `NG-001` to numeric cells in this PR. Update only the associated identity text/cells;
  retain their independent economic expectations and duplicate-occurrence coverage.
- Update instrument help and mirrored pages, template/creation/readback documentation,
  and UAT item 2. No legacy text-ID compatibility path. Keep any existing golden baseline
  changes separate under the repository's source/golden review rule.
- Run the full gate. Update meaningful creation/retained-memory budget expectations if
  integer storage changes them; preparation, evaluation and report work remain unchanged.

No counterparty field, trade lookup service, uniqueness registry, external-system connector,
new handle identity or per-trade valuation is part of this ticket.

## As built, #NN

Engineering's record of what landed, in the ticket's terms.
[create-trades.md](../../library/trades/create-trades.md),
[kernel.md](../../library/trades/kernel.md) and
[show-instrument.md](../../library/instruments/show-instrument.md) are the pages.

- **The field.** `trade_id` is `FieldType.NUMBER` in `src/goosedove/instruments/definitions.py`:
  the description `External numeric identifier of the executed deal`, the options `a whole number
  of at most 15 digits` and the rule `The source system's deal number, whole, -999999999999999 to
  999999999999999, never text; duplicates keep separate occurrences`; the headers, the creator
  signatures and the field's optionality are as they were. The seam binds the column as float64
  and refuses text, a boolean, a blank and empty text in its own words, `trade_rows cell (1, 1)
  is text 'NG-001', expected number`; nothing is coerced.
- **The rule.** `whole_trade_ids(values, where)` in `src/goosedove/trades/terms.py`, beside
  `whole_quantities` and `finite_prices`: finite, whole and within the 15 digits either side of
  zero, the first bad value named in the caller's words and shown without a fraction when whole,
  `trade_id row 2 is 123456.5, expected a whole number of at most 15 digits`, `trade_id is
  1000000000000000, expected a whole number of at most 15 digits`; then one conversion to int64,
  frozen. `trade_id_of` in `template.py` reads a template's ID when the template is made, so a bad
  one fails there and is never read again; `_Fields.ids` in `resolution.py` repeats the template's
  integer or reads the ticket's column once through the rule, naming the row, at the place the
  label was read before. Nothing rounds, truncates, generates or remaps an ID.
- **Retained state.** `ResolvedTrades.labels` is `trade_ids`, an `int64` array per occurrence or
  None, frozen by `resolved_trades`, which checks the count, `trade_ids has 2 ids, expected 5,
  one per occurrence`, and nothing else; `clearing_house` and `broker` stay text tuples. The
  components keep their occurrence rows, so a strip's rows repeat their occurrence's ID.
- **Diagnostics and readback.** `named_trade` writes `trade 1001 at row 5` and `trade at row 3`,
  no quotes, no fraction, no exponent, in the kernel, the observations and the encoding alike.
  `util_ReadHandle` spills `trade_id` as an `int64` column and a template's ID as a number; the
  15 digits survive the float64 cell exactly. `_ReportValues`, `_ReportRisk` and `_ReportDelta`
  are unchanged.
- **Migration.** Every kept label became a number by one rule: NG-001 to NG-004 are 1001 to 1004,
  WAH001 is 1001, a bare letter is its place in the alphabet, a letter with digits is its digits.
  The tests, the smoke, the host's facts, the pages and the kept workbook's 33 ID cells under 19
  tickets changed in that way, their economic expectations untouched; the owner's earlier
  tickets keep the messages they quoted when they were built.
- **Pinned by hand.** The ticket's rows, 123456, 123457 and 123456 again, two occurrences of one
  ID with their contributions doubled; 999999999999999 and -999999999999999 kept exactly and zero
  accepted; 1000000000000000, 123456.5, infinity, NaN and text refused in their words; a numeric
  formula cell accepted; a template's 77 on every row of a ticket without the column and the
  overlap refused though the numbers agree; a strip's rows carrying their ID and original row, a
  later bad row named by its own ID and row; the values, cash and risk of a batch unchanged by
  its IDs.
- **Counts.** The resolution's ledger reads the IDs through `_Fields.ids` once and the two labels
  through `_Fields.labels` twice where it read three labels; nothing else moved. The allocation
  pins are unmoved, the pinned batches carrying no ID column; a 2,500-row batch with one measures
  710,007 bytes at its peak against 708,952 before, the int64 column in place of a tuple over the
  seam's texts.
- **Not built.** No counterparty field, lookup, uniqueness registry, connector, handle identity or
  per-trade valuation; no text IDs, no leading zeros and no sixteenth digit; no legacy path.
