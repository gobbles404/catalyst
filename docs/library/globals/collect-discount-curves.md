# _CollectDiscountCurves

A collection of named discount curves: the curves a batch of trades will select among by name, gathered as they are and held by reference, nothing of their factors constructed or combined, each name once. It is the first worksheet piece of the [named-curve arc](../../engineering-tickets/trade-valuation-pipeline/multiple-discount-curves.md), built as [slice 1](../../engineering-tickets/trade-valuation-pipeline/named-curves-slice-1.md): today a collection is made, read back and refused, and nothing takes one yet; `_EvaluateTrades` takes a collection in the arc's third slice, when every bilateral trade names its curve by `discount_curve_key`. The code is `src/catalyst/globals/discount_curve_set.py`, the record and its builder, and `src/catalyst/excel/globals.py`, the worksheet function.

## Worksheet contract

```python
def _CollectDiscountCurves(
    curve_handles: Handles[DiscountCurve],
) -> Handle[DiscountCurveSet]: ...
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

One argument, required and without a default: a cell, a row or a column of cells each showing [_CreateDiscountCurve](discount-curve.md)'s result, [util_BumpDiscountCurve](../utilities/bump-discount-curve.md)'s or a name for one, `Handles[DiscountCurve]`, [inputs.md](../../seam/inputs.md) decision 44. The seam holds the range to one cell, one row or one column before any cell is read, a wider and taller block refused by its shape; then each cell is resolved once, in sheet order, left to right along a row and down a column, and the function receives the curves and never the texts. A blank cell, a number, a boolean, an empty text, a text naming no live object, a handle of another kind, a collection among them, and a creator's failure are each refused at their cell in the seam's words, the failure carried whole so that a consumer of the failed collection shows the creator's text once. One cell is one curve collected, so at least one curve is always given. A range holds curve handles alone: A6:A9 above would take in the collection in A8 and is refused by that cell as another kind, so the members of a scenario are gathered through cells that refer to the curves, as rows 10 and 12 do. The result is a handle, text in the cell that stands for the collection the seam keeps, declared `Handle[DiscountCurveSet]` as [bridge.md](../../seam/bridge.md#a-handle-one-store-and-the-text) says; the text stays compact, `30512:discount_curve_set:4`, and the members are the readback's to show. Equal calls share one collection while any is live, and it is released when Excel disconnects the last, as [handles.md](../../seam/handles.md#publication-and-release) says: a curve replaced on the sheet remakes every collection referring to it, and a held old collection keeps its old members.

## The rule

Each name once. A key will select one curve by its name, so a collection holding two curves of one name could select neither; the first repeat is refused with the cell it repeats, the cells counted from one in the order the sheet gave them, and the same handle given twice is a repeat too, as is a later snapshot of a name, a curve bumped or remade. Names match exactly, case and all, so `SOFR` and `sofr` are two names, and equal factors under two names are two curves.

Nothing else is checked. Which curves must start on the valuation day and cover which payments is the evaluation's to decide, for the curves a batch selects, so a collection checks no date and holds curves of any spans: a one-day curve sits beside a ten-year one, and a curve nobody selects costs nothing. No factor is read or copied: the curves are kept as they are, the objects themselves and not copies, frozen, so a collection is one tuple of references and the curves stay their creators'.

| Refused | As |
|---|---|
| two curves of one name, the same handle twice included | `curve_handles cell 1 and cell 2 are both named 'SOFR', expected each name once` |
| a block wider and taller than one | `curve_handles is 2x2 array, expected one cell, one row or one column of discount curve handles` |
| a blank cell among the handles | `curve_handles cell (2, 1) is blank, expected discount curve handle` |
| a number, a date among them | `curve_handles cell (1, 2) is number 3.0, expected discount curve handle` |
| an empty text | `curve_handles cell (2, 1) is empty text, expected discount curve handle` |
| text naming no live object | `curve_handles cell (2, 1) is text 'x' naming no live object, expected discount curve handle` |
| a handle of another kind, a collection among them | `curve_handles cell (2, 1) is valuation date handle '30512:valuation_date:1', expected discount curve handle`; `curve_handles cell (1, 1) is discount curve set handle '30512:discount_curve_set:4', expected discount curve handle`; a lone cell holding one, `curve_handles is discount curve set handle '30512:discount_curve_set:4', expected discount curve handle` |
| a creator's failure in a cell | `curve_handles cell (2, 1) is the creator's failure, expected discount curve handle: #ERROR _CreateDiscountCurve: ValueError: discount_factor row 1 is 0.98, expected exactly 1 at the curve's first date`, and a consumer of the collection shows that creator's text once |
| the argument left out, or a blank cell in its place | `curve_handles is missing, expected discount curve handles in a cell, a row or a column`; `curve_handles is blank, expected discount curve handles in a cell, a row or a column` |

Nothing is published by a refusal.

## Binding a key

A trade's row, a cashflow's row or a quote's template names its curve by a key, `discount_curve_key`, and whoever discounts binds that key to a curve of the collection. The step is one, since [shared-curve-binding.md](../../engineering-tickets/trade-valuation-pipeline/shared-curve-binding.md), `curve_named` in `src/catalyst/globals/discount_curve_set.py`, for every caller: the curve whose name is the key, matched exactly, case and all, with nothing trimmed or guessed; no fallback to the first curve, a collection of one included; and no curve read for anything but its name. A key that names none is refused in one sentence, `no_curve_named`, raised by whoever looked: the key, who booked it where the caller has someone to name, a trade or a cashflow by its row, and the names the collection holds, each quoted, in the collection's order.

| Caller | Refused as |
|---|---|
| `_EvaluateTrades`, a bilateral batch, each distinct key in key order, [evaluate-trades.md](../trades/evaluate-trades.md) | `discount_curve_key 'Sonia' of trade 1003 at row 3 names no curve of the collection, which holds 'SOFR', 'FFOIS' and 'SONIA'; expected a curve of that name` |
| `_EvaluateCashflows`, each distinct key of the batch in key order, the first row booking it named, since [cashflow-curve-keys.md](../../engineering-tickets/trade-valuation-pipeline/cashflow-curve-keys.md), [evaluate-cashflows.md](../cashflows/evaluate-cashflows.md) | `discount_curve_key 'FFOIS' of trade at row 2 names no curve of the collection, which holds 'SOFR'; expected a curve of that name` |
| `_Quote`, `_QuoteByDates` and `_QuoteRFQ`, a bilateral template's one key, [quote.md](../quoting/quote.md) | `discount_curve_key 'SOFR' names no curve of the collection, which holds 'FFOIS'; expected a curve of that name` |

What each caller keeps is its own: whether a collection is required or refused, that a selected curve starts on the valuation day, `curve_starts_on` in `globals/payments.py`, and that it covers the caller's own unpaid payment days.

## Reading it back

`util_ReadHandle` spills one row per curve in the order given: `name`, `start_date`, `end_date` and `days`, the span the curve covers, inclusive; not the daily factors, which each curve's own handle spills. The collection of row 8 above:

| name | start_date | end_date | days |
|---|---|---|---:|
| str | datetime64[D] | datetime64[D] | int64 |
| SOFR | 4-Jan-2027 | 3-Jan-2029 | 731 |
| FFOIS | 4-Jan-2027 | 3-Jan-2029 | 731 |

## Excel help

Quoted from the declaration in `src/catalyst/excel/globals.py`, which `tests/unit/test_help.py` pins; Excel shows it while typing and in the `fx` dialog.

| Item | Text |
|---|---|
| Function | Collects named discount curves into one collection, each name once, the curves as they are and nothing of their factors combined, and shows its handle, the text other formulas take as the collection. |
| `curve_handles` | The curves to collect: a cell, a row or a column of cells showing _CreateDiscountCurve's or util_BumpDiscountCurve's results, such as B2:B3, each name once. |

## Work

`collect_discount_curves` in `src/catalyst/globals/discount_curve_set.py` counts what it did on the `WorkCounter` it is given: `curves_collected`, one per curve given, the names read once each for the rule. No numpy runs, whatever the curves' lengths, and the peak follows the curves and never their days, about 48 bytes a curve beyond a slack of small objects; the collection keeps no array of its own, so nothing is freed on release but the references, `tests/performance/test_discount_curve_set_budgets.py`. Through the seam the vector's shape is checked once, the cells decoded in one pass and each resolved once, then one publication; the readback lays out one row per curve.

## Tests

The record and the rule are `tests/unit/test_discount_curve_set.py`; the seam's texts and handles `tests/unit/test_globals.py`; the readback `tests/unit/test_utilities.py`; the help `tests/unit/test_help.py`; the smoke rows `tools/excel_smoke.ps1`, the UQ block, and their replay `host/Catalyst.Host.Tests/CallTests.cs`. What a call costs is `tests/performance/test_discount_curve_set_budgets.py`.

| Case | Kind |
|---|---|
| two curves collect in the order given, the objects themselves, counting each; a collection of one; curves of any spans together; equal factors under two names and two cases of one name are distinct curves; the record is frozen and the curves stand | example |
| the same curve twice, a later snapshot, two names each twice and a repeat not first: refused naming the first repeat and the cell it repeats, nothing counted | example |
| for any distinct names, the collection is the curves in order, each counted; for any names with a repeat, the first repeat and the cell it repeats are named | property |
| binding a key, since [shared-curve-binding.md](../../engineering-tickets/trade-valuation-pipeline/shared-curve-binding.md): the curve of the exact name whatever the collection's order, another case or a space naming none, a collection of one no fallback; the refusal's sentence with and without who booked the key, the names quoted in the collection's order for one, two and three | example |
| for any names and any key, the key is bound exactly when the collection holds its name, and refused naming every name it holds otherwise | property |
| a column, a row and a cell of curves collect under a compact handle, read back as their names in the order given; a bumped curve collects under its source's name; a scenario's members through cells referring to them; the curves stand as they were | example, through the seam |
| each name once through the seam, the same handle twice, a later snapshot and a bump of a member included; nothing published by a refusal | example, through the seam |
| every refusal above in the seam's words, a consumer of a failed collection showing the creator's text once, nothing published | example, through the seam |
| the seam's calls grow with the handles and no numpy runs; the peaks by count; nothing kept and nothing freed; the readback by count | budget |
| the UQ block: AA1's table under a second name, the two beside each other and collected, the bumped SOFR beside the base refused, a collection of one; the readbacks; the name's refusals and the collection's | Excel smoke |
| the same on the host: the named handles, the three-column curve readback, the collection's four-column readback, a row, one alone, the library's refusal and the seam's | host |

## Not here

Taking a collection: `_EvaluateTrades` takes one since [named-curves-slice-3.md](../../engineering-tickets/trade-valuation-pipeline/named-curves-slice-3.md), [evaluate-trades.md](../trades/evaluate-trades.md), each bilateral row naming its curve by `discount_curve_key` and the evaluation binding each key to the curve of that exact name, a collection of one included and a curve nobody selects read for nothing; `_EvaluateCashflows` takes one the same way since [cashflow-curve-keys.md](../../engineering-tickets/trade-valuation-pipeline/cashflow-curve-keys.md), each cashflow naming its curve, [evaluate-cashflows.md](../cashflows/evaluate-cashflows.md). A collection of collections, a curve added to or removed from a held collection, a lookup of one member by name on the sheet, and any check of the curves' dates: none; the readback shows the members and the evaluation judges the dates.
