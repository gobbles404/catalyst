# Handles

Built through #113: the text, publishing and resolving. Built in #114: release when a creator goes and reuse of an unchanged creator, through Excel's live-data subscription, in [Publication and release](#publication-and-release) and [The seam's part](#the-seams-part). Built in #116: the process ID first in every handle, in [The handle's text](#the-handles-text). Open: batches of one handle per row.

A handle is text in a cell that stands for an object the add-in holds in memory, such as a curve. Excel owns the worksheet's dependency graph; the seam owns the retained objects and resolves the current handle value to the Python object; the library builds and consumes objects and never sees the text. Built in #53: the declaration `Handle[Kind]`, one store, the handle's text, publishing on the way out and resolving on the way in, with every failure as text in the cell. Those parts now live where the seam's built things live, [inputs.md](inputs.md) decisions 34 to 37, [outputs.md](outputs.md) decisions 10 to 12 and [bridge.md](bridge.md#a-handle-one-store-and-the-text), and this page keeps what a workbook author may rely on, what is ready to ship and what is still open. Built in #114: release when a creator is deleted or its workbook closes, and reuse of one object and handle while a creator call with the same arguments is live, both through Excel's live-data subscription, the channel Excel uses to tell an add-in that a formula's value is wanted and, later, that it is not. Open: batches of one handle per row. The evidence behind the way release was built is [excel-dna-handles.md](excel-dna-handles.md).

## A small object first

```excel
A2   11-Sep-2026
B2   0.5
C2   =_CreateValuationDate(A2, B2)      displays 30512:valuation_date:1
```

The shared workbook `workbooks/handles.xlsx` holds this sheet, the curve's, and a block for each creator built since, its inputs and creator on the left and `util_ReadHandle` spilling the object on the right, with a `notes` column for whoever is looking at it: `.\tools\excel_dev.ps1 workbooks\handles.xlsx` opens it with the add-in, and `.\tools\excel_show.ps1 workbooks\handles.xlsx` prints it as its cells show.

The creator builds a Python object holding a numpy day and a float. The seam retains that object and displays its handle in `C2`. Another formula refers to `C2`, or to a defined name referring to it; the seam resolves the handle once and hands the library the object. Reading it does not rebuild it. One valuation-date creator per workbook is the expected case, not an enforced singleton: the store holds many independent objects.

## The worksheet workflow

A creator formula returns a handle into its cell. A consumer refers to that cell, directly or through an Excel defined name referring to it. Workbook authors connect formulas with Excel's own references and names; they do not type or copy handle text.

```excel
Data!A1:B1    date / discount_factor headers
Data!A2:B15   the daily table

Inputs!B2     =_CreateDiscountCurve("SOFR", Data!A1:B1, Data!A2:B15)
              displays 30512:discount_curve:SOFR:17

Defined name  DeskCurve refers to =Inputs!$B$2
```

A consumer's curve argument may be `Inputs!$B$2` or `DeskCurve`. Excel tracks the dependency either way and passes that cell's current value to the seam, which resolves it once. The library never receives, parses or looks up a worksheet address or name. `DeskCurve` is an Excel name for a cell, not a second object registry, a permanent alias, or the curve's content identity.

Supported: cell references, and defined names referring to cells. An ordinary formula relaying a creator's value is still an Excel dependency, not an independent owner. Renaming a name, inserting rows or moving formulas follows Excel's own reference behaviour. Not supported: pasting a handle as a value, typing one into a formula, assigning the literal text to a defined name, or carrying one outside the workbook's dependency chain; none of these acquires ownership or a persistence promise. This is a usage contract, not a claim that the seam can reject every literal: a live handle resolves however it reached the argument, since rejecting on worksheet provenance would need host information that does not exist. Text absent from the store and handles of the wrong stored kind fail visibly, a text from another Excel among them. A saved handle can equal a different object's handle after a restart only when Windows has given the new Excel the old one's process ID; see [the known limitation](#known-limitation-a-reused-process-id-after-a-restart).

## The handle's text

Built in #53 as `kind:session:number`; `kind:index-name:count` and `kind:count` since #113, the name of the index where the object carries one and the publication count alone, the session part gone. Built in #116, the owner's ticket of 27 September 2026: the process ID first, `pid:kind:index-name:count` and `pid:kind:count`, so that two Excels running at once never show one text for two objects, and an engineer reading a handle can tell which Excel made it.

