# Handles

**Normative.** How a retained object is reached from a worksheet. Why these choices, and
what they cost, is in [decisions.md](decisions.md#handles) — D22 to D26.

Not implemented. The seam cannot return a handle today (D26).

A handle is opaque text in a cell that identifies an object held in memory.

> Excel owns the worksheet dependency graph. The runtime owns the retained objects. The
> seam resolves the current handle value to the expected Python object.

## The worksheet workflow

A creator formula returns a handle into its cell. A consumer refers to that cell, directly
or through an Excel defined name referring to it. Workbook authors connect formulas with
Excel's own references and names; they do not maintain handle strings.

```excel
Data!A1:B1    date / df headers
Data!A2:B15   the daily table

Inputs!B2     =CreateDiscountCurve(Data!A1:B1, Data!A2:B15)
              displays Curve:17

Defined name  DeskCurve refers to =Inputs!$B$2
```

A consumer's curve argument may be `Inputs!$B$2` or `DeskCurve`. Excel tracks the
dependency either way and passes that cell's current value to the seam. The seam resolves
it once and hands the library the typed object. The library never receives, parses or
looks up a worksheet address or name.

`DeskCurve` is an Excel name for a cell. It is not a second object registry, a permanent
alias, or the curve's content identity.

Handle strings shown in this document are illustrative. Their spelling and numbering are
not a selected implementation, a persistent ID, or a user-managed version sequence.

## What is supported, and what is not

Cell references, and defined names referring to cells. An ordinary formula relaying a
creator's value is still an Excel dependency, not an independent owner, however it looks.
Renaming a name, inserting rows, or moving formulas follows Excel's own reference
behaviour.

Not supported: pasting a handle as a value, typing one into a formula, assigning the
literal text to a defined name, or carrying one outside the workbook dependency chain.
None of these acquires ownership or a persistence promise. A name referring to
`Inputs!$B$2` and a name holding the constant `"Curve:17"` are different workflows.

This is a usage contract, not a claim that the seam can reject every literal. A live handle
may resolve however it reached the argument; rejecting on worksheet provenance would need
host information that does not exist. What is required: unknown, expired and wrong-kind
values fail visibly, and matching-looking text never selects an unrelated object.

## Ownership

| Layer | Owns |
|---|---|
| Excel | references and names, calculation scheduling and order, displaying creator values and failures |
| Host and seam | publishing and resolving handles, enforcing the declared object kind at the boundary, retaining and releasing the Python references they own |
| Library | building valid immutable objects, consuming typed objects, retaining the Python dependencies its own objects need. It does not navigate worksheets and does not import the Excel bridge |

A live creator owns its currently published object. A lookup, or another cell displaying
its value, is not a separate ownership record. A retained object that depends on another
must hold its own strong Python reference, which can keep the underlying object alive after
the original creator moves on.

**Cell addresses locate formulas.** They must not become object IDs, cache keys, or
permanent producer slots. A moved formula follows Excel's rules; it must not collide with
whatever previously occupied the destination, nor be treated as an unauthorized second
producer because its address changed (D23). This does not prohibit Excel-DNA from tracking
subscriptions internally.

## A missing object is a failure, not a cache miss

Cleanup must not delete an object a live creator owns or a retained dependency needs. An
LRU or age limit must not evict the object behind a valid handle to admit another. If a
capacity policy is introduced, failed new construction leaves existing owned objects valid.

Excel sees the value in the creator cell, not the object store. Removing the object behind
`Curve:17` does not change that cell and does not ask Excel to rebuild the curve. A missing
object where this contract promises one is a runtime failure: report it. Never substitute
another object, and never silently reuse a previous answer.

Collecting objects proven unused is a different thing from evicting live ones. An optional
cache of *calculated results* may discard an answer that can be recomputed from available
inputs; it must not discard the input objects. Construction reuse, calculation reuse and
object lifetime are three separate responsibilities.

Saving a workbook preserves formulas, names, inputs and possibly the displayed handle text.
It does not persist the object store. Handle text from a previous runtime must never
resolve to an unrelated new object.

## Favored direction: reuse unchanged, publish changed

**Not settled** (D25). The direction under consideration:

| Worksheet action | Creator cell | Consumer |
|---|---|---|
| Supply a valid table | displays `Curve:17` | a reference supplies `Curve:17`; the seam resolves it |
| Recalculate, inputs unchanged | reuses the existing object and handle | resolves the same object without reconstruction |
| Change a factor to another valid value | publishes a new immutable curve, displays `Curve:18` | Excel propagates; the same formula now receives `Curve:18` |
| Supply invalid data | shows the construction error, publishes no replacement handle | receives the failure through the seam's error path |

The old object is not mutated or retargeted to hold the new data. Failure to construct a
replacement must not present the previous handle as though it described the new inputs.

In manual calculation mode, editing inputs promises no immediate propagation; when the user
requests calculation, creator and dependents update in Excel's dependency order. The runtime
must not invalidate a still-retained object merely because no lookup happened recently.

## Errors are text

The seam returns failures as text beginning `#ERROR `, not as Excel error values. A failed
creator's cell therefore holds that text, and a consumer referring to it receives the text
as its handle argument. The resolver recognises the prefix and fails as *the creator
failed*, quoting its message — not as an unknown handle, which sends the user looking for a
store problem that does not exist.

## Acceptance scenarios

Planning cases, not implemented tests, and not a claim that Excel-DNA already meets this
contract.

| Scenario | What must hold |
|---|---|
| consumer uses a direct cell reference, or a name referring to it | both supply the current handle and resolve the correct typed object |
| unchanged creator recalculates | the favored behaviour reuses the active object and handle; measure preparation as well as publication and lookup |
| a valid factor change | the creator publishes the new curve; consumers update through existing references; retained old objects are unchanged |
| an invalid factor change | creator and dependents show the failure; no handle is published for the invalid inputs |
| manual calculation | owned objects survive between calculation requests; a requested calculation follows Excel's dependency order |
| insert rows, sort a table, cut and paste a formula block, move across sheets, rename a name | values and references follow Excel's semantics; no cell-slot collision, no false second-producer error |
| duplicate creator formulas, then remove one | removing one owner does not invalidate an object another still owns |
| replace or delete a creator while another retained object uses its old curve | the dependent keeps valid immutable data; release happens when its final owner is gone |
| a live object's store entry is deliberately removed in a diagnostic test | the failure is visible; any promised recovery is verified |
| a pasted literal, an old-session token, a diagnostic display | none acquires ownership by appearing as text; unknown, expired and wrong-kind values fail |
| undo, interrupted calculation, workbook close and reopen | promises agreed first, then exercised in Excel |

Use deterministic work counts for construction, transport, copies, fingerprinting, lookup,
publication, scans and release. Observe retained bytes with shared ownership accounted for.
Record end-to-end timing as evidence, never as a gate. Existing seam checks are a baseline;
they do not validate an unbuilt handle system.

## Open

| | |
|---|---|
| What the seam needs before any of this exists | D26 |
| The precise reuse and equality rule; duplicate creators; inputs differing only before normalization | D25 |
| Release timing, and whether a published handle stays resolvable after its creator releases it | D25 |
| Session safety, save and reopen, creator reconstruction on startup | D25 |
| Recovery from unexpected loss; undo; interrupted calculation | D25 |

Excel-DNA 1.9 is the first candidate to evaluate. No mechanism is selected: not its store,
not a custom Python registry, not a COM workbook scan, collector, LRU, recovery macro or
fingerprint framework. The evidence is in [notes/excel-dna-research.md](notes/excel-dna-research.md).

The supported use of cell references and names is settled and is not reopened as a
requirement to support independently managed text tokens.
