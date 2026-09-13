# Handles

Open: D26.

A handle is opaque text in a cell that stands for an object the add-in holds in memory, such as a curve. Excel owns the worksheet's dependency graph; the runtime owns the retained objects; the seam resolves the current handle value to the expected Python object. This page is the seam's spec for handles, written the way a function page is: what a workbook author may rely on, what the seam must do, and what is still open. Why these choices and what they cost is [decisions.md](../library/decisions.md#handles), D22 to D26; the evidence behind the store candidates is [excel-dna-handles.md](excel-dna-handles.md). When handles are built, this page's content moves into [inputs.md](inputs.md), [outputs.md](outputs.md) and [bridge.md](bridge.md), and the page goes.

## A small object first

```excel
A2   11-Sep-2026
B2   0.5
C2   =CreateValuationDate(A2, B2)
```

The builder creates a Python object holding a numpy day and a float. The seam retains that object and displays a handle in `C2`. Another formula refers to `C2`, or to a defined name referring to it; the seam resolves the handle once and hands the library the object. Reading it does not rebuild it. One valuation-date creator per workbook is the expected case, not an enforced singleton: the mechanism must hold many independent objects.

## The worksheet workflow

A creator formula returns a handle into its cell. A consumer refers to that cell, directly or through an Excel defined name referring to it. Workbook authors connect formulas with Excel's own references and names; they do not maintain handle strings.

```excel
Data!A1:B1    date / df headers
Data!A2:B15   the daily table

Inputs!B2     =CreateDiscountCurve(Data!A1:B1, Data!A2:B15)
              displays curve:17

Defined name  DeskCurve refers to =Inputs!$B$2
```

A consumer's curve argument may be `Inputs!$B$2` or `DeskCurve`. Excel tracks the dependency either way and passes that cell's current value to the seam, which resolves it once. The library never receives, parses or looks up a worksheet address or name. `DeskCurve` is an Excel name for a cell, not a second object registry, a permanent alias, or the curve's content identity.

Supported: cell references, and defined names referring to cells. An ordinary formula relaying a creator's value is still an Excel dependency, not an independent owner. Renaming a name, inserting rows or moving formulas follows Excel's own reference behaviour. Not supported: pasting a handle as a value, typing one into a formula, assigning the literal text to a defined name, or carrying one outside the workbook's dependency chain; none of these acquires ownership or a persistence promise. This is a usage contract, not a claim that the seam can reject every literal: a live handle may resolve however it reached the argument, since rejecting on worksheet provenance would need host information that does not exist. What is required is that unknown, expired and wrong-kind values fail visibly, and matching-looking text never selects an unrelated object.

## The handle's text

Four colon-separated parts, all lowercase: `object_type:readable_label:session_id:counter`.

| Part | Meaning |
|---|---|
| `object_type` | a lowercase type tag with underscores between words: `valuation_date`, `discount_curve`, `trade`; Python types and worksheet functions keep their PascalCase names |
| `readable_label` | a readable lowercase label with underscores; labels need not be unique and do not identify an object on their own; its source and normalization are open |
| `session_id` | an identifier for this running object-store session, changed whenever the counter resets; its generation, spelling and length are open |
| `counter` | one decimal publication number starting at 1, padded to at least six digits, shared by every object type and workbook using the store |

```text
valuation_date:valuation:<session>:000001
discount_curve:curve_a:<session>:000002
trade:summer_swap:<session>:000003
```

The counter is a publication number, not a version, an array index, a per-type sequence or a count of live objects. A new publication takes the next number; a batch publishing two distinct objects takes two, even for identical rows; removing entries never recycles numbers; closing a workbook does not reset the counter of a runtime that stays open; six digits is a minimum width, and the counter grows past it without wrapping. A new runtime may start at `000001` because its session identifier changes, so saved text from an old session never resolves to an unrelated object. The full, exact text is the lookup key: a consumer neither looks up a label alone nor normalizes a supplied handle, and the stored, verified kind establishes the object's type; the visible prefix describes it and proves nothing. The short forms `curve:17` and `curve:18` below abbreviate this text to explain ownership; they are not accepted formats.

## Separate objects and shared dependencies

Separate creator formulas publish separate immutable objects and handles, even with identical inputs. Separate trade rows within one batch remain separate objects: two identical trade rows are two trades. Distinct handles around one shared object do not satisfy this. Recalculating the same creator is not a separate creator: unchanged inputs reuse its current objects and handles and consume no new publication numbers; the equality key and the preparation work behind that reuse are open. Objects may hold references to the same dependency: two independent trades may use one valuation date or curve without copying it.

A creator may own several published objects. The working proposal for a creator that takes several rows is one handle per row, spilled as a column:

| Input to one creator | Output | Retained |
|---|---|---|
| row 1, trade details X | `trade:17` | trade object A |
| row 2, identical details X | `trade:18` | trade object B |

One creator formula owns the batch; a successful replacement releases the previous batch, deleting the creator releases its batch, and the duplicate rows never collapse into one object. Row positions describe input-to-output pairing, not persistent identity. The declaration, the row-error policy, blocked-spill behaviour, resizing, and partial reuse of unchanged rows when others change are open under D26; one handle per row is a proposal, not a supported result today, and no public trade function is specified here.

## Who owns what

| Layer | Owns |
|---|---|
| Excel | references and names, calculation scheduling and order, displaying creator values and failures |
| the host and the seam | publishing and resolving handles, enforcing the declared object kind at the boundary, retaining and releasing the Python references they own |
| the library | building valid immutable objects, consuming typed objects, retaining the Python dependencies its own objects need; it never navigates worksheets and never imports the Excel bridge |

A live creator owns its currently published object or batch. A lookup, or another cell displaying its value, is not a separate ownership record. A running calculation keeps the references it needs for its call. A retained object that depends on another holds its own strong Python reference, which can keep the underlying object alive after the original creator moves on. Spill cells belong to their creator's output. Cell addresses locate formulas: they must not become object identities, cache keys or permanent producer slots, and a moved formula follows Excel's rules without colliding with whatever previously occupied the destination or being treated as an unauthorized second producer (D23).

## A missing object is a failure, not a cache miss

Cleanup must not delete an object a live creator owns or a retained dependency needs; no age or capacity limit evicts the object behind a valid handle to admit another, and if a capacity policy is ever introduced, failed new construction leaves existing owned objects valid. Excel sees the value in the creator cell, not the store: removing the object behind `curve:17` neither changes that cell nor asks Excel to rebuild the curve, so a missing object where this contract promises one is a runtime failure, reported, never substituted, never answered from a previous result (D24). Collecting objects proven unused is a different thing from evicting live ones, and an optional cache of calculated results may discard an answer that can be recomputed from available inputs but never the input objects: construction reuse, calculation reuse and object lifetime are three separate responsibilities.

Saving a workbook preserves formulas, names, inputs and possibly the displayed handle text; it does not persist the store. Reopening rebuilds fresh objects through creator execution, never by reconnecting saved tokens, and handle text from a previous runtime never resolves to an unrelated new object. When that calculation runs, including in manual mode, is open.

## Publication and release

| Worksheet action | Creator cell | Consumer |
|---|---|---|
| supply a valid table | displays `curve:17` | a reference supplies `curve:17`; the seam resolves it |
| recalculate, inputs unchanged | reuses this creator's existing object and handle; no new publication number | resolves the same object without reconstruction |
| change a factor to another valid value | publishes a new immutable curve, displays `curve:18`, releases the creator's old entry for `curve:17` | Excel propagates; the same formula now receives `curve:18` |
| supply invalid data | shows the construction error, publishes no replacement | receives the failure through the seam's error path |
| delete the creator | releases its current ownership promptly; other creators stay valid | |
| close its workbook | releases that workbook's creator ownership promptly; references still needed elsewhere stay valid | |

The old object is never mutated or retargeted; there is no retained version history, and the numbers in this table are not a history we keep. Failed construction or publication must not present the previous handle as a successful answer for new inputs and must leave no abandoned temporary ownership. Dropping a store entry and freeing its object are different events: the entry owns a reference, removing it releases that reference, and a running calculation or another retained object may still hold its own, which protects the data until its final user lets go without keeping the old text resolvable. For a fixed workbook with no retained old dependencies, repeated replacements settle back to the expected live object count; temporary overlap while updates finish is expected, keeping every abandoned version is not. In manual calculation mode, editing inputs promises no immediate propagation; when the user requests calculation, creator and dependents update in Excel's dependency order, and the runtime never invalidates a still-retained object merely because no lookup happened recently.

## Errors are text

The seam returns failures as text beginning `#ERROR `, not as Excel error values. A failed creator's cell holds that text, and a consumer referring to it receives the text as its handle argument. The resolver recognises the prefix and fails as *the creator failed*, quoting its message, not as an unknown handle, which would send the user looking for a store problem that does not exist.

## The seam's part

Today the result rules in [bridge.py](../../src/goosedove/excel/bridge.py) send scalars and numerical arrays, no rule retains an object, and an unknown return type refuses registration; returning text alone would add no retention, no kind-aware resolution and no lifetime. Building handles needs four pieces, kept out of the pricing library: a declared result rule that retains a verified object and returns its text; an argument rule that resolves text to the expected object kind, so a function receives the object and never the text; one store; and host lifecycle integration, so a creator's deletion or its workbook's closing releases what it owned. Registration selects the publication and resolution operations once from the declared types, one mechanism for every object kind, so adding a kind adds no store and no cleanup code of its own; the verified kind comes from the declaration, not from the handle's prefix. `-> ValuationDate` and `-> Handle[ValuationDate]` are illustrative spellings of the declaration; the library produces the domain object and any wrapper is the seam's. Errors beginning `#ERROR ` stay failures and are never published as objects.

The recommended first candidate splits the work in two: the host tracks creator lifetimes and sends publication and release notifications, and the seam holds one map from handle text to verified kind and strong Python reference, publishing, resolving and releasing entries; the library builds immutable objects and calculates with typed ones, seeing no handle.

```text
Excel creator  -> the host and the seam -> the Python builder -> one Python store: curve:17 -> curve object
Excel consumer -> handle argument -> Python lookup -> the existing curve object
Excel lifetime ends -> host cleanup notification -> Python releases the entry
```

On the host, the native path for a tracked creator is Excel disconnecting its RTD subscription when the formula is removed, Excel-DNA invoking that subscription's cleanup callback, and the associated ownership being released; the callback already holds the ownership information and searches no cell text, and deleting a relay cell or a pasted token releases nothing. Our host does not activate that path today, and the adaptation is unproved: native tracking groups equal function-and-argument calls and shares their object, which conflicts with separate creator objects, and it does not provide the batch spill. Creator-specific tracking through recalculation, moves and deletion has to be demonstrated, cell addresses must not become keys, a fresh random key on every invocation is no reuse or lifetime solution, and workbook-close and interpreter-shutdown cleanup need their own verification.

A store in C# over Excel-DNA's own object handler is the alternative: a managed owner retaining one Python reference, resolving the right Python kind and acquiring and releasing references safely, with native tracking adapted to our occurrence rules. It needs no copying of Python fields into C#, but it must not retain a temporary Python wrapper the current call disposes, and a dependent Python object needs its own reference to the underlying object. Either choice needs safe Python access during callbacks and cleanup before interpreter shutdown. Choose by evidence: correct worksheet behaviour first, then the custom ownership work, constructions, lookups, copies and retained memory, measured on whole calls with small records and array-bearing objects; a faster isolated dictionary lookup is not a reason. Python is the first recommendation because creation, argument preparation and consumption already happen there; C# wins if its native store demonstrably removes enough lifecycle coordination or measures a material gain without added ownership complexity. Nothing has been measured. The source facts behind all of this are in [excel-dna-handles.md](excel-dna-handles.md).

## Acceptance scenarios

Planning cases, to be built with the first proof. Deterministic counts for construction, transport, copies, fingerprinting, lookup, publication, scans and release; retained bytes with shared ownership counted once; timing as evidence, never a gate.

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

1. `CreateValuationDate`: create, retain, return a handle, resolve in a test-only consumer, release. Two identical creators, distinct objects, independent cleanup; one unchanged creator recalculated, with its object, handle and publication count unchanged; the argument-preparation work under a measured budget.
2. Worksheet lifetime and memory: replacement, deletion, moves, closing one of several books, fresh reopen, manual calculation, failures, retained dependencies; repeated edits accumulate no unowned objects; store entries and retained objects counted, shared data once; process memory alone is not an object-lifetime measurement.
3. `CreateDiscountCurve`: the same ownership path with numpy arrays; its input layout is D21 and is not settled through a handle prototype.
4. Batch returns: duplicate-row separation, row-to-handle pairing, replacement and release of the owned batch, resizing and failure cleanup, after the return and error rules are agreed.

Concurrent calls must not multiply ownership, and no publication scans the store.

## Open

Every open question here is D26, which says what would decide it: the store, creator tracking and callback timing, including safe shutdown; the return declaration, and the batch spill rules, its declaration, row errors, blocked spill, resizing and partial reuse; the label's source and normalization, and the session token's generation and spelling; the equality key and the preparation work for unchanged-creator reuse; whether moving a creator may rebuild its objects or must keep their handles; reopen calculation timing, interrupted calculation, undo and unexpected loss.