Two forms, the tags lowercase, colons between the parts:

```text
pid:kind:index-name:count
pid:kind:count
```

| Part | Meaning |
|---|---|
| `pid` | the process ID of the Excel holding the object: the number Windows gives each running program, shown in the PID column of Task Manager and by `Get-Process EXCEL` in PowerShell, written whole in decimal, nothing cut, hashed or padded, `30512`. Python runs inside Excel's own process, so the seam reads its own process ID once, when it starts, and every handle that Excel publishes carries it, whichever workbook the creator is in |
| `kind` | the kind's tag, its class name in lowercase words joined by underscores: `valuation_date`, `market_history`; Python types and worksheet functions keep their PascalCase names |
| `index-name` | the name the index was created with, `_CreateIndex`'s first argument, read off the stored object when it is published and written whole as typed: case, spaces, punctuation, colons and any character kept, nothing trimmed, re-cased or shortened; a batch's currency stands there for the cashflows and a curve's own name for a discount curve; present for the kinds the table below names, absent for the rest |
| `count` | the runtime's publication count, a plain number with no padding: 1 for the first object published after Python starts, then 2, shared by every kind and every workbook open in that Excel, never reset and never repeated while Python runs |

| Object | Shows | The name read from |
|---|---|---|
| index | `30512:index:WTI:31` | its own `name` |
| calendar | `30512:calendar:WTI:32` | `index.name` |
| futures fixings | `30512:futures_fixings:WTI:33` | `index.name` |
| IFERC fixings | `30512:iferc_fixings:HNG:41` | `index.name` |
| Gas Daily fixings | `30512:gas_daily_fixings:HNG:45` | `index.name` |
| market history | `30512:market_history:WTI:34` | `calendar.index.name` |
| price vector | `30512:price_vector:WTI:35` | `index_name`, the text typed to `_CreatePriceVector` since #112 |
| market | `30512:market:WTI:36` | `market_history.calendar.index.name` |
| trades | `30512:trades:WTI:41` | `resolved.index.name`, the index the batch was resolved against, since #139 |
| prepared trades, trade results | `30512:prepared_trades:WTI:43`, `30512:trade_results:WTI:45` | the batch's index through the records, `encoded.terms.index.name` and `prepared.encoded.terms.index.name`, since #141 |
| cashflows, cashflow results | `30512:cashflows:USD:12`, `30512:cashflow_results:USD:13` | the batch's one currency, `currency`, where an index's name would be, since #200 |
| discount curve | `30512:discount_curve:SOFR:2` | its own `name`, `_CreateDiscountCurve`'s first argument, kept by `util_BumpDiscountCurve` on the curve it makes, [discount-curve.md](../library/globals/discount-curve.md) |
| valuation date, trade template, quote template, discount curve set | `30512:valuation_date:1`, `30512:trade_template:40`, `30512:quote_template:41`, `30512:discount_curve_set:4` | none: a template serves any compatible index and carries none, and a collection's members are its readback's to show |
| the three schedules, the holiday calendar, the conventions, the contract specifications | `30512:futures_schedule:12`, `30512:holiday_calendar:13`, `30512:index_conventions:14`, `30512:contract_specifications:15` | none: an index uses them, which names them nothing, and their creators gain no argument |

Every sample on this page and on the library's pages uses one process ID, `30512`; a real Excel shows its own, and two Excels open at once show two.

A name is written as it was typed, so `30512:market_history:Henry Hub NYMEX:34` keeps its space, the workbook's `30512:market_history:Sample futures index, closed 25 May:212` its comma, `30512:index:Henry Hub: Gas Daily:50` its colon, four in that text, and `30512:index:Brent Dated €/bbl:51` its characters. Two indices of one name are `30512:index:WTI:7` and `30512:index:WTI:9`, told apart by the count alone. A price vector shows the name it was typed with, so `30512:price_vector:wti nymex:37` beside `30512:market_history:WTI NYMEX:34` shows the mismatch the [market](../library/market/market.md) will refuse, before it does.

