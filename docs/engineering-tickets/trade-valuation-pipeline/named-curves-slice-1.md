# Named discount curves and their collection

[Parent arc](multiple-discount-curves.md) · slice 1 of 4 · [Curve](../../library/globals/discount-curve.md) · [Bump](../../library/utilities/bump-discount-curve.md) · [Handles](../../seam/handles.md)

**Status:** Built in #201 on `feat/named-curves` from main `504cb34`, 18 October 2026, the ticket reviewed and corrected first. The pages that own what was built are [discount-curve.md](../../library/globals/discount-curve.md), [collect-discount-curves.md](../../library/globals/collect-discount-curves.md), [bump-discount-curve.md](../../library/utilities/bump-discount-curve.md), [read-handle.md](../../library/utilities/read-handle.md) and [handles.md](../../seam/handles.md). One wording changed at implementation: the library receives the curves as a tuple and no cell coordinates, so a repeated name is refused by position, `curve_handles cell 1 and cell 2 are both named 'SOFR'`, the cells counted from one in the order the sheet gave them, not `cells (1, 1) and (1, 2)` as drafted; the seam's own refusals of a cell keep their coordinates.

## Outcome

Every discount curve has a name, given when it is created, shown in its readback and in its handle text. `_CollectDiscountCurves` gathers existing named curves into a collection that evaluation will take in slice 4: it keeps references, constructs nothing, refuses a repeated name and reads back its membership. `util_BumpDiscountCurve` keeps the source curve's name on the curve it makes. Every caller that creates a curve, on the sheets, in the host, in the tests and on the pages, supplies a name. Nothing else moves: `_EvaluateTrades` and `_EvaluateCashflows` still take one curve, the trade terms have no key yet, and the reports' labels still say `curve_1` until slice 3.

## Worksheet contract

```text
_CreateDiscountCurve(name, header_row, table)   -> discount_curve handle, pid:discount_curve:SOFR:N
_CollectDiscountCurves(curve_handles)           -> discount_curve_set handle, pid:discount_curve_set:N
util_BumpDiscountCurve(curve, bump_bps)         -> discount_curve handle, the source's name kept
```

| | A | B | C |
|---|---|---|---|
| 1 | date | discount_factor | |
| 2 | 4-Jan-2027 | 1 | |
| 3 | 4-Jan-2028 | 0.95 | |
| 4 | 3-Jan-2029 | 0.9 | |
| 6 | `=_CreateDiscountCurve("SOFR",A1:B1,A2:B4)` | shows `30512:discount_curve:SOFR:2` | |
| 7 | `=_CreateDiscountCurve("FFOIS",A1:B1,D2:E4)` | shows `30512:discount_curve:FFOIS:3`, the second table 1, 0.96, 0.92 | |
| 8 | `=_CollectDiscountCurves(A6:A7)` | shows `30512:discount_curve_set:4` | |
| 9 | `=util_BumpDiscountCurve(A6,1)` | shows `30512:discount_curve:SOFR:5`, a basis point up, SOFR still | |
| 10 | `=A9` | `=A7` | the scenario's members, the bumped SOFR and the same FFOIS, in two cells |
| 11 | `=_CollectDiscountCurves(A10:B10)` | shows `30512:discount_curve_set:6`, the scenario collection | |
| 12 | `=A6` | `=A9` | the base SOFR and the bumped SOFR, two snapshots of one name |
| 13 | `=_CollectDiscountCurves(A12:B12)` | shows `#ERROR _CollectDiscountCurves: ValueError: curve_handles cell 1 and cell 2 are both named 'SOFR', expected each name once` | |

A range given to `_CollectDiscountCurves` holds curve handles alone: A6:A9 would take in the collection in A8 and is refused by that cell as another kind, so the members are gathered through cells that refer to the curves. `name` is the required first argument of `_CreateDiscountCurve`, text as the seam checks any text scalar, a number, a blank, empty text and a range refused in its words; the library holds it to a name, text with no whitespace around it and not whitespace alone. The table, the interpolation and the curve's rules stand as they are. The handle carries the name where an index's name goes, through the named-handle machinery, as the cashflows carry their currency. `curve_handles` is a cell, a row or a column of curve handles through the handle-vector seam, one kind, in the order given, at least one cell; a blank, text naming nothing, another kind's handle and a nested collection are refused by their cell in the seam's words. The collection's handle stays compact; its members are its readback's to show.

## The library checks

