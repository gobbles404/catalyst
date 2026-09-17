# Handles

Open: release and reuse, below.

A handle is text in a cell that stands for an object the add-in holds in memory, such as a curve. Excel owns the worksheet's dependency graph; the seam owns the retained objects and resolves the current handle value to the Python object; the library builds and consumes objects and never sees the text. Built in #53: the declaration `Handle[Kind]`, one store, the three-part text, publishing on the way out and resolving on the way in, with every failure as text in the cell. Those parts now live where the seam's built things live, [inputs.md](inputs.md) decisions 34 to 37, [outputs.md](outputs.md) decisions 10 to 12 and [bridge.md](bridge.md#a-handle-one-store-and-the-text), and this page keeps what a workbook author may rely on and what is still open: release when a creator is deleted or its workbook closes, reuse of the same handle on an unchanged recalculation, and batches of one handle per row. Today every creator call publishes a new object, and the store holds it until Excel closes. The evidence behind the ways of building release is [excel-dna-handles.md](excel-dna-handles.md). When release is built, the rest of this page moves the same way and the page goes.

## A small object first

```excel
A2   11-Sep-2026
B2   0.5
C2   =_CreateValuationDate(A2, B2)      displays valuation_date:3f9a1c:000001
```

The shared workbook `workbooks/handles.xlsx` holds this sheet, the curve's, and a block for each creator built since, its inputs and creator on the left and `util_ReadHandle` spilling the object on the right, with a `notes` column for whoever is looking at it: `.\tools\excel_dev.ps1 workbooks\handles.xlsx` opens it with the add-in, and `.\tools\excel_show.ps1 workbooks\handles.xlsx` prints it as its cells show.

The creator builds a Python object holding a numpy day and a float. The seam retains that object and displays its handle in `C2`. Another formula refers to `C2`, or to a defined name referring to it; the seam resolves the handle once and hands the library the object. Reading it does not rebuild it. One valuation-date creator per workbook is the expected case, not an enforced singleton: the store holds many independent objects.

## The worksheet workflow

A creator formula returns a handle into its cell. A consumer refers to that cell, directly or through an Excel defined name referring to it. Workbook authors connect formulas with Excel's own references and names; they do not type or copy handle text.

```excel
Data!A1:B1    date / discount_factor headers
Data!A2:B15   the daily table

Inputs!B2     =_CreateDiscountCurve(Data!A1:B1, Data!A2:B15)
              displays discount_curve:3f9a1c:000017

Defined name  DeskCurve refers to =Inputs!$B$2
```

A consumer's curve argument may be `Inputs!$B$2` or `DeskCurve`. Excel tracks the dependency either way and passes that cell's current value to the seam, which resolves it once. The library never receives, parses or looks up a worksheet address or name. `DeskCurve` is an Excel name for a cell, not a second object registry, a permanent alias, or the curve's content identity.

Supported: cell references, and defined names referring to cells. An ordinary formula relaying a creator's value is still an Excel dependency, not an independent owner. Renaming a name, inserting rows or moving formulas follows Excel's own reference behaviour. Not supported: pasting a handle as a value, typing one into a formula, assigning the literal text to a defined name, or carrying one outside the workbook's dependency chain; none of these acquires ownership or a persistence promise. This is a usage contract, not a claim that the seam can reject every literal: a live handle resolves however it reached the argument, since rejecting on worksheet provenance would need host information that does not exist. What is required, and built, is that unknown, expired and wrong-kind values fail visibly, and matching-looking text never selects an unrelated object.

## The handle's text

Three colon-separated parts, all lowercase: `kind:session:number`.

| Part | Meaning |
|---|---|
| `kind` | the kind's tag, its class name in lowercase words joined by underscores: `valuation_date`, `discount_curve`; Python types and worksheet functions keep their PascalCase names |
| `session` | six hex characters drawn once when Python starts, so text saved in a workbook never names an object of a later session |
| `number` | one running publication number starting at 1, six digits at least, shared by every kind and workbook using the store |

```text
valuation_date:3f9a1c:000001
discount_curve:3f9a1c:000002
```

The number is a publication number, not a version, an array index, a per-kind sequence or a count of live objects. A new publication takes the next number; removing entries never recycles numbers; closing a workbook does not reset the number of a runtime that stays open; six digits is a minimum width, and the number grows past it without wrapping. The full, exact text is the lookup key: a consumer neither looks up a part alone nor normalizes a supplied handle, and the stored, verified kind establishes the object's type; the visible tag describes it and proves nothing. The readable label the earlier direction carried was dropped by the owner on 2026-09-13: nothing supplies one, and one can be added when a need appears. The short forms `curve:17` and `curve:18` below abbreviate this text to explain ownership; they are not accepted formats.

## Separate objects and shared dependencies

Separate creator formulas publish separate immutable objects and handles, even with identical inputs; built, and pinned. Separate trade rows within one batch remain separate objects: two identical trade rows are two trades. Distinct handles around one shared object do not satisfy this. Recalculating the same creator is not a separate creator: unchanged inputs are to reuse its current objects and handles and consume no new publication numbers; that reuse is not built, today a recalculation publishes anew, and the equality key and the preparation work behind it are open. Objects may hold references to the same dependency: two independent trades may use one valuation date or curve without copying it.

A creator may own several published objects. The working proposal for a creator that takes several rows is one handle per row, spilled as a column:

| Input to one creator | Output | Retained |
|---|---|---|
| row 1, trade details X | `trade:17` | trade object A |
| row 2, identical details X | `trade:18` | trade object B |

One creator formula owns the batch; a successful replacement releases the previous batch, deleting the creator releases its batch, and the duplicate rows never collapse into one object. Row positions describe input-to-output pairing, not persistent identity. The declaration, the row-error policy, blocked-spill behaviour, resizing, and partial reuse of unchanged rows when others change are open below; one handle per row is a proposal, not a supported result today, and no public trade function is specified here.

## Who owns what

| Layer | Owns |
|---|---|
| Excel | references and names, calculation scheduling and order, displaying creator values and failures |
| the host and the seam | publishing and resolving handles, enforcing the declared object kind at the boundary, retaining and releasing the Python references they own |
| the library | building valid immutable objects, consuming typed objects, retaining the Python dependencies its own objects need; it never navigates worksheets and never imports the Excel bridge |

A live creator owns its currently published object or batch. A lookup, or another cell displaying its value, is not a separate ownership record. A running calculation keeps the references it needs for its call. A retained object that depends on another holds its own strong Python reference, which can keep the underlying object alive after the original creator moves on. Spill cells belong to their creator's output. Cell addresses locate formulas: they must not become object identities, cache keys or permanent producer slots, and a moved formula follows Excel's rules without colliding with whatever previously occupied the destination or being treated as an unauthorized second producer: an address locates a formula and is never an object's identity ([golden rule 10](../golden-rules.md)).

## A missing object is a failure, not a cache miss

Cleanup must not delete an object a live creator owns or a retained dependency needs; no age or capacity limit evicts the object behind a valid handle to admit another, and if a capacity policy is ever introduced, failed new construction leaves existing owned objects valid. Excel sees the value in the creator cell, not the store: removing the object behind `curve:17` neither changes that cell nor asks Excel to rebuild the curve, so a missing object where this contract promises one is a runtime failure, reported, never substituted, never answered from a previous result. Collecting objects proven unused is a different thing from evicting live ones, and an optional cache of calculated results may discard an answer that can be recomputed from available inputs but never the input objects: construction reuse, calculation reuse and object lifetime are three separate responsibilities.

Saving a workbook preserves formulas, names, inputs and possibly the displayed handle text; it does not persist the store. Reopening rebuilds fresh objects through creator execution, never by reconnecting saved tokens, and handle text from a previous runtime never resolves to an unrelated new object: the session part of the text sees to that today. When that calculation runs, including in manual mode, is open.

## Publication and release

The first column below is built: a creator's cell shows what the table says. The release in the third, fifth and sixth rows is not: today the old object stays in the store, and the table is the contract release will meet.

| Worksheet action | Creator cell | Consumer |
|---|---|---|
| supply a valid table | displays `curve:17` | a reference supplies `curve:17`; the seam resolves it |
| recalculate, inputs unchanged | is to reuse this creator's existing object and handle, with no new publication number; today publishes `curve:18` | resolves the same object without reconstruction, or today the new one |
| change a factor to another valid value | publishes a new immutable curve, displays `curve:18`, releases the creator's old entry for `curve:17` | Excel propagates; the same formula now receives `curve:18` |
| supply invalid data | shows the construction error, publishes no replacement | receives the failure through the seam's error path |
| delete the creator | releases its current ownership promptly; other creators stay valid | |
| close its workbook | releases that workbook's creator ownership promptly; references still needed elsewhere stay valid | |

The old object is never mutated or retargeted; there is no retained version history, and the numbers in this table are not a history we keep. Failed construction or publication must not present the previous handle as a successful answer for new inputs and must leave no abandoned temporary ownership; built: a creator that fails publishes nothing and moves no number. Dropping a store entry and freeing its object are different events: the entry owns a reference, removing it releases that reference, and a running calculation or another retained object may still hold its own, which protects the data until its final user lets go without keeping the old text resolvable. For a fixed workbook with no retained old dependencies, repeated replacements settle back to the expected live object count; temporary overlap while updates finish is expected, keeping every abandoned version is not. In manual calculation mode, editing inputs promises no immediate propagation; when the user requests calculation, creator and dependents update in Excel's dependency order, and the runtime never invalidates a still-retained object merely because no lookup happened recently.

## Errors are text

The seam returns failures as text beginning `#ERROR `, not as Excel error values. A failed creator's cell holds that text, and a consumer referring to it receives the text as its handle argument. The resolver recognises the prefix and fails as *the creator failed*, carrying the creator's own text whole at the end, `curve is the creator's failure, expected discount curve handle: #ERROR _CreateDiscountCurve: ...`, not as an unknown handle, which would send the user looking for a store problem that does not exist. A consumer of that consumer relays the same text: the creator's failure is taken out of the relay and carried on unchanged, never quoted again, so a chain of any length shows one message. Built.

## The seam's part

Built, in [bridge.md](bridge.md#a-handle-one-store-and-the-text): the declared result rule that keeps a verified object and returns its text, the argument rule that resolves text to the expected kind so a function receives the object and never the text, and the one store, a dictionary in the bridge from text to the verified kind and a strong Python reference. Registration selects the two rules from the declaration once, one mechanism for every kind, so adding a kind adds no store and no code of its own; the verified kind comes from the declaration, not from the handle's prefix; and errors beginning `#ERROR ` stay failures and are never published.

What remains is host lifecycle integration, so that a creator's deletion or its workbook's closing releases what it owned, and reuse on an unchanged recalculation, which needs the same creator tracking. The host hooks no Excel event today. Two ways of building it were researched, with the evidence in [excel-dna-handles.md](excel-dna-handles.md). Excel-DNA's own object handler, in the version the host references, tracks a creator through Excel's live-data subscription and disposes its object when the formula goes away; but it shares one object between creator cells with equal inputs, which this contract forbids, pays a caller lookup, a hash of the whole input and one extra Excel call on every recalculation of a creator, and is documented as unreliable inside array formulas. Shipped add-ins with handles do something plainer: remember which cell made each object, replace that cell's previous object on its next recalculation, purge everything on workbook close, and accept that a deleted creator's object waits for the close. Either way the store and the text stay as built, and the choice is made on counts: correct worksheet behaviour first, then the work per creator recalculation, then retained memory, measured on whole calls.

## Acceptance scenarios

Held by tests today: a direct reference supplies the current handle and resolves the typed object (the smoke rows); duplicate creators give distinct handles and distinct objects; a pasted literal, an old-session token and a handle of another kind fail, named; a creator's failure is relayed as the creator's; a failed creator publishes nothing. The rest wait for release. Deterministic counts for construction, transport, copies, lookup, publication and release; retained bytes with shared ownership counted once; timing as evidence, never a gate.

| Scenario | What must hold |
|---|---|
| a consumer uses a direct cell reference, or a name referring to it | both supply the current handle and resolve the correct typed object |
| an unchanged creator recalculates | reuses the active object and handle without a new publication number; preparation is measured as well as publication and lookup |
| a valid factor change | the creator publishes the new curve; consumers update through existing references; retained old objects are unchanged |
| an invalid factor change | creator and dependents show the failure; no handle is published for the invalid inputs |
| manual calculation | owned objects survive between calculation requests; a requested calculation follows Excel's dependency order |
| insert rows, sort a table, cut and paste a formula block, move across sheets, rename a name | values and references follow Excel's semantics; no cell-slot collision, no false second-producer error |
| duplicate creator formulas, then remove one | distinct handles resolve distinct objects; removing one releases only its ownership |
| a future batch holds two identical trade rows | both stay distinct objects; the creator owns the batch; spill and error rules are agreed before they are tested |
| replace or delete a creator while another retained object uses its old curve | the dependent keeps valid immutable data; release happens when its final owner is gone |
| repeated replacements with fixed input sizes and no retained old dependencies | old entries do not accumulate; live objects and retained data return to the expected level |
| a live object's store entry is deliberately removed in a diagnostic test | the failure is visible; any promised recovery is verified |
| a pasted literal, an old-session token, a diagnostic display | none acquires ownership by appearing as text; unknown, expired and wrong-kind values fail |
| close one of several workbooks | that book's creator ownership is released promptly; other creators and retained dependencies stay valid |
| reopen a workbook | creator execution builds fresh objects; old tokens do not reconnect |
| undo and interrupted calculation | promises agreed first, then exercised in Excel |

## The first proof

1. `_CreateValuationDate`: create, retain, return a handle, resolve in a consumer. Done in #53, with distinct objects for two identical creators and a failed creator publishing nothing; independent cleanup and unchanged-creator reuse wait for release.
2. Worksheet lifetime and memory: replacement, deletion, moves, closing one of several books, fresh reopen, manual calculation, failures, retained dependencies; repeated edits accumulate no unowned objects; store entries and retained objects counted, shared data once; process memory alone is not an object-lifetime measurement. Open.
3. `_CreateDiscountCurve`: the same path with numpy arrays, done in #53 for construction, with the curve's two arrays copied and frozen; its release waits with step 2.
4. Batch returns: duplicate-row separation, row-to-handle pairing, replacement and release of the owned batch, resizing and failure cleanup, after the return and error rules are agreed. Open.

Concurrent calls must not multiply ownership, and no publication scans the store.

## Open

Every open question here is release, decided by the next handle pull request with counts: creator tracking and callback timing, including safe shutdown; the batch spill's declaration, row errors, blocked spill, resizing and partial reuse; the equality key and the preparation work for unchanged-creator reuse; whether moving a creator may rebuild its objects or must keep their handles; reopen calculation timing, interrupted calculation, undo and unexpected loss.