The count is a publication count, not a version, an array index, a per-kind sequence or a count of live objects. A new publication takes the next number; a failed creator moves it not at all; reading a handle publishes nothing and moves nothing; removing entries never recycles numbers; closing a workbook, or every workbook, does not reset the count of a runtime that stays open, and does not change its process ID. The full, exact text is the lookup key: a consumer neither looks up a part alone nor normalizes a supplied handle, nothing in the seam or the library splits the text, and the stored, verified kind establishes the object's type; the visible process ID, tag and name describe the object and prove nothing. An edited name, an edited count, a number not yet published, another Excel's process ID or a text with none fails as text naming no live object, `market_history is text '30512:market_history:Brent:34' naming no live object, expected market history handle`, and a live handle of another kind fails by its stored kind, `market_history is price vector handle '30512:price_vector:WTI:35', expected market history handle`. The readable label dropped on 2026-09-13, when nothing supplied one, returns as the index's name, which #107 and #112 supply. The short forms `curve:17` and `curve:18` below shorten the text to explain ownership; a real text reads `30512:discount_curve:SOFR:17`.

The seam reads its process ID once, when it starts, and formats the text once, at publication, in the one publication path. Registration reads the declared result kind and prepares, once, the path to that kind's name, `index.name` for a calendar, `market_history.calendar.index.name` for a market, none for a schedule, so publishing reads two or three attributes and builds one string, with no scan, no hash of contents and no search of the store; the library's records hold their data and learn nothing of handles, and the host learns nothing of the process ID, which it never reads and never checks. Before the entry is stored, the whole text is measured as Excel counts text, in UTF-16 units, against the 32,767 the text-out rule already holds ([outputs.md](outputs.md)); a longer text fails in the result voice, `returned handle of 32796 characters, expected at most 32767`, nothing truncated, nothing stored and the count unmoved. Only a name of some 32,730 characters reaches it.

The count starts again when Python starts, and the process ID changes with it. Two workbooks open in one Excel share the process ID, the store and the count: a creator call in either with the same function and argument values as a live call in the other shares that call's publication and shows its text, and a creator call with any other argument values publishes an object of its own, as [Shared objects and shared dependencies](#shared-objects-and-shared-dependencies) says. A second Excel started as its own program is a second process with a process ID, a Python and a store of its own, so the same sheet open in both shows the same kinds, names and counts under two IDs, `30512:price_vector:WTI:35` and `41188:price_vector:WTI:35`, and a text of one handed to the other fails as text naming no live object, never as the other's object. Before #116 the two showed `price_vector:WTI:35` alike, and reading the first Excel's handle in the second returned the second's vector. A text a workbook saved names nothing in a later Excel unless Windows gave that Excel the same process ID, which it may once the earlier one has exited, and the new runtime publishes the same kind, name and count: the known limitation below. Whether the add-in requests a calculation when a workbook opens is deferred beyond #114, the supported way being the user's full calculation, as [A missing object is a failure](#a-missing-object-is-a-failure-not-a-cache-miss) says.

### Known limitation: a reused process ID after a restart

Recorded during the review of #113 on 26 September 2026, when the text carried no process ID and any later Excel could repeat it, and narrowed by this ticket to one condition more. Windows may give a new process the ID of one that has exited, so a saved text can still equal a later Excel's publication when three things coincide: Windows gave that Excel the earlier one's process ID, its runtime published the same kind, name where present, and count, and a consumer calculated before the saved creator ran again, which manual calculation permits. Two Excels running at once never share a process ID, so the collision the ticket reproduced between two instances is closed, and within one runtime the count never repeats.

The reproduction of 26 September, on that day's text, opened that revision's `workbooks/handles.xlsx` read-only in a fresh Excel with manual calculation selected, left `handles!B677` uncalculated with its saved `price_vector:Sample futures index:6` and its first source price `74.25`, published a second vector over `999` on a temporary sheet until it took the same text, and read `=INDEX(util_ReadHandle(handles!B677),3,1)` there: `999`, the new vector's price, from a formula referring to the original creator. Today the same steps need the fresh Excel to have received the process ID the saving Excel had, and were not repeated. No handle was pasted or typed as a value; the case is possible, not frequent, and one history per index does not prevent it.

