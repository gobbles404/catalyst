# Apply brokerage and clearing reserves only when booked

[Pipeline overview](README.md) · [UAT item 18](surface-uat-notes.md#18-brokerage-and-clearing-applicability) · [Original reserve totals](reserve-totals.md)

**Status:** Built in #NN on `claude/reserve-fee-applicability` from `main` at `738b862`, 16 October
2026, two commits as asked; the [As built](#as-built-nn) section at the end says what was built
and what was not.
**Scope:** One focused PR from current main, with two ordered commits: fee applicability,
then the related instrument-description cleanup. No new fields, signatures or readers.

## Problem and agreed behavior

The current reserve calculation applies both fee rates from the selected index
specification to every trade component. A bilateral trade therefore incurs clearing
reserves despite having no clearing house, and a trade without a broker incurs brokerage.

The resolved trade determines whether a fee applies; its selected specification
supplies the rate. After the existing template and ticket resolution:

| Route | Broker for the trade | Brokerage | Clearing |
|---|---|---|---|
| bilateral | Omitted or `none` | 0 | 0 |
| bilateral | Named broker | Specification brokerage rate | 0 |
| cleared | Omitted or `none` | 0 | Specification clearing rate |
| cleared | Named broker | Specification brokerage rate | Specification clearing rate |

**Owner clarification:** a screen trade can explicitly have `broker = None` and
must reserve no brokerage. Reserve the exact text `none`, matched case-insensitively,
for this meaning: `None`, `none` and `NONE` all mean unbrokered. This is a rule for
the broker field, not a general conversion of text to Python `None`. Omitting the
broker field from both template and ticket still means no brokerage for the batch.

A template's broker value applies to all its trades. A ticket broker column may mix
named brokers and `none`; applicability is per trade, including every component of
that trade. Broker names do not select rates; the selected specification does.
Resolve this once during trade creation. Preserve the entered attribution in readback.

Clearing applicability is determined by `route = cleared`. The clearing house
identifies the organization and does not select a rate or act as a fee exemption.
Keep existing route validation: cleared trades require a clearing house and bilateral
trades cannot supply one. No special `none` meaning is introduced for clearing houses.

Keep the existing rejection of blank broker cells and duplicate template/ticket
fields. In particular, a ticket `none` cannot override a broker supplied by its template.

## Calculation and ownership

Make the change in static reserve creation, currently
`src/goosedove/trades/reserves.py`, using the resolved per-trade brokerage applicability
and route. No new lookup or repeated interpretation of the ticket is needed.

```text
brokerage_enabled[i] = trade i has a named broker, not omitted or the token none
clearing_enabled = resolved.route == cleared

count[k] = abs(resolved.component_quantity[k])
spec[k]  = resolved.specification[resolved.occurrence[k]]
brokered[k] = brokerage_enabled[resolved.occurrence[k]]

brokerage_reserve = sum(count[k] * brokerage_rate[spec[k]] for active brokered components)
clearing_reserve  = sum(count[k] * clearing_rate[spec[k]])   if clearing_enabled else 0
```

The pseudocode describes array operations, not per-component Python loops. Select
brokered components before rate arithmetic; skip inactive components and an entirely
inactive category's multiplication and reduction. Do not compute an invalid amount
and mask it to zero afterward. Existing specification validation
continues to apply. Active categories retain the finite-component and finite-total
checks, including the existing treatment of zero quantities and nonfinite rates.

Measure fee-component calculations as brokered component count plus cleared component
count, under `reserved_fee_components` rather than silently changing the meaning of
`reserved_components`. For N components: bilateral direct is 0, bilateral brokered
and cleared direct are N, and cleared brokered is 2N; a mixed broker column counts
only its brokered components for brokerage. Retain the separate marketing count.

Preserve the quantity and rate basis: rates are per count of the selected entry
specification, not per risk-reporting lot. Use absolute component quantities before
exposure netting. Both buys and sells incur applicable costs; duplicates count again;
strips contribute per monthly component, with existing `month` and `calday` sizing.

Reserve totals remain static, nonnegative costs in settlement currency. Preparation and
evaluation retain them without recalculation; `_ReportReserves` and debug readback
continue to read the saved totals. Marketing remains the existing optional amount
summed once per original ticket row. No reserve changes mark, cash, delta or DV01.

## Hand acceptance example

Use one USD specification with brokerage **10 per LOT** and clearing **4 per LOT**.
Each batch contains one **+10 LOT** trade covering one month. Supply valid route,
counterparty and settlement terms through the existing pipeline.

| Batch | Broker | Clearing house | Brokerage reserve | Clearing reserve |
|---|---|---|---:|---:|
| Bilateral direct | omitted or `None` | omitted | 0 | 0 |
| Bilateral brokered | `ION` | omitted | 100 | 0 |
| Cleared direct | omitted or `None` | supplied | 0 | 40 |
| Cleared brokered | `ION` | supplied | 100 | 40 |

Repeat with **-10 LOT**: the same reserve amounts. For two opposite +10/-10 rows
in the cleared brokered batch, exposure nets to zero while reserves are **200/80**.
Moving supplied attribution between template and ticket gives the same result.

Two +10 LOT rows, one with `broker = ION` and one with `broker = None`, reserve
**100 brokerage / 80 clearing** on the cleared route and **100 / 0** on the bilateral
route. These test a supplied broker column whose individual values control fees.

## Delivery: one PR, two commits

### Commit 1 — Fix fee applicability

Implement the reserve calculation and acceptance cases above. Include the behavioral
tests, creation work/allocation budgets, reserve-reference changes and affected smoke,
host and kept-workbook numerical expectations. This commit owns the change to which
fees are charged; the existing quantity/rate basis and valuation/risk remain intact.

### Commit 2 — Align instrument descriptions with the booking workflow

Correct the library-owned descriptions exposed by `_ShowInstrument`, and the matching
current documentation and description/spill tests. These are the descriptions users
consult when choosing fields for templates and completing tickets:

| Field | Meaning the description must convey |
|---|---|
| `broker` | A named broker enables brokerage reserves for that trade at the selected specification's rate. Omit the field or enter `none` (case-insensitive) for no brokerage, including screen trades. A ticket column may mix names and `none`. |
| `clearing_house` | Identifies the clearing organization. Retain the current required-for-cleared and forbidden-for-bilateral rules; the name does not select a rate. |
| `route` | Cleared trades incur specification clearing reserves; bilateral trades do not. Cleared valuation is undiscounted and takes no discount curve. Bilateral valuation is implemented and requires a discount curve at evaluation. Remove the obsolete claim that bilateral valuation waits on rates. |
| `settlement_method` | Physical versus financial settlement affects supported behavior, validation and payment requirements; it is not merely descriptive. Physical delivery remains outside the model. |

Keep the descriptions consistent whether a field is supplied by the template or the
ticket. Update directly matching help and reference wording, including the instrument
grid shown in the kept workbook where affected. This commit changes descriptions only:
no field names, types, choices, required flags, validation rules, signatures, spill
layout or numerical behavior. It is not a wider documentation reorganization.

## Implementation and validation

- Pin the four cases through creation, evaluation and `_ReportReserves`, including
  template/ticket parity. Test brokerage applicability independently of route.
  Pin omitted broker, `None`, `none`, `NONE`, a named broker, and mixed named/none
  rows. Pin the mixed-row totals above and propagation through strips. Blanks and
  duplicate template/ticket fields still fail; template `none` covers every row.
- Preserve meaningful tests for zero quantities, mixed entry specifications, strips,
  `calday`, duplicate occurrences, reordering and active-category overflow. Update
  old fee fixtures to explicitly supply the attribution that incurs their charges:
  add a broker to the reserve-totals example and its smoke, host and kept-workbook
  versions to preserve their 50 brokerage / 20 clearing expectations. Separately
  test nonzero specification rates with no broker on both cleared and bilateral routes.
  Pin that a nonfinite rate currently permitted by specification validation is unused
  when its category is inactive, including an unbrokered row in a mixed batch, but
  fails when active, including with zero quantity.
- Verify adding/removing a named broker or changing it to `none` changes only brokerage
  reserves. Renaming one real broker to another or renaming a clearing house does not
  change the amounts. Marketing and existing
  valuation/risk results remain unchanged for otherwise identical bookings.
- Pin no fee work during preparation, ticks, curve updates or reading. Update creation
  work/allocation budgets to describe the category skips; keep numerical work vectorized.
- Keep behavioral changes in commit 1 and the instrument-description cleanup in
  commit 2, as specified above. Pin that `_ShowInstrument` and its matching reference
  show the corrected descriptions, with their schema and layout unchanged. Keep the
  original reserve ticket as history with a link to this correction.
- Run `check.ps1` and report the results. Keep any golden-baseline acceptance separate
  under the repository's existing rule.

No new fee-switch fields, broker-specific rates, clearing-fee exemptions, reserve
discounting, fee payment lifecycle or changes to route validation are included.

## As built (#NN)

Built on `claude/reserve-fee-applicability` from `main`, one pull request of two commits and the
number stamped after.

**Commit 1, `fix(reserves): charge brokerage on brokered trades and clearing on the cleared
route`.** The terms find the brokered rows once, `ResolvedTrades.brokered`, a row's broker text
given and other than `none` in any case, the texts kept as typed for the readback;
`trades/reserves.py` charges brokerage over the brokered rows' components and clearing over every
component on a cleared route, each fee in one pass over the components it charges and no amount
made for a fee that does not charge, so a NaN or infinite rate the specifications let pass is
never read there; the counter reports `reserved_fee_components`, one per component per fee
charged, the marketing count as before. The hand examples hold at the kernel and through the
seam: 0/0, 100/0, 0/40 and 100/40, a sell the same, +10/-10 200/80, the tokens, the mixed column
100/80 cleared and 100/0 bilateral, the labels' spelling changing nothing, the blank cell and
the duplicate field refused as before. The reserve-totals example names ION as broker in its
tests, the smoke, the host and the kept workbook, so its 50 and 20 stand; the smoke and the host
add a cleared template without a broker, 0 and 20, and a mixed column, 20 and 20; the kept
workbook gains the block from row 2722 with the four batches, the mixed column by route and the
refusal. The `_ReportReserves` help and the pages say which fee charges where.

**Commit 2, `docs(instruments): say what route, clearing_house, broker and settlement_method
control`.** The four descriptions in `instruments/definitions.py`, the matching page and the kept
workbook's instrument grid; descriptions only.

**Not here.** No fee-switch field, broker-specific rate, clearing-fee exemption, reserve
discounting or fee payment lifecycle; no change to route validation; the readback adds no
column, the broker's text standing where the batch has the field.
