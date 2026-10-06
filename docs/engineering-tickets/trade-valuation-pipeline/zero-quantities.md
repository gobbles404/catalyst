# Allow zero quantities in trade entry

[Pipeline overview](README.md) · [Trade creation](create-trade.md) ·
[Quantity unit selection](quantity-unit-selection.md) · [Create trades](../../library/trades/create-trades.md)

**Status:** Requested 6 October 2026 following UAT of
[PR #145](https://github.com/gobbles404/goosedove/pull/145), reviewed at `df7f4d7`.
Implement as one focused follow-up PR on the quantity-selection change, or on main once
it contains that change. This ticket supersedes the earlier requirement that a trade
quantity be nonzero; the other quantity and entry rules remain.

## Outcome

Accept a numeric `0` for `quantity` in a trade template or ticket. Users can keep fully
specified rows ready for quick trade entry and change the quantity when they need them.
A zero quantity contributes zero exposure, mark, cash and risk through the ordinary
creation, preparation, evaluation and reporting path.

Here, a spare row means a valid row with an explicit numeric zero. It does not mean an
empty Excel row, an empty quantity cell, or a partly completed ticket. Required fields
must still come from the template or ticket. Supporting genuinely blank rows is separate
work, not an implicit part of accepting zero.

## Worksheet example

Use a template with `quantity_unit = NYMEX NG`, where the supplied index defines that
name as 10,000 MMBTU, plus `quantity_per = month`, `schedule_method = lastday`,
`route = cleared`, `settlement_method = physical` and `clearing_house = CME Clearing`.

| trade_id | trade_date | contract_code | quantity | fixed_price |
|---|---|---|---:|---:|
| NG-001 | 2026-10-06 | Z26 | 2 | 3.00 |
| ENTRY-002 | 2026-10-06 | F27 | 0 | 3.30 |

With both contracts live, Z26 at 3.10 and F27 at 3.40, the batch returns mark 2,000,
cash 0 and aggregate delta 20,000. Its contract delta vector is `[20000, 0]` on
`[Z26, F27]`. The second row remains visible in the trade readback.

Changing the second quantity to -1, with everything else unchanged, creates new trades,
preparation and results. Mark becomes 1,000 and the delta vector `[20000, -10000]`,
aggregate delta 10,000. The history and market need not change. These are independent
hand expectations in USD, with delta measured in USD per USD/MMBTU. When booking a real
deal, the user also supplies its actual trade date and agreed price.

## Entry and pipeline rules

1. `quantity` remains a required, finite whole number. Positive, negative and zero values
   are accepted, including numeric negative zero. Fractional quantities, NaN and infinity
   remain refused. Text `"0"`, booleans, blank cells and empty text retain their existing
   seam errors; none is coerced to a number.
2. Accept zero wherever quantity is supplied: as a template default or in a ticket column.
   Template and ticket fields remain disjoint, even when both would supply zero. A missing
   quantity field still fails unless the template supplies it.
3. Keep the occurrence, its components and its recorded fields. Do not drop zero rows
   before validation or silently renumber the ticket. Duplicate occurrences still count.
   `util_ReadHandle` shows their quantity and encoded zero amounts through its existing
   layout. Preserve the stable contract axis, including zero delta entries.
4. Use the existing formulas: quantity times the selected specification's size and unit
   conversion gives zero quote quantity, hence zero coefficient and entry-price offset.
   A zero monthly strip contributes zero in each constituent month. One zero trade, many
   zero trades and a mix of zero and nonzero trades use the same path; an all-zero batch
   produces normal handles and zero reports when its other inputs are valid and supported.
5. Zero does not bypass the other boundaries. Invalid specification names, contract codes,
   dates, payment terms and unsupported methods still fail. History/index and market/history
   identity checks remain. Missing market coverage still fails. An expired physical future
   remains unsupported even at zero quantity; bilateral evaluation remains deferred.

The current kernel retains live slots by date, including slots with zero exposure. Keep
that behavior for this slice: a live zero slot still uses its ordinary market reference,
and fixed slots follow the existing history path. Do not add a special all-zero evaluator,
skip required prices, or prune net-zero contracts. Omitting work for zero exposures is a
separate optimization with its own lifecycle and validation decisions.
Offsetting nonzero trades at different fixed prices can have zero net floating exposure
and nonzero P&L; their entry-price offsets must remain intact.

Public signatures, result labels, report layouts, fixing and payment rules, and the
meaning of `quantity_unit` established in #145 stay unchanged. This change does not add
fractional quantities, mixed quantity selections within a batch, blank-row handling or
an inactive-trade flag.

## Implementation scope

- Remove the zero rejection from `whole_quantities` in `src/goosedove/trades/terms.py`,
  retaining its finite and whole-number checks. Both template `quantity_of` and resolved
  trade validation must accept zero through that same rule.
- Update `src/goosedove/instruments/definitions.py` and the generated `_ShowInstrument`
  table to describe a signed whole quantity including zero. Remove current claims of
  "nonzero" from the affected template, resolution, kernel and trade-entry documentation.
  Mark the earlier quantity-selection ticket's nonzero rule as superseded without
  rewriting historical decisions as if zero had always been supported.
- Replace tests expecting a zero-quantity refusal with positive acceptance tests. Keep
  independent numeric expectations, existing nonzero cases and all other refusal coverage.
- Add a zero row to the kept workbook's trade example without changing its existing
  aggregate financial expectations. Update affected smoke, host and lifetime checks and
  any readback row-count assertions deliberately. No new public function is needed.

## Acceptance

| Case | Required result |
|---|---|
| Template and ticket entry | Numeric zero accepted from either source, through the Excel seam and library. Overlap still fails. |
| Single zero and all-zero batch | Create, prepare, evaluate and both reports succeed with valid supported inputs. Mark, cash, aggregate delta and DV01 are zero in the cleared model; risk vectors retain their contract coordinates. |
| Mixed batch | The worked example above matches its hand values. Adding zero rows does not alter mark, cash or aggregate risk; additional contract coordinates may appear with zero delta. |
| Retained rows | Trade readback retains zero rows and their original occurrence order and labels. An all-zero batch is not treated as an empty ticket. |
| Strips and selections | A zero monthly strip retains its constituent months and zero amounts. Cover a non-first specification and an explicitly defined size-one quantity unit. |
| Financial lifecycle | A zero financial trade remains zero while live, fixed but unpaid, and paid. Use valid history and market fixtures; do not bypass their creation rules. |
| Existing refusals | Blank/empty/text/boolean quantity, fractional and nonfinite values still fail. A zero row with an invalid contract or specification also fails. Pin that zero does not bypass expiry, identity or coverage checks. |
| Cardinality | Extend the relevant quantity generators to include zero. Batch economics equal summed singletons, reordered rows preserve economics, and duplicate nonzero rows still contribute twice. Compare risk on aligned contract axes. |
| Excel dependency chain | Edit a quantity 0 to a nonzero value and back. Each edit replaces trades, preparation and results, updates mark and risk, releases obsolete handles, and retains the history and market. A price-only tick still reuses preparation. |

## Validation and handoff

Keep the work-budget tests. Removing the zero check removes a validation pass; update
affected call-profile assertions and record the before and after counts. For the same
row, contract and date structure, the reported creation, preparation and tick work should
remain unchanged. Additional retained rows can add components or slots. Do not change
allocation ceilings to hide extra work.
Run `check.ps1`, including host, Excel smoke and the trades lifetime group, and verify
the kept workbook in Excel. Existing golden changes, if any become necessary, require
their separate reviewed PR.

The implementation PR should show the zero-to-nonzero worksheet interaction, its hand
values and the updated instrument rule. Completion is support for explicit zero quantity
on otherwise valid rows; it is not support for empty or partially entered rows.
