# Handles

Open: release and reuse, below.

A handle is text in a cell that stands for an object the add-in holds in memory, such as a curve. Excel owns the worksheet's dependency graph; the seam owns the retained objects and resolves the current handle value to the Python object; the library builds and consumes objects and never sees the text. Built in #53: the declaration `Handle[Kind]`, one store, the handle's text, publishing on the way out and resolving on the way in, with every failure as text in the cell. Those parts now live where the seam's built things live, [inputs.md](inputs.md) decisions 34 to 37, [outputs.md](outputs.md) decisions 10 to 12 and [bridge.md](bridge.md#a-handle-one-store-and-the-text), and this page keeps what a workbook author may rely on and what is still open: release when a creator is deleted or its workbook closes, reuse of the same handle on an unchanged recalculation, and batches of one handle per row. Today every creator call publishes a new object, and the store holds it until Excel closes. The evidence behind the ways of building release is [excel-dna-handles.md](excel-dna-handles.md). When release is built, the rest of this page moves the same way and the page goes.

## A small object first

```excel
A2   11-Sep-2026
B2   0.5
C2   =_CreateValuationDate(A2, B2)      displays valuation_date:1
```

The shared workbook `workbooks/handles.xlsx` holds this sheet, the curve's, and a block for each creator built since, its inputs and creator on the left and `util_ReadHandle` spilling the object on the right, with a `notes` column for whoever is looking at it: `.\tools\excel_dev.ps1 workbooks\handles.xlsx` opens it with the add-in, and `.\tools\excel_show.ps1 workbooks\handles.xlsx` prints it as its cells show.

The creator builds a Python object holding a numpy day and a float. The seam retains that object and displays its handle in `C2`. Another formula refers to `C2`, or to a defined name referring to it; the seam resolves the handle once and hands the library the object. Reading it does not rebuild it. One valuation-date creator per workbook is the expected case, not an enforced singleton: the store holds many independent objects.

## The worksheet workflow

A creator formula returns a handle into its cell. A consumer refers to that cell, directly or through an Excel defined name referring to it. Workbook authors connect formulas with Excel's own references and names; they do not type or copy handle text.

```excel
Data!A1:B1    date / discount_factor headers
Data!A2:B15   the daily table

Inputs!B2     =_CreateDiscountCurve(Data!A1:B1, Data!A2:B15)
              displays discount_curve:17

Defined name  DeskCurve refers to =Inputs!$B$2
```

A consumer's curve argument may be `Inputs!$B$2` or `DeskCurve`. Excel tracks the dependency either way and passes that cell's current value to the seam, which resolves it once. The library never receives, parses or looks up a worksheet address or name. `DeskCurve` is an Excel name for a cell, not a second object registry, a permanent alias, or the curve's content identity.