| Rule | Refused as |
|---|---|
| the name has no whitespace around it and is not whitespace alone, since a key will match it exactly, case and all | `name is ' SOFR', expected a name with no whitespace around it`; `name is '  ', expected a name, not whitespace alone` |
| each name once in a collection, the same handle twice included; the first repeat named with the cell it repeats, the cells counted from one in the order given | `curve_handles cell 1 and cell 2 are both named 'SOFR', expected each name once` |

Nothing else: a collection checks no date, since which curves must start on the valuation day and cover which payments is the evaluation's to decide for the curves a batch selects, in slice 4; two curves of different spans sit in one collection. Equal factors under different names are two curves; two snapshots of one name are refused in one collection and, across results, kept apart by identity in slice 3.

## Reading it back

A curve spills `date`, `discount_factor` and, since this slice, `name` on every row, the name last so that every positional read of the two columns stands. A collection spills one row per curve in the order given: `name`, `start_date`, `end_date` and `days`, the span the curve covers; not the daily factors, which each curve's own handle spills.

| name | start_date | end_date | days |
|---|---|---|---:|
| SOFR | 4-Jan-2027 | 3-Jan-2029 | 731 |
| FFOIS | 4-Jan-2027 | 3-Jan-2029 | 731 |

## Hand-worked acceptance

The grid above is the acceptance: the two named curves, their handles, the collection of two, the bumped SOFR named SOFR, the scenario collection accepted through cells referring to its members, and the collection holding two snapshots of SOFR refused by both cells. The bumped curve's factors are the bump ticket's, 0.9499050047498416 a year out, under the name SOFR. A collection of one curve is a collection. Reading a collection back after one of its curves is replaced on the sheet shows the new curve, since the collection is remade, and a held old collection keeps its old members.

## Migration

Every creation of a curve supplies a name; no caller is left on the old form and no form without a name is kept.

| Where | Creations | Proposed name |
|---|---:|---|
| kept workbook, `workbooks/handles.xlsx` | 16, at B6, B16, B79, B2050, B2084, B2087, B2103, B2106, B2118, B2420, B2489, B2746, J2785, J2787, C2860, V2896 | `SOFR` for every one; the cross-gamma block's second curve, J2787, is a second snapshot of the same curve and keeps the name |
| `tools/excel_smoke.ps1` | 15 | `SOFR`; the two tables that differ in one block are snapshots of one curve |
| `tools/excel_lifetime.ps1` | 5 | `SOFR` |
| `host/Goosedove.Host.Tests/CallTests.cs` | the curve facts and rows | `SOFR` |
| the unit and performance tests | 16 files | `SOFR`, and `FFOIS` where a test needs a second name |
| the pages | 17 mention the creator | the grids and the examples gain the name |

A migration harness rewrites each kept-workbook formula in place and takes a snapshot of every cell that depends on a curve before and after. It saves only when every economic result stands, each mark, cash, delta, DV01, cross-gamma, factor and date showing what it showed; the changes it allows are the intended ones alone, a curve's handle text carrying its name, its readback three columns wide and the spills that moved for it; and it rejects any other difference and any new error, `#SPILL!` where a wider spill meets an occupied cell included. The evaluation formulas, the templates and the tickets are slice 4's. The pages that own the creator, the bump and the handles say what changed; the arc's parent ticket stays the design record.

## Work and budgets

Naming a curve costs nothing per day: the record gains a reference. A collection is one tuple of references, the names read once each for the repeat rule, counted once per curve as `curves_collected`; its peak follows the curves, not their days, and its retained bytes are the references alone, the curves being theirs. The curve's own budgets stand.

## Tests

The names, the two rules, the readbacks, the bump keeping the name and the handles' texts, in `tests/unit/test_discount_curve.py`, `tests/unit/test_bump_discount_curve.py` and a new `tests/unit/test_discount_curve_set.py`, with the seam's words; the help pinned; the curve and bump budgets re-pinned where a name entered the ledger and the collection's own in `tests/performance/test_discount_curve_set_budgets.py`; the host facts and smoke rows; the lifetime script's curves named; the kept workbook migrated.

## Not in this slice

Per-curve risk, the labels `SOFR USD dv01` and the cashflow collection through `_AggregateResults`: slice 2, [named-curves-slice-2.md](named-curves-slice-2.md). The `discount_curve_key` field, the collection as `_EvaluateTrades`'s input and the key's binding: slice 3. Anything numeric about the curves themselves.