When diagnosing a wrong or a missing object after a restart, read the handle's first part against the running Excel's process ID, `Get-Process EXCEL` in PowerShell: a text carrying another ID, or none, names nothing here and the cell says so. When the IDs match, check calculation mode, whether the referenced creator has run in this runtime and whether another publication has taken its saved text, and recalculate the creators and their consumers before relying on their results. The owner accepts the compromise, stated in the ticket: the whole process ID identifies the process for an engineer and closes the demonstrated collision between concurrent Excels; no token, hash or padding goes beside it, nothing checks the ID on the way in, the whole text staying the key, and whether the add-in requests a calculation on opening stays with release.

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
| the process ID leads every text of every kind, read once and equal to the process's own; two publications share it; the count after it runs on as before | example, through the seam |
| a live text under another process's ID, and a text with no ID, name nothing, in the words above; a failed creator and a read still move no count | example, through the seam |
| a name long enough to take the text past 32,767 units fails with the process ID counted in the total | example, through the seam |
| every creator's ledger unchanged; every ceiling unchanged, the text longer by the process ID and a colon | work and allocation budget |
| every handle a hidden Excel shows begins with that Excel's process ID, read from its window, and the count after the name is a number | Excel smoke, the lifetime script's `core` group, and the host replay under its own process ID |
| two Excels at once: the same chain in each shows the same kinds, names and counts under two IDs; a handle of one read in the other fails as text naming no live object; every workbook closed in one leaves its count and its ID as they were; a workbook saved by one and fully calculated in the other shows the other's ID on every handle | the lifetime script's `processes` group |

#113 rewrote the text where it was written: [bridge.md](bridge.md#a-handle-one-store-and-the-text), [outputs.md](outputs.md) decisions 8 and 11 and [inputs.md](inputs.md) decision 35's sample, the handle row of [conventions.md](../library/conventions.md), [history.md](history.md), the sample handle on every library page, fifteen patterns and four count-reading helpers in the tests, and `test_handles.py`'s three-part reader. The smoke's rows read a handle's start with `LEFT` and stood so until #116, below; the workbook's handle cells are formulas and rewrite themselves on a full calculation, its notes' sample texts refreshed by hand. No alias for the old text: a saved workbook shows the new text after its first calculation.

#116 put the process ID first where the text is written: [bridge.md](bridge.md#a-handle-one-store-and-the-text), [outputs.md](outputs.md) decisions 8 and 11 and [inputs.md](inputs.md) decision 35's samples, the handle row of [conventions.md](../library/conventions.md), [history.md](history.md), the sample handle on every library page under one process ID, `30512`, the patterns and count-reading helpers in the tests, which expect this process's own ID first, and the prefixes of the host's replay, the smoke and the lifetime script, which read the hidden Excel's from its window. The smoke's rows read the part after the first colon, and four read the part before it against the process ID; the lifetime script gains its `processes` group. The workbook's handle cells rewrite themselves on a full calculation under the saving Excel's ID. No alias for the old text: a saved workbook shows the new text after its first calculation, and its old texts name nothing until then.

### Not here

Enforcing one index per name: separate work, when the owner wants it; the label helps the eye and checks nothing. Release when a creator is deleted or its workbook closes, and reuse on an unchanged recalculation: built in #114, in [Publication and release](#publication-and-release), and changing nothing in the text. Persisting the store and reconnecting saved text: none. Saved text carries no persistence or reconnection guarantee; [the known limitation](#known-limitation-a-reused-process-id-after-a-restart) says when it can still resolve to another publication, and [A missing object is a failure](#a-missing-object-is-a-failure-not-a-cache-miss) says to recalculate after opening. A calculation requested on open: deferred beyond #114, under [Open](#open). No label for the schedules, the holiday calendar, the conventions or the specifications, and no argument added to any creator. No change to `Handle[object]`, to `util_ReadHandle` or to any spill. No token, hash or padding beside the process ID, no check of it on the way in, and no change to the count, the store, `GoosedoveHandles` or `Ping`; a process ID that Windows reuses is accepted, above.

## Shared objects and shared dependencies

Since #114, two creator formulas with the same function and the same argument values share one immutable object and one handle while both are live, in one workbook or in two; before it, separate cells published separate objects even with equal inputs, built and pinned since #53. The reason is the mechanism: Excel-DNA tracks a live call by its function and its argument values, and one object per cell would need the cell's address in the key, which golden rule 10 forbids. Sharing is accepted as the mechanism's, and it changes three things a sheet can see. The count does not move for the second cell. Changing one cell's inputs gives that cell its own new object and leaves the other's as it was. Two identical `_CreateIndex` cells are one index, so a calendar over one and fixings over the other pass the identity check of #109, which stays as it is: sharing is by the call's arguments, never by an index's name, and one index per name is still separate work. A handle argument is its full text, so two consumers of one creator cell share as its dependents always did.