Supported: cell references, and defined names referring to cells. An ordinary formula relaying a creator's value is still an Excel dependency, not an independent owner. Renaming a name, inserting rows or moving formulas follows Excel's own reference behaviour. Not supported: pasting a handle as a value, typing one into a formula, assigning the literal text to a defined name, or carrying one outside the workbook's dependency chain; none of these acquires ownership or a persistence promise. This is a usage contract, not a claim that the seam can reject every literal: a live handle resolves however it reached the argument, since rejecting on worksheet provenance would need host information that does not exist. Text absent from the store and handles of the wrong stored kind fail visibly. A saved handle can equal a different object's handle after a runtime restart; see [the known limitation](#known-limitation-saved-handles-after-restart).

## The handle's text

Built in #53 as `kind:session:number`; `kind:index-name:count` and `kind:count` since #113, the name of the index where the object carries one and the publication count alone, the session part gone.

Two forms, the tags lowercase, colons between the parts:

```text
kind:index-name:count
kind:count
```

| Part | Meaning |
|---|---|
| `kind` | the kind's tag, its class name in lowercase words joined by underscores: `valuation_date`, `market_history`; Python types and worksheet functions keep their PascalCase names |
| `index-name` | the name the index was created with, `_CreateIndex`'s first argument, read off the stored object when it is published and written whole as typed: case, spaces, punctuation, colons and any character kept, nothing trimmed, re-cased or shortened; present for the eight kinds below, absent for the rest |
| `count` | the runtime's publication count, a plain number with no padding: 1 for the first object published after Python starts, then 2, shared by every kind and every workbook open in that Excel, never reset and never repeated while Python runs |

| Object | Shows | The name read from |
|---|---|---|
| index | `index:WTI:31` | its own `name` |
| calendar | `calendar:WTI:32` | `index.name` |
| futures fixings | `futures_fixings:WTI:33` | `index.name` |
| IFERC fixings | `iferc_fixings:HNG:41` | `index.name` |
| Gas Daily fixings | `gas_daily_fixings:HNG:45` | `index.name` |
| market history | `market_history:WTI:34` | `calendar.index.name` |
| price vector | `price_vector:WTI:35` | `index_name`, the text typed to `_CreatePriceVector` since #112 |
| market | `market:WTI:36` | `market_history.calendar.index.name` |
| valuation date, discount curve | `valuation_date:1`, `discount_curve:2` | none |
| the three schedules, the holiday calendar, the conventions, the contract specifications | `futures_schedule:12`, `holiday_calendar:13`, `index_conventions:14`, `contract_specifications:15` | none: an index uses them, which names them nothing, and their creators gain no argument |

A name is written as it was typed, so `market_history:Henry Hub NYMEX:34` keeps its space, the workbook's `market_history:Sample futures index, closed 25 May:212` its comma, `index:Henry Hub: Gas Daily:50` its colon, three in that text, and `index:Brent Dated €/bbl:51` its characters. Two indices of one name are `index:WTI:7` and `index:WTI:9`, told apart by the count alone. A price vector shows the name it was typed with, so `price_vector:wti nymex:37` beside `market_history:WTI NYMEX:34` shows the mismatch the [market](../library/market/market.md) will refuse, before it does.

The count is a publication count, not a version, an array index, a per-kind sequence or a count of live objects. A new publication takes the next number; a failed creator moves it not at all; reading a handle publishes nothing and moves nothing; removing entries never recycles numbers; closing a workbook does not reset the count of a runtime that stays open. The full, exact text is the lookup key: a consumer neither looks up a part alone nor normalizes a supplied handle, nothing in the seam or the library splits the text, and the stored, verified kind establishes the object's type; the visible tag and the name describe the object and prove nothing. An edited name, an edited count or a number not yet published fails as text naming no live object, `market_history is text 'market_history:Brent:34' naming no live object, expected market history handle`, and a live handle of another kind fails by its stored kind, `market_history is price vector handle 'price_vector:WTI:35', expected market history handle`. The readable label dropped on 2026-09-13, when nothing supplied one, returns as the index's name, which #107 and #112 supply. The short forms `curve:17` and `curve:18` below shorten the tag to explain ownership; a real text reads `discount_curve:17`.

The seam formats the text once, at publication, in the one publication path. Registration reads the declared result kind and prepares, once, the path to that kind's name, `index.name` for a calendar, `market_history.calendar.index.name` for a market, none for a schedule, so publishing reads two or three attributes and builds one string, with no scan, no hash of contents and no search of the store; the library's records hold their data and learn nothing of handles. Before the entry is stored, the whole text is measured as Excel counts text, in UTF-16 units, against the 32,767 the text-out rule already holds ([outputs.md](outputs.md)); a longer text fails in the result voice, `returned handle of 32790 characters, expected at most 32767`, nothing truncated, nothing stored and the count unmoved. Only a name of some 32,740 characters reaches it.

The count starts again when Python starts, so handle text can repeat between runtimes. A saved text names nothing unless the new runtime publishes the same kind, name where present, and count. If that happens, lookup cannot distinguish the saved text from the new publication. Two workbooks open in one Excel share the store and the count, each creator cell publishing its own object; a second Excel started as its own program is a second Python with a store of its own. Recalculation on open belongs to release, below.

### Known limitation: saved handles after restart

Recorded during review of #113 on 26 September 2026, at `c687940`. The owner chose to retain the shorter handle format and document this case for future handle-lifecycle work. No immediate behavior change is requested.

The reproduced case requires a creator formula to retain its saved handle after a runtime restart, a new publication to acquire exactly the same handle text, and a consumer to calculate before the saved creator is recalculated. Manual calculation permits that ordering. Within one runtime the publication count does not repeat; merely creating two vectors for one index does not collide.

Native Excel reproduction, using that revision's `workbooks/handles.xlsx` opened read-only in a fresh Excel process with manual calculation selected before opening it:

1. Leave `handles!B677` uncalculated. Its saved formula is `_CreatePriceVector(B1231,A672:A675)`, its cached handle is `price_vector:Sample futures index:6`, and its first source price in `A672` is `74.25`.
2. On a temporary sheet put `999` in `A1` and `_CreatePriceVector(handles!B1231,A1)` in `B1`. Calculate this second creator until it publishes `price_vector:Sample futures index:6`, keeping the original creator uncalculated.
3. Calculate `=INDEX(util_ReadHandle(handles!B677),3,1)` on the temporary sheet. It returns `999`, the new vector's price, although it references the original creator whose source price is `74.25`.

No handle was pasted or typed as a value. The test deliberately arranged a second vector with the same index name and advanced the count to match; it establishes that a collision is possible, not how often it occurs in desk use. One history per index does not prevent this case. Unnamed kinds, such as valuation dates, need only the same kind and count to match across runtimes.

When diagnosing a wrong object after a restart, check calculation mode, whether the referenced creator has run in the current runtime, and whether another publication has acquired its saved text. Recalculate the creators and their consumers before relying on their results. Automatic handling of saved creator results, including manual calculation and partial-sheet calculation, remains a decision for the handle-lifecycle work; this note does not choose a mechanism or add a startup hook.

### Tests

The texts are pinned in `tests/unit/test_handles.py` with the seam's own two kinds and in each creator's test file with its own; the reader's are in `tests/unit/test_utilities.py`; the ledgers are `tests/performance/test_seam_budgets.py` and the ceilings `tests/performance/test_seam_allocation.py`; the smoke rows are `tools/excel_smoke.ps1` and their replay `host/Goosedove.Host.Tests/CallTests.cs`; `workbooks/handles.xlsx` shows its named indices side by side with their fixings, calendars, histories, vectors and markets.

| Case | Kind |
|---|---|
| each of the eight kinds shows its index's name as typed, and every other kind its tag and count alone | example, through the seam |
| a name in another case, with spaces, with a colon, with Unicode: shown whole; two publications with one label differ by count | example, through the seam |
| the count starts at 1, rises by one per publication across kinds, and moves on no failed creator and no read | example, through the seam |
| an edited name, an edited count and a number not yet published fail as text naming no live object; a handle of another kind fails by its stored kind; a creator's failure is relayed; a failed creator publishes nothing | example, through the seam |
| a name long enough to take the text past 32,767 units fails in the result voice, with no store entry and the count unmoved | example, through the seam |
| every creator's ledger keeps its calls, or gains one for the name, and keeps its numpy calls; every ceiling unchanged, the text growing by the name's length only | work and allocation budget |
| a direct reference, a defined name and `util_ReadHandle` resolve the same objects as before, and every spill is unchanged | Excel smoke and host replay |

#113 rewrote the text where it was written: [bridge.md](bridge.md#a-handle-one-store-and-the-text), [outputs.md](outputs.md) decisions 8 and 11 and [inputs.md](inputs.md) decision 35's sample, the handle row of [conventions.md](../library/conventions.md), [history.md](history.md), the sample handle on every library page, fifteen patterns and four count-reading helpers in the tests, and `test_handles.py`'s three-part reader. The smoke's rows read a handle's start with `LEFT` and stand; the workbook's handle cells are formulas and rewrite themselves on a full calculation, its notes' sample texts refreshed by hand. No alias for the old text: a saved workbook shows the new text after its first calculation.

### Not here

Enforcing one index per name: separate work, when the owner wants it; the label helps the eye and checks nothing. Persisting the store, reconnecting saved text, release when a creator is deleted or its workbook closes, reuse on an unchanged recalculation, recalculation on open: release, below. No label for the schedules, the holiday calendar, the conventions or the specifications, and no argument added to any creator. No change to `Handle[object]`, to `util_ReadHandle` or to any spill.

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

Saving a workbook preserves formulas, names, inputs and possibly the displayed handle text; it does not persist the store. Creator execution after reopening builds fresh objects. Until a creator runs, its saved text may fail lookup or resolve to a different publication as described in [the known limitation](#known-limitation-saved-handles-after-restart). When that calculation runs, including in manual mode, and whether the add-in requests it when a workbook opens, is open.

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

Held by tests today: a direct reference supplies the current handle and resolves the typed object (the smoke rows); duplicate creators give distinct handles and distinct objects; text naming no live entry and a handle of another kind fail, named; a creator's failure is relayed as the creator's; a failed creator publishes nothing. These tests do not establish that saved text cannot resolve to a different publication after restarting; the manual-calculation reproduction above records that limitation. The rest wait for release. Deterministic counts for construction, transport, copies, lookup, publication and release; retained bytes with shared ownership counted once; timing as evidence, never a gate.

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
| a pasted literal, a text from an earlier runtime, a diagnostic display | none acquires ownership by appearing as text; unknown, expired and wrong-kind values fail |
| close one of several workbooks | that book's creator ownership is released promptly; other creators and retained dependencies stay valid |
| reopen a workbook | creator execution builds fresh objects; handling uncalculated saved creator results remains open, with the collision case recorded above |
| undo and interrupted calculation | promises agreed first, then exercised in Excel |

## The first proof

1. `_CreateValuationDate`: create, retain, return a handle, resolve in a consumer. Done in #53, with distinct objects for two identical creators and a failed creator publishing nothing; independent cleanup and unchanged-creator reuse wait for release.
2. Worksheet lifetime and memory: replacement, deletion, moves, closing one of several books, fresh reopen, manual calculation, failures, retained dependencies; repeated edits accumulate no unowned objects; store entries and retained objects counted, shared data once; process memory alone is not an object-lifetime measurement. Open.
3. `_CreateDiscountCurve`: the same path with numpy arrays, done in #53 for construction, with the curve's two arrays copied and frozen; its release waits with step 2.
4. Batch returns: duplicate-row separation, row-to-handle pairing, replacement and release of the owned batch, resizing and failure cleanup, after the return and error rules are agreed. Open.

Concurrent calls must not multiply ownership, and no publication scans the store.

## Open

Every open question here is release, decided by the next handle pull request with counts: creator tracking and callback timing, including safe shutdown; the batch spill's declaration, row errors, blocked spill, resizing and partial reuse; the equality key and the preparation work for unchanged-creator reuse; whether moving a creator may rebuild its objects or must keep their handles; whether the add-in requests a full calculation when a workbook opens, which would remove stale text as a state, and reopen calculation timing otherwise; interrupted calculation, undo and unexpected loss.
