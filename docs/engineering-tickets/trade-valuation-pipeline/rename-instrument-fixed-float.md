# Rename the instrument from future to fixed_float

[Pipeline overview](README.md) · [Bilateral plan](bilateral-discounting-and-dv01.md) ·
[UAT notes](surface-uat-notes.md)

**Status:** Built in #174, 10 October 2026, stacked on PR #173 at `92d49b3`, awaiting review.
This is the first, rename-only PR in the bilateral arc; [As built](#as-built) at the foot records
what changed. This ticket does not authorize merging the prototype stack.

**Suggested PR title:** `refactor(instruments): rename future to fixed_float`

## Outcome

Rename the existing broad instrument identifier `future` to `fixed_float`. Its current
representation already covers more than a single exchange-futures product. Give that
definition its agreed name before extending bilateral functionality.

This is one existing definition renamed, with the same fields, validation rules and
numerical behavior. Do not introduce a second definition or pricing path.

## Public contract

```text
_ListInstruments()
    -> lists fixed_float in place of future

_ShowInstrument("fixed_float")
    -> the existing field schema, in the existing transposed layout

_CreateTradeTemplate("fixed_float", fields, values)
    -> the existing template handle kind

_CreateTrades(index, fields, trade_rows, template)
    -> the existing trades handle kind
```

Update the instrument description to identify a fixed-versus-floating position with
explicit observation and settlement terms, without claiming new valuation support.
Keep the existing function signatures, field order, requiredness, options, field types,
strict header rules and template/ticket disjointness.

`"future"` ceases to be a valid instrument identifier. It fails through the normal
unknown-instrument path. No alias, fallback, retired-name registry or special migration
branch; preserve existing identifier case/whitespace validation.

## Implementation and migration

- Rename the definition constant `FUTURE` to `FIXED_FLOAT`, its catalog entry and the
  imports/identity checks referring to this instrument. Preserve one definition object
  and the existing resolution path. Current locations include
  `src/catalyst/instruments/definitions.py` and `src/catalyst/trades/resolution.py`.
- Update instrument-specific descriptions, errors, help and readback text. For example,
  the index-kind refusal in `src/catalyst/trades/terms.py` should name `fixed_float`
  while retaining its current accepted index kinds.
- Migrate executable callers: tests, registered-function fixtures, host replay,
  smoke/lifetime scripts and the kept `workbooks/handles.xlsx`. Include literal selector
  cells, validation lists and formulas where present, not just text inside formulas.
  Keep economic inputs and numerical expectations unchanged. Recalculate the kept
  workbook through the project's established workflow and inspect its relevant spills.
- Update active catalog, template, creation, kernel and pipeline documentation so the
  public name is consistent. Preserve historical review records and archived designs
  as history; do not rewrite old evidence or indiscriminately replace prose.
- Update this ticket, the pipeline overview and UAT list with the implementation PR
  and tested revision when delivered.

Actual futures terminology stays where it describes the market: `Kind.FUTURES`,
`FuturesSchedule`, futures histories, `future_expiry`, exchange product names and their
contract codes are unaffected. Existing handle kinds/prefixes and lifetime behavior stay
the same. Classify references by meaning; do not perform a repository-wide word replacement.

## Acceptance

1. Discovery lists `fixed_float` once. Show and template creation accept the new identifier;
   the old identifier is rejected by the ordinary unknown-instrument validation.
2. The field schema is unchanged apart from instrument naming/description. Template
   identity, trade resolution, encoding, preparation and evaluation follow the same path.
3. Migrated examples retain exactly the existing valuation, cash, lot-risk and reserve
   expectations, including daily/monthly/yearly risk views. Existing supported futures
   and IFERC cases retain their coverage; bilateral evaluation still refuses as before.
4. Current work/allocation budgets and lifetime behavior remain unchanged. Do not add
   numerical work, caching, handles or counters merely to implement a rename.
5. All kept executable callers use the new identifier, except deliberate old-name
   refusal tests. Run the full `check.ps1` gate, including host and Excel checks.
   Follow the existing separate-review rule for any existing golden changes; do not
   rewrite financial baselines to make a rename pass.

Use the existing discovery, creation and financial tests; add only the focused cutover
coverage needed to demonstrate the public contract. State the unchanged numerical
expectations and work budgets in the PR description, plus the migrated surface artifacts.

## Scope boundary

No counterparty or marketing-reserve field, new route, discount-curve argument,
discounting, DV01, delta-basis change, payment-rule change, schedule change or report
layout change belongs in this PR. Those are subsequent slices in the bilateral plan.
Only naming-related text changes are expected in reports/readback. There is no new
instrument support or change to physical-settlement restrictions.

## As built

PR #174 on `claude/fixed-float-rename`, stacked on #173. The library pages are
[list-instruments.md](../../library/instruments/list-instruments.md) and
[show-instrument.md](../../library/instruments/show-instrument.md); the seam's record is the #174 row of
[history.md](../../seam/history.md).

- The definition is `FIXED_FLOAT`, name `fixed_float`, description `A fixed-for-floating position on a
  specified reference contract, with explicit observation and settlement terms.`, the catalog's one entry;
  the resolution checks a template's instrument against it. Fields, rules, handle kinds and numbers are
  as they were.
- Texts that name the instrument: the two help strings, `such as fixed_float`; the index-kind refusal,
  `index is a Gas Daily index, expected a futures or an IFERC index for a fixed_float`; `a physical
  fixed_float after its expiry is not supported`; `template is of instrument 'swap', expected fixed_float,
  the one instrument whose trades are built`; `expected a field of fixed_float: ...`; the settlement rule,
  `a physical fixed_float past its expiry is refused`. Exchange products keep their words, `a penultimate
  future is cash settled ...` and `an IFERC basis future is cash settled ...`, as do futures indices,
  schedules, expiries and the prompt future.
- The old name fails through the one unknown-instrument path, `instrument is 'future', expected one of:
  'fixed_float'`, pinned in the library, through the seam, on the smoke's sheet and in the host's rows;
  the case and whitespace refusals stand.
- Migrated: every test that named the instrument, the smoke, the lifetime script's three templates, the
  host's rows and facts, and `workbooks/handles.xlsx`: the Show formula in B1262, seventeen template
  formulas, the label in A1262 and the notes in D1258 and D1270; the list in B1259, the shown rule in J1268
  and the readbacks in F1275 and F1291 recalculated to the new words, every value elsewhere unchanged.
- Counts: no ledger, allocation pin or numerical expectation moved; the Python tests 2,514 to 2,514, the
  smoke 936 formulas to 937, the host's 313 to 314, the lifetime's 128 unchanged; the workbook
  25 cells changed, the Show formula, sixteen template formulas, one label, two notes, and the list,
  the shown rule and two readbacks recalculated to the new words.
- Not done, as the ticket keeps separate: no counterparty or marketing-reserve field, no new route, no
  discount-curve argument, discounting or DV01, no payment, schedule or report change; bilateral evaluation
  still refuses as before. Seam history rows and review records keep the old name as history; the two
  archived design pages carry a one-line naming note instead of a rewrite. No golden file changed.