The sharing is the host's and never the bridge's: the seam's prepared path publishes an object on every run, as the tests that call it directly show, and the host runs it only when Excel-DNA finds no live call with that function and those argument values, handing back the live call's value otherwise. So a library page says what a worksheet sees, one publication for equal live calls, and a test through the prepared path sees a new publication per call. The lifetime script proves the sharing through the production registration: a duplicate price vector in its `core` group, a market's call typed in another cell in its `edits` group, and five equal creators across two workbooks in its `books` group; every creator shares by the same key.

What sharing never does is remove a trade. Separate trade rows within one batch remain separate objects: two identical trade rows are two trades, contributing twice to any aggregate, and this page changes what is retained, not what is counted. Objects may hold references to the same dependency: two independent trades may use one valuation date or curve without copying it.

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

A live creator call owns its currently published object or batch. Equal live creator calls, the same function with the same argument values in any cells of any open workbook, own their one publication together: it stays while any of them is live, and the seam releases it when Excel disconnects the last. A lookup, or another cell displaying its value, is not a separate ownership record. A running calculation keeps the references it needs for its call. A retained object that depends on another holds its own strong Python reference, which can keep the underlying object alive after the original creator moves on. Spill cells belong to their creator's output. Cell addresses locate formulas: they must not become object identities, cache keys or permanent producer slots, and a moved formula follows Excel's rules without colliding with whatever previously occupied the destination or being treated as an unauthorized second producer: an address locates a formula and is never an object's identity ([golden rule 10](../golden-rules.md)).

## A missing object is a failure, not a cache miss

Cleanup must not delete an object a live creator owns or a retained dependency needs; no age or capacity limit evicts the object behind a valid handle to admit another, and if a capacity policy is ever introduced, failed new construction leaves existing owned objects valid. Excel sees the value in the creator cell, not the store: removing the object behind `curve:17` neither changes that cell nor asks Excel to rebuild the curve, so a missing object where this contract promises one is a runtime failure, reported, never substituted, never answered from a previous result. Collecting objects proven unused is a different thing from evicting live ones, and an optional cache of calculated results may discard an answer that can be recomputed from available inputs but never the input objects: construction reuse, calculation reuse and object lifetime are three separate responsibilities.

Saving a workbook preserves formulas, names, inputs and possibly the displayed handle text; it does not persist the store. Creator execution after reopening builds fresh objects. Until a creator runs, its saved text names nothing, since a later Excel has a process ID of its own, or resolves to a different publication in the one case [the known limitation](#known-limitation-a-reused-process-id-after-a-restart) describes. When that calculation runs, including in manual mode, is the user's: the supported way to open a workbook is a full calculation, repeated as feeds become ready, and whether the add-in requests one on opening is deferred beyond #114.

## Publication and release

Every row below is built, the reuse in the second, the sharing in the third and the release in the rest since #114, through Excel's live-data subscription: a creator's cell subscribes to its call, the subscription lives while a creator call with those arguments is live anywhere, and when Excel disconnects the last one, after a delay of its own, the seam releases that one publication.

| Worksheet action | Creator cell | Consumer |
|---|---|---|
| supply a valid table | displays `curve:17` | a reference supplies `curve:17`; the seam resolves it |
| recalculate, inputs unchanged | reuses the live object and handle, with no new count | resolves the same object without reconstruction |
| a second cell with the same inputs, in this workbook or another | shows `curve:17` too, the object shared while both are live | resolves the same object |
| change a factor to another valid value | publishes a new immutable curve, displays `curve:18`; the entry for `curve:17` goes when Excel disconnects its last subscriber | Excel propagates; the same formula now receives `curve:18` |
| supply invalid data | shows the construction error, publishes no replacement; its previous subscription goes when Excel disconnects it | receives the failure through the seam's error path |
| delete the creator, replace it with another formula or a value, remove its sheet, or leave it in an IF branch not taken | releases its ownership when Excel disconnects it; other creators stay valid | |
| close its workbook | releases that workbook's ownership when Excel disconnects it; a publication another open workbook still shares stays valid | |
| quit Excel | the process ends and its memory with it; Excel may end the subscription server without a disconnect for every topic, and nothing depends on one | |

What a cell shows does not change: the same text, handed to Excel inside the subscription before the creator's first call returns, so a new publication never shows `#N/A` while Excel waits for its next live-data update; handed over after the return, the research measured `#N/A` on every changed input's first result. The old object is never mutated or retargeted; there is no retained version history, and the numbers in this table are not a history we keep. Failed construction or publication must not present the previous handle as a successful answer for new inputs and must leave no abandoned temporary ownership; built: a creator that fails publishes nothing and moves no count. Dropping a store entry and freeing its object are different events: the entry owns one reference, releasing it releases that reference and nothing else, and another retained object may still hold its own, so an old market still reads its original vector after both old entries are gone while the old text names nothing. For a fixed workbook with no retained old dependencies, repeated replacements settle back to the live model; temporary overlap while Excel delivers its callbacks is expected, and a thousand updates that peaked at 293 entries in the research settled to three, so a settled count is the test and a peak is not accumulation. Unchanged failing inputs publish nothing and grow nothing. In manual calculation mode, editing inputs promises no immediate propagation; when the user requests calculation, creator and dependents update in Excel's dependency order, and the runtime never invalidates a still-retained object merely because no lookup happened recently.

### Known limitation: a creator moved in manual calculation mode

Recorded from the live tests of 26 September 2026 on Excel 16.0.20326.20158, in [excel-dna-handles.md](excel-dna-handles.md#the-live-tests-of-26-september-2026), and accepted with its remedy. In manual calculation mode, cutting a creator formula to another cell can make Excel disconnect its subscription, and others on the same sheet, about half a second later, while the cells still show the old text and the old dependent numbers; the seam releases those publications as told, and the next formula to read one of those texts fails as text naming no live object. The same happened with Excel-DNA's own handles and no Python, so it is Excel's behaviour, not the seam's. A full calculation, Ctrl+Alt+F9, rebuilds every live object, an ordinary F9 did too in every tested case, and further updates then propagate. The guidance: after moving creator formulas in manual calculation mode, run a full calculation before relying on dependent results, since Excel may still show old handles or cached numbers until it recalculates. The error text stays as it is, since an unknown text is also what a typo produces; no publication is kept past its disconnect, no timer and no cell tracking work around it, and neither the user's calculation mode nor Excel's live-data throttle is changed. Automatic calculation was not affected in the tested build.

## Errors are text

The seam returns failures as text beginning `#ERROR `, not as Excel error values. A failed creator's cell holds that text, and a consumer referring to it receives the text as its handle argument. The resolver recognises the prefix and fails as *the creator failed*, carrying the creator's own text whole at the end, `curve is the creator's failure, expected discount curve handle: #ERROR _CreateDiscountCurve: ...`, not as an unknown handle, which would send the user looking for a store problem that does not exist. A consumer of that consumer relays the same text: the creator's failure is taken out of the relay and carried on unchanged, never quoted again, so a chain of any length shows one message. Built.

## The seam's part

Built, in [bridge.md](bridge.md#a-handle-one-store-and-the-text): the declared result rule that keeps a verified object and returns its text, the argument rule that resolves text to the expected kind so a function receives the object and never the text, and the one store, a dictionary in the bridge from text to the verified kind and a strong Python reference. Registration selects the two rules from the declaration once, one mechanism for every kind, so adding a kind adds no store and no code of its own; the verified kind comes from the declaration, not from the handle's prefix; and errors beginning `#ERROR ` stay failures and are never published.

Built in #114, the release and the reuse, on Excel-DNA's `ExcelAsyncUtil.Observe`, the way the research proved out ([excel-dna-handles.md](excel-dna-handles.md)), and on three small additions of our own:

- The seam says which functions create a handle. `function_specs` carries one more flag per function, read off the declared `Handle[Kind]` result at registration, and the host builds an observed delegate for those and the plain delegate for every other function: no list of names, no parsing of returned text, no special path for any one kind.
- A creator's prepared path hands back the cell's value and whether it owns a publication, together, in one result: the handle and yes on success, the failure text and no otherwise. The host never asks the store a second time, never splits the text and never takes a string for a handle because it looks like one. Consumers keep their path as it is.
- The seam gains one operation, the release of exactly one publication by its text: the entry goes and its reference with it, nothing else is touched, and releasing a text already gone does nothing. It runs under the interpreter lock and only while the interpreter is alive.

The host gains one small class, a publication with `Subscribe` and `Dispose`. Excel-DNA calls the factory for it when no live call with that function and those argument values exists, and hands the live one's value back otherwise, so a reuse hit runs nothing in Python and moves no count. `Subscribe` runs the prepared call once, hands the value to Excel before it returns and keeps the ownership flag; `Dispose` releases the one publication it owns, once, however many times Excel calls it, and reports a failure rather than swallowing it. An Excel error among the arguments is the value, found as the plain path finds it, in argument order and cell order, and owns nothing. The class is plain enough for the host's tests to drive with a fake observer, and the one line that calls `Observe` is the only line Excel alone can exercise. Not built: Excel-DNA's own `[ExcelHandle]` store, which would keep a second store and a second text, and the cell tracking of shipped add-ins, which golden rule 10 forbids.

The host's counter gains three counts, publications, reuses and releases, beside the trips it counts today; Excel-DNA's hashing of the argument arrays to find the live call is the dependency's work, reported as read from its source and not measured by a second pass of our own. The Python ledgers are unchanged: a creator's prepared path does what it did, plus the flag it returns.

## Acceptance scenarios

Held by tests today: a direct reference supplies the current handle and resolves the typed object (the smoke rows); duplicate calls through the seam's prepared path give distinct handles and distinct objects, since the seam publishes on every run and the sharing is the observed worksheet call's, which the lifetime groups below hold; text naming no live entry and a handle of another kind fail, named; a creator's failure is relayed as the creator's; a failed creator publishes nothing. These tests do not establish that saved text cannot resolve to a different publication after a restart in which Windows reused the process ID; the known limitation above records that. Deterministic counts for construction, transport, copies, lookup, publication, reuse and release; retained bytes with shared ownership counted once; timing as evidence, never a gate.

The checks of #114 run in three homes. Routine, in `check.ps1`, `tools/excel_lifetime.ps1 -Groups core,processes,trades,valuation` beside the smoke: the seam's tests for the creator flag, the combined result and the release; the host's tests driving the publication class with a fake observer, first delivery inside the subscription, ownership on success and none on failure, disposal twice, a failure during setup or delivery, the interpreter gone; and one compact live group in a hidden Excel beside the smoke, first delivery and unchanged reuse, a changed vector reaching its market, duplicate creators sharing until the last goes, one invalid input and its recovery, and the last workbook closing back to the baseline while Python runs; since #116 the `processes` group beside it, two hidden Excels at once, every handle under its own Excel's process ID, a handle of one refused in the other, and a workbook saved by one recreated under the other's ID; since #139 the `trades` group, the trade chain's creators living and dying with their inputs, and since #155 the `valuation` group, the valuation path through a tick that retains an old result readable and unchanged, the day moved onto an expiry and past it, a vector left in place across the roll refused with the reports showing the failure and no number, the vector trimmed and the chain rebuilt, and the last workbook closed. Before merging, and whenever ownership or registration changes: the complete lifetime groups of the same script, `tools/excel_lifetime.ps1` with no group named, one fresh Excel per group, `edits` for structural edits and manual mode, `books` for two workbooks, closure and reopening, and `quit` for Excel quitting with live publications, apart from the groups that need it alive. A hidden Excel driven from outside does not exit while a workbook is left open at Quit, with or without a handle in it, so the tools close first and the quit group closes the chain's workbook as quitting would, checks that every disconnect reached the seam, and then takes the terminal path to the process's exit; a release once the add-in is closing is skipped and counted, pinned by the host's tests, and reaches no interpreter. Evidence for the pull request, not a gate in `check.ps1`: `tools/performance/handle_retention.ps1`, a thousand changed updates of a 150-price vector through the market under it, store entries and live price bytes at settled checkpoints and the baseline recovered at the last close. Since #117 the run gives a verdict of its own and exits nonzero, after its cleanup, when Excel has not reported its calculation done within the patience after an update, whatever the cell then holds, or when the market's first quote, read once as a number after that, is not the expected number, a later read within the patience telling the failure whether the number arrived late or never and changing nothing, when a checkpoint has not settled at the baseline within the patience, when the store is not empty after the close, or when any release missed or failed; each failure names the update or the checkpoint, what was expected and what was found. What the cell's text showed and how long the run took are reported beside and decide nothing, and `-Fault` proves the verdict by expecting the wrong price and the wrong count.

| Scenario | What must hold |
|---|---|
| a consumer uses a direct cell reference, or a name referring to it | both supply the current handle and resolve the correct typed object |
| an unchanged creator recalculates | reuses the live object and handle; construction and the count do not move; the argument hashing is reported |
| a creator's first result, and an input changing once a second | the handle shows at once, never `#N/A` while Excel waits; changed prices reach the market while the updates continue, observed through production registration |
| a valid change of quotes | the vector and the market publish anew; history and calendar are shared unchanged; the abandoned publications go once Excel disconnects them |
| duplicate creator formulas with identical inputs, then one changes, then one is deleted | they share one object and handle; the changed one diverges; deleting one preserves the other; deleting the last releases the publication |
| identical `_CreateIndex` cells feeding a calendar and fixings through different cells | one index, and the identity check passes; genuinely different inputs stay distinct |
| a retained old market | reads its original vector through its own reference after both old entries are gone; dropping its last owner releases the old prices |
| invalid inputs and recovery | every existing text, blank, boolean, Excel-error, wrong-kind, count and name refusal shows as today; no publication for the failure and no old success shown in its place; valid inputs recover the chain |
| deletion and replacement | clearing a creator, replacing it with another formula or a value, and removing its sheet release the abandoned publications after Excel's callbacks |
| nested and conditional creators | active calls work; an IF branch not taken and a removed nested creator release what they no longer use |
| manual calculation without a move | owned objects stay valid while waiting; a requested calculation propagates the current inputs |
| automatic calculation and structural edits | current values after cut, move, copy and row insertion, after Excel's callbacks; no cell address owns an object |
| a creator moved in manual calculation mode | the known limitation: after Excel's callbacks the old texts name nothing; a full calculation restores the chain and later updates propagate; a build that keeps the subscriptions instead is recorded, not failed |
| two workbooks, WTI and NG | different globals and markets stay independent; identical globals may share; closing either leaves the other whole; closing both returns to the baseline with Python running; the count never resets |
| close and reopen | the supported workflow, a full calculation and another once the feed is ready, resolves current handles and values; saved text is neither required to reconnect nor required to be refused |
| disposal, a failure during setup, quitting Excel | at most one release per publication and exactly one on normal disposal; no orphan entry after a failed setup or delivery; no unreported disposal failure; quitting is safe with or without a disconnect for every topic and never calls a finalized interpreter |
| a pasted literal, a text from an earlier runtime, a diagnostic display | none acquires ownership by appearing as text; unknown, expired and wrong-kind values fail |
| two Excels running at once | each publishes under its own process ID; equal kinds, names and counts never make one text; a handle from the other Excel fails as text naming no live object, never as a local object |
| workbooks in one Excel | share the process ID and the count; identical creators share their publication as before; closing every workbook leaves both as they were |
| a saved workbook opened in another Excel and fully calculated | its handles are recreated under that Excel's process ID; the saved texts name nothing there |
| a stale text, or one with no process ID, evaluated | fails through the existing lookup error, text naming no live object |
| a future batch holds two identical trade rows | both stay distinct objects; the creator owns the batch; spill and error rules are agreed before they are tested |
| undo and interrupted calculation | promises agreed first, then exercised in Excel |

## The first proof

1. `_CreateValuationDate`: create, retain, return a handle, resolve in a consumer. Done in #53, with a failed creator publishing nothing; its two identical creators gave distinct objects then and share since #114.
2. Worksheet lifetime and memory: replacement, deletion, moves, closing one of several books, fresh reopen, manual calculation, failures, retained dependencies; repeated edits accumulate no unowned objects; store entries and retained objects counted, shared data once; process memory alone is not an object-lifetime measurement. Built in #114, the scenarios above.
3. `_CreateDiscountCurve`: the same path with numpy arrays, done in #53 for construction, with the curve's two arrays copied and frozen; shared and released since #114 as every creator's publication is, step 2.
4. Batch returns: duplicate-row separation, row-to-handle pairing, replacement and release of the owned batch, resizing and failure cleanup, after the return and error rules are agreed. Open.

Concurrent calls must not multiply ownership, and no publication scans the store.

## Open

Batches of one handle per row: the spill's declaration, row errors, blocked spill, resizing and partial reuse of unchanged rows. Whether the add-in requests a full calculation when a workbook opens, deferred beyond #114, the supported way being the user's full calculation. Enforcing one index per name, separate work. Undo, interrupted calculation and unexpected loss, promises agreed first.
