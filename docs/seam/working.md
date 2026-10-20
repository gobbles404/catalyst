# Working on the seam

The how-to page. The seam is the one place Excel and Python talk: when a cell holds `=Add(A1, B1)`, the seam carries the two cells into Python, checks that both are numbers, runs the function, and carries the answer back. It has two sides: the host is the C# add-in Excel loads, and the bridge is the Python side, one module. This page is what to do, in steps, for the things a person comes back needing to do. What may cross is [inputs.md](inputs.md) and [outputs.md](outputs.md); how each side works is [host.md](host.md) and [bridge.md](bridge.md); how it is measured is [measuring.md](measuring.md); the numbers are [baseline.md](baseline.md); why it is as it is, and what is still open, is [history.md](history.md); the index to all of them, and the words they share, is [README.md](README.md).

Every command below is typed in PowerShell at the top of the repository.

## 1. When a cell looks wrong

Start from what the cell shows. The first column is the text, the second who put it there, the third what to do.

| The cell shows | Who said it | What to do |
|---|---|---|
| `#NAME?` | Excel, which does not know that name | Four causes. First, look at the inputs: an input cell holding `#NAME?` is passed through unchanged, like any Excel error (the row below), and nothing is wrong with the formula. Then type `=GoosedoveStatus()`: if that shows `#NAME?` too, the add-in is not loaded, so load it (section 8). If it answers with an error instead of `ok`, Python did not start, so nothing was registered and no Python function exists yet; the error text says why, usually `goosedove.cfg` naming a Python that is not there. If `=GoosedoveStatus()` says `ok`, the name is misspelt: a probe, a hidden worksheet function that does no work beyond crossing the seam, is absent from Excel's function wizard, so there is no list to pick from, and the spelling to match is the function's own name in its module under `src/goosedove/excel/`. `=RegisterAll()` shows `#NAME?` on purpose, and the smoke test checks that it does. |
| An Excel error: `#N/A`, `#DIV/0!`, `#REF!`, `#NAME?`, `#NUM!`, `#NULL!`, `#GETTING_DATA` | Excel, passed through by the host unchanged | One of the inputs holds that error. The host returns the first one it meets, arguments left to right and, inside a range, in sheet order; a range is an argument that arrives as a rectangle of cells, such as `A1:A8`. The function is never called. A trip is one crossing from the host into Python and back, and the only trip such a call makes is for a range the host reached before the error and had already handed over. Nothing is wrong with the seam: find the input cell and fix it. |
| `#VALUE!`, with no error anywhere in the inputs | Excel, in place of a value it will not hand over | Excel sends `#VALUE!` for a rich data type, an in-cell image, a LAMBDA value, a multi-area reference such as `(A1:B2,D1:D2)`, a 3-D reference, and for its own newer errors `#SPILL!` and `#CALC!`. Put plain cells in that argument. The full list of what Excel can send is in [inputs.md](inputs.md). |
| `#ERROR Forward: price is text 'Brent', expected number`, or `#ERROR Strip: values cell (3, 1) is blank, expected number` | the bridge, rejecting an argument | Read it literally: the function, the argument, what arrived, what was declared. Reject means a call-time failure. Inside a range the cell is counted the way `INDEX` counts, row then column from 1 within the range that was passed, because no sheet address ever crosses. The words are [inputs.md](inputs.md)'s, and so is the rule behind each: a boolean is not a number, text is never a number, empty text is not text, and a blank cell is not a missing argument. |
| `#ERROR Forward: returned text 'x', expected number`, or `#ERROR Prices: result cell (3, 1) is not a finite number` | the bridge, rejecting the result | The function returned something its declared return type does not allow. This is a fault in the function or in its declaration, not in the sheet. [outputs.md](outputs.md) has the rules and the full list of what fails. |
| `#ERROR Fail: ValueError: as asked` | the function itself | The function raised, and the cell carries its type and its message. The message is the library's; act on it there. |
| `#ERROR host: ...` | the host | Rare, and worth reporting whole: an exception escaping the trip, a cell holding a type the scan does not know, a result whose memory the host could not read as an array of numbers, or a text holding NUL (U+0000) in an argument, [inputs.md](inputs.md#nul-in-input-text). [host.md](host.md) names each. `#ERROR python did not start: ...` is the host too; no formula can reach it today, because when Python does not start nothing is registered and the cell shows `#NAME?`. |

Two functions to type first, in this order.

```
=GoosedoveStatus()
```

Shows `ok: python started and functions registered`, or the start-up error. It is written in C# and registered whatever happens, so it answers even when Python never started.

```
=Ping()
```

Shows `goosedove 0.1.0 from C:\...\src\goosedove\__init__.py`, with `source checkout` in place of the version when the package is not installed. It answers the question after a rebuild: which copy of the code is this Excel running.

## 2. Adding a worksheet function

The library's functions are one module per group under `src/goosedove/excel/`: `globals.py`, two creators that return handles; `index_definitions.py`, seven creators, one of three columns whose third may be left out, one of a single column of dates, one of five text scalars, one of a header row and a table of contracts, two of a column of codes and two columns of dates, and one of text and four handles, the last of which may be left out; `market_data.py`, four creators, one of a column of dates, a column of settles and the index's handle, one of a column of codes, a column of prices and the index's handle, one of a column of flow days, a column of prices and the index's handle, and one of the index's name and a single column of prices; `calendar.py`, one creator of a valuation date's handle and the index's; `market.py`, two creators of two handles each, one of the calendar's and its market's fixings', any of the three kinds, one of the history's and the price vector's; and `utilities.py`, a reader that takes any handle and spills a table. Beside them are `Ping` in `src/goosedove/excel/bridge.py` and the sixteen probes in `src/goosedove/excel/probes.py`, whose cost is the seam's cost and nothing more; those are the examples to copy. Before writing one, read [baseline.md](baseline.md)'s standing recommendation, which the numbers have now supported twice: declare pricing functions over arrays, one call for a column of trades, and never read a range once per row, which is the most expensive shape there is.

1. Put the module under `src/goosedove/excel/`, beside `bridge.py` and `probes.py`. It may import the pricing code; the pricing code never imports it. That one-way rule is why pricing can be tested without Excel.
2. Write a plain function with `@excel_function` above it. Annotate every parameter and the return with a declared type: the annotation that decides which one rule checks the value and which words its messages use, `float` for a number, `NumberColumn` for a column of numbers. It must be one of the fourteen the seam can receive, or a table schema, or `Handle[Kind]` around a class the library defines, and one of the eleven it can send, or a handle, listed in [inputs.md](inputs.md) and [outputs.md](outputs.md). A mixed range crosses in only as a table: a function Excel lists never declares `MixedArray` as a parameter on its own ([inputs.md](inputs.md) decision 38); as a result it is the rectangle of three kinds a function spills, built with `MixedArray.table` from rows of headings over columns of one kind each ([outputs.md](outputs.md) decision 13), or, for a column that holds a number on one row and a word on another, composed from the record's three fields, as the market history's and the market's tables in `utilities.py` do through one helper, or, for a small descriptive grid whose columns hold more than one kind, such as the shown instrument's schema, with `MixedArray.cells` cell by cell, since #137. The function's own name becomes the worksheet name, and its parameter names become the argument names Excel shows. Name it as the library's [conventions.md](../library/conventions.md#names) says, `_` then a verb, `_Scale`, or `util_` for a utility, and list it in the module's own `__all__`: the underscore is Excel's filter, and without that entry pyright reads it as Python's privacy and reports the function unused.
3. Write the docstring as the wizard text. The whole docstring, with the surrounding spaces removed, is the description Excel shows, so keep it to one sentence a user of the sheet would read. Beside each parameter, write the one line Excel shows about that argument, `x: Annotated[float, "One number to multiply."]`; the type checker reads the type and ignores the words. The shape of a line, what to select, an example, and at most one thing that must hold, is in the library's [conventions.md](../library/conventions.md#excel-help), with the optional form. A function Excel lists is refused without either, with more than the 253 characters Excel shows, or with a line that does not end with a period. Registration adds what the signature already says: an optional argument's name in brackets and what it takes when omitted, so write neither.
4. Give an optional argument a default in the signature. The default goes through the same accept rule as a real argument at registration, once, and is stored already converted, so only a missing argument takes it and a blank cell still fails. `None` is never an ordinary default, since every accept rule calls it blank; an argument that may be left out with nothing in its place is declared with its type written `X | None` and `None` as its default, `option_expiry: DateColumn | None = None`, and the function receives `None` only when the formula left the argument out, a blank cell in the slot still failing as a blank. Excel shows such an argument in brackets with its line alone, so again write neither. A table and a handle take no default at all and may not be left out; registration refuses both.
5. Import the module in the catalogue, `src/goosedove/excel/__init__.py`, and add its name to the `__all__` list beside the two that are there, or the lint step reports the import as unused. The catalogue is the list of modules whose functions Excel sees, and it is the only place a new module is named.
6. Pin its messages in a unit test under `tests/unit/`. Reach the function the way the tests do, `bridge.call("_Scale", [...])`, and assert the exact `#ERROR` text for one wrong argument and the value it hands back for a right one. A pin is a test that holds a fact still, so a change that moves it fails.
7. Add a row to `tools/excel_smoke.ps1`: the formula exactly as a person would type it, and the exact text the cell must display. Put any input cells the formula needs in the `$cells` list below it. The count it prints at the end follows the list of formulas.
8. Try it by hand with `.\tools\excel_dev.ps1`, which builds the add-in and opens it in a fresh Excel of its own, then run `.\check.ps1` (section 7).

The host needs no change. It asks the bridge for the list of functions at start-up and registers whatever is in it.

One function, whole:

```python
from goosedove.excel.bridge import NumberColumn, excel_function

__all__ = ["_Scale"]


@excel_function
def _Scale(values: NumberColumn, factor: float = 1.0) -> NumberColumn:
    """Every value times the factor."""
    return NumberColumn(values * factor)
```

`=_Scale(A1:A100, 2)` spills a hundred answers down. `=_Scale(A1:A100)` doubles nothing and returns the column unchanged, because the omitted factor takes its default; `=_Scale(A1:A100, B1)` with B1 empty fails, and says so.

A function that takes a table, a header row and a body, declares a schema beside it: a class deriving from `Table`, one line per column, the header name and its column type, and takes the header row as a `TextRow` in the parameter just before the table. Nothing else changes: the schema is read at registration as the signature is, the columns bind by name whatever their order, and the function receives one record with a typed attribute per column.

```python
from goosedove.excel.bridge import (
    BooleanColumn,
    DateColumn,
    NumberColumn,
    Table,
    TextColumn,
    TextRow,
    excel_function,
)

__all__ = ["_TotalQuantity"]


class Trades(Table):
    date: DateColumn
    product: TextColumn
    quantity: NumberColumn
    cleared: BooleanColumn


@excel_function
def _TotalQuantity(header_row: TextRow, trades: Trades) -> float:
    """Sum of quantity over a table of trades."""
    return float(trades.quantity.sum())
```

With `date`, `product`, `quantity` and `cleared` across A1:D1 and a trade per row below, `=_TotalQuantity(A1:D1, A2:D4)` sums the quantity column, and a sheet that puts `cleared` first still works. The rules and every message are in [inputs.md](inputs.md), the mechanism in [bridge.md](bridge.md), and `SumQuantity` in `probes.py` is the example to copy.

A function that creates an object the sheet reaches by handle declares `Handle[Kind]` as its result, the kind being a class the pricing library defines, and returns the object; the seam keeps it and the cell shows its handle, `30512:discount_curve:SOFR:2`. A function that takes such an object declares a parameter the same way and receives the object, never the text; one that takes the object behind any handle, whatever its kind, declares `Handle[object]`, which only a parameter may, since a creator names what it makes. The mechanism and every message are in [bridge.md](bridge.md#a-handle-one-store-and-the-text); `_CreateDiscountCurve` in `globals.py`, `_CreateFuturesFixings` in `market_data.py`, which takes the index's handle beside its date and settle columns, and `util_ReadHandle` in `utilities.py` are the examples to copy. Nothing more is written for a creator's lifecycle: registration reads the declared `Handle[Kind]` result, the host observes the call, equal live calls share one publication and Excel's disconnect of the last releases it, as [handles.md](handles.md#publication-and-release) says. A creator's ledger and ceiling go in the two performance files like any other function's, and its creator gets no row in the timing runners, which call the prepared path in a loop, where every run publishes and nothing is released, and would keep an object per call.

## 3. Adding a declared type

Registration refuses a function whose annotation is not one of the declared types, so the type comes first and the function second. [inputs.md](inputs.md) names one that is wanted and not built, `ContractMonth`, a whole serial falling on the first of a month; the steps below use a month type as the example.

1. Add the label in `src/goosedove/excel/bridge.py`, beside the others: `Month = NewType("Month", np.datetime64)`. `NewType` gives a name to a shape that already exists, so the seam can tell a month from a plain date though both are numpy days.
2. Write the accept rule beside the rules of its kind: one function that takes what arrived and returns the typed value, or raises `_Rejected`. For a scalar, one value such as the number in `B2`, build on `_number`, `_whole` and `_date`, which already reject in the right order. For a range, one look and no walk: a look is one pass over every cell at once, the way `=SUM` reads a range; a walk is visiting cells one at a time, which the seam avoids. `_first_bad` turns the look's first flag into the cell a message can name.
3. Add its row to `_DECLARED`: the label is the key, and the row holds two things, the plain name every message uses and the rule. Pick a name a user of the sheet would say, in the words of the sheet: `"month"` for `Month`, `"column of months"` for `MonthColumn`. A column type also gets a row in `_COLUMNS`, with the rule for one column of a table, so a schema may name it.
4. Add a rule to `_RESULTS` if a function may return the type. If it may not, a function declaring it as a result is refused at registration, which is what happens today for a column of text.
5. Teach `describe` the new words only if a new shape of value can now arrive or come back. It already names numbers, text, booleans, blanks, missing arguments, ranges, numpy days by their unit, and numpy arrays by their dimensions and kind; a month held as a numpy day needs nothing.
6. Add the type to its owners, section 10: a row in [inputs.md](inputs.md)'s table of declared types, what it accepts and refuses, and in [outputs.md](outputs.md)'s if it can be returned, striking it from inputs.md's table of what is wanted next; and a row in [bridge.md](bridge.md)'s table naming its rule and what the function receives, the mechanism and not a second copy of the contract. A question decided on the way gets its own named section in inputs.md, as the NUL rule has, dated where the date tells a reader something; no new number.
7. Pin the message texts in the three unit test files: the scalar words in `tests/unit/test_type_validation.py`, the range words and the property that the first bad cell is named in `tests/unit/test_range_validation.py`, the result words in `tests/unit/test_result_validation.py`. Each file registers its own small functions at the top; add one per new type and put your cases in the tables of exact texts.
8. Add a look-counting function to `tests/performance/conftest.py` when a probe would earn no place, which is whenever the host cannot tell the new range from one it already carries. `FirstOfNumbers`, `FirstOfDates` and `FirstOfNames` are there for exactly that reason: they are registered outside the package, so they are not themselves counted, and they exist only to count the Python side of each look. Then give it a ledger in `tests/performance/test_seam_budgets.py`, the exact list of which of the seam's functions ran and how many times, and a ceiling in `tests/performance/test_seam_allocation.py`, the most memory one warm call may hold at its peak, written as the measured figure plus the file's slack; warm means measured after a first call has set everything up.
9. A new cell kind needs the host as well. A cell's kind is which of five things a cell holds, number, text, boolean, blank or missing, and the codes are shared: the `Kind` list in `bridge.py` and the byte constants and summary bits in `host/Goosedove.Host/AddIn.cs` are two halves of one agreement. A sixth kind means the host's scan, its summary of kinds, `cells_from_buffers`, and the counts in `tests/performance/HostWorkBudgets.cs`. A month is not a new kind: it arrives as a number, like every date.

A form of declaration rather than a type, such as `X | None = None` for an argument that may be left out with nothing in its place, follows the same steps without a rule of its own: registration and what it refuses, a row and a named section in [inputs.md](inputs.md), the pins in the unit tests, and the paragraphs of [bridge.md](bridge.md) that describe declaring a function. Nothing crosses the host differently, so it needs no probe and no runner row.

## 4. Adding a probe

The record asks for two next, and until they exist no runner has a row for a text range or a date range, so the before-and-after tool is blind to those paths: a text probe and a date probe, with rows in all three runners. [history.md](history.md) lists both as open.

1. Write it in `src/goosedove/excel/probes.py` with `@probe`, which registers it hidden, so Excel's function wizard never lists it and it still ships in the build everyone loads. Begin the docstring with `Probe:` and name the one thing it proves. It must do no work beyond proving it, or its cost stops being the seam's cost.
2. Add a scenario to `tools/performance/measure_python.py`, in `scenarios()`, with its inputs built there, before any clock starts, and a check of the answer. Put it inside the size loop if it has a cells knob.
3. Add a row to `workloads()` in `tools/performance/profile_workload.py`, one representative call at a size a sheet might send, or `.\measure.ps1` writes no profile for the new probe and nothing says so.
4. Add a scenario to `tools/performance/Goosedove.Host.Measure/Scenarios.cs`: a delegate from `Registration.MakeDelegate(Bridge.Prepare("Name"), n)`, then one `measurements.Run` with the same shape as its neighbours, a check, and `Counted(...)` so the host's counters are recorded beside the timing; a counter is a named tally of one thing the host did during a call, such as the trips it made into Python or the cells it scanned.
5. Add a case to `tools/performance/measure_excel.ps1` if Excel should time it, with a native formula beside it as its floor, the way `=SUM` sits beside `SumArray`. A probe that only proves correctness needs no Excel case.
6. Add a row to `tools/excel_smoke.ps1`, so the probe is checked in a real Excel with the exact text it must show, and the same row to `host/Goosedove.Host.Tests/CallTests.cs`, which replays the smoke rows without Excel. Add the name to the set of hidden probes in `tests/unit/test_bridge.py`: that test asks only that the set contains them, so a missing name never fails, which is why it has to be done on purpose.
7. Give it a ledger in `tests/performance/test_seam_budgets.py`, both lists where numpy is asked anything, and a ceiling in `tests/performance/test_seam_allocation.py`.
8. Add a counts test to `tests/performance/HostWorkBudgets.cs`, which is compiled into the host's test project: what the host did for one warm call, as an exact table of counters.
9. Add it to the probe tables in [measuring.md](measuring.md), with its knob, and [bridge.md](bridge.md), with what it proves. The tables are the list; a page that states a count of probes drops the count when it is next touched, as [AGENTS.md](../../AGENTS.md) asks.

## 5. Changing the seam and measuring it

1. Start from the counter, ledger or ceiling the change means to move, and write it down before touching anything. [baseline.md](baseline.md) says where the work is now and which counters already stand at the floor the design allows. A change that moves none of them is not the change it claims to be.
2. Make the change.
3. Let the pins fail, and re-pin them in the same pull request. The ledgers are in `tests/performance/test_seam_budgets.py`, the ceilings in `tests/performance/test_seam_allocation.py`, the host's counts and its managed-byte ceilings in `tests/performance/HostWorkBudgets.cs`. Write the new measured figure into the comment beside a ceiling, with its date, as the range-in and text-column comments in `test_seam_allocation.py` and the two in `HostWorkBudgets.cs` do; `test_seam_allocation.py`'s docstring carries the session's date for the ceilings whose comments give only a figure.
4. Run the before-and-after tool with the machine otherwise idle and nothing else open:

   ```powershell
   .\tools\performance\before_after.ps1
   .\tools\performance\before_after.ps1 -Base <commit>
   .\tools\performance\before_after.ps1 -SkipExcel
   ```

   With no parameters the base is where this branch left `origin/main`; `-Base` names another; `-SkipExcel` runs the Python and host runners only. The base is checked out into a temporary worktree, a second copy of the code in Windows' temp folder under the name `goosedove-base-<the base's short revision>`, so this tree is never touched, and "after" is this tree as it stands, uncommitted changes included. The runners alternate sides so drift lands on both. The results land in `profiles\before` and `profiles\after`, and the report in `profiles\compare.md`: every timed row of every layer, every host counter that differs, and the allocation figures. Paste that report whole into the pull request. Read it as [measuring.md](measuring.md) says: a row counts as moved only when its two batch spreads do not overlap, and a move is real when it is large, consistent across sizes, and where the change aimed; a large move where it did not aim is the finding.
5. Move the pages that own what changed, section 10: [host.md](host.md) and the steps in [walk.md](walk.md) for the host, [bridge.md](bridge.md) for the bridge, [inputs.md](inputs.md) or [outputs.md](outputs.md) when a rule changed; and a row in [history.md](history.md) when the change declined something, settled a question or set a new baseline, not for a routine change.
6. Run `.\check.ps1` and fix what it reports (section 7).
7. Open the pull request with the template's six headings in order: What; Counts, with the counters before and after; Tenets; Conflicts; Checked in Excel; Not done. One purpose, and a title that names kind and scope first, `feat(seam):`, `feat(host):`, `chore(tools):` or `docs:`. The counts are the evidence. No timing gates a merge; the timings are the record that says whether the counts mattered.

The pins move with the source, in the same pull request, while a baseline document lands alone in its own. That is not the golden rule that behavior and its baseline never move together: the pins are the claim the change makes about itself, so they belong to it, while a baseline is the record of one session's numbers at a named revision, and a record that moves with the thing it records is no record.

## 6. Making a baseline

A baseline is one session's numbers at a named revision; a session is one sitting of the runners on one machine. This is what pull request #42 did, at the revision the last change merged at.

1. Check out the merged revision, with nothing uncommitted, and note it: the document is named after it.
2. Run the three runners in one sitting on an idle machine, then the control, a larger-size run kept to show how costs grow rather than to define the ordinary case:

   ```powershell
   .\measure.ps1
   dotnet run --project tools\performance\Goosedove.Host.Measure -c Release
   .\tools\performance\measure_excel.ps1
   .\tools\performance\measure_excel.ps1 -Rows 10000
   ```

   `.\measure.ps1` runs the profiler, the Python runner and the summary. Check the load by hand before each part. The control rebuilds the add-in and can fail before it times anything, because the Excel of the previous run has not yet let go of the `.xll`; wait, run it again, and say so in the document if the session was not one unbroken stretch, as [baseline.md](baseline.md) does today.
3. Copy these ten files out of `profiles\` into `docs\seam\baseline\`, with the host runner's three renamed and the rest keeping their names. The summary, the HTML profiles, and anything the before-and-after tool left behind stay in `profiles\`:

   | From `profiles\` | To `docs\seam\baseline\` |
   |---|---|
   | `host-measure\batches.csv` | `host-batches.csv` |
   | `host-measure\work.csv` | `host-work.csv` |
   | `host-measure\environment.json` | `host-environment.json` |
   | `python-timing.csv`, `python-allocation.csv`, `python-environment.json` | the same names |
   | `excel-timing.csv`, `excel-timing-environment.json` | the same names |
   | `excel-timing-rows10000.csv`, `excel-timing-rows10000-environment.json` | the same names |

4. Strip the byte-order mark from the Excel runner's environment files, an invisible marker Windows PowerShell puts at the start of a text file it writes. Both baselines so far have been stripped by hand; the one-line fix in the runner is still open.
5. Write the paired-rows file with `compare.py`, which sets every row of the previous session beside the same row of this one. It reads two directories laid out the way the runners write them, so the previous baseline's files have to be brought back from git history and the renames of step 3 undone. Take that commit into a worktree of its own rather than redirecting `git show` into a file, which would write the CSVs in an encoding `compare.py` cannot read:

   ```powershell
   git worktree add --detach <tmp> <the previous baseline's commit>
   ```

   Its baseline directory sits wherever it sat at that commit: `docs\baseline\` before the seam's pages moved into `docs\seam\`. Copy from it into a `profiles\previous\` of the shape the runners write: `host-batches.csv` to `host-measure\batches.csv`, `host-work.csv` to `host-measure\work.csv`, `host-environment.json` to `host-measure\environment.json`, and the Python and Excel files under their own names. Rename any row that has been renamed since, so it pairs with itself instead of appearing twice. Then:

   ```powershell
   uv run python tools\performance\compare.py profiles\previous profiles --before-label "the session at <previous>" --after-label "the session at <this>"
   git worktree remove --force <tmp>
   ```

   `compare.py` writes its report in the parent of the second directory it was given, so with `profiles` as the second side it lands at the top of the repository as `compare.md`. Move it to `docs\seam\baseline\since-<previous revision>.md`, named for the revision it reads since. Retitle it for the two revisions and put a paragraph at the top saying which files it read, that the two are separate sessions rather than one session's before and after, so a few percent either way is the noise between them, and which rows were paired under new names.
6. Rewrite `baseline.md` whole. Keep its sections: how to read a number, the session, the machine, what a call costs, a cell in, a cell out, the round trip and one answer per row, the same answers three ways, what the tests pin, what moved since the last baseline, and what it all says about the library's formulas. Every number is a row of this session's CSVs or arithmetic that names the rows it used. The previous document stays in git history at the commit the new one names.
7. Add a row to [history.md](history.md)'s timeline for the pull request, and bring its baselines section forward: that table carries one column per baseline, so the new revision joins it as a column, and the paragraphs above it say which sessions compare and why.
8. Open it as its own pull request, `docs: the baseline at <revision>`, with no source change beside it and "no code changed" under Counts.

## 7. Running the checks

`.\check.ps1` runs nine steps in this order and stops at the first failure:

1. `uv run ruff format .`
2. `uv run ruff check --fix .`
3. `uv run pyright`
4. `uv run pytest -n auto`
5. `dotnet test host\Goosedove.Host.Tests -c Release --nologo -v q`
6. `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_busy_selftest.ps1`
7. `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_session_selftest.ps1`
8. `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_smoke.ps1`
9. `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\excel_lifetime.ps1 -Groups core,processes,trades,valuation`

The sixth and seventh steps need no Excel. The sixth proves what the last two do when Excel refuses a call as busy, which a run of them may never meet; [host.md](host.md#when-a-hidden-excel-is-busy) is the page, and the last two end with one line saying which calls had to wait, `busy Excel: no call had to wait` on a calm run. The seventh proves that a hidden Excel whose start fails is still ended, its process waited for and stopped if it stays, with the failure that began it kept; [host.md](host.md#when-a-hidden-excel-quits) is the page.

The last two steps need Excel installed. The lifetime script's core group builds a chain of creators in a hidden Excel and checks that a creator's cell shows its handle at once, that an unchanged recalculation publishes nothing, that a changed price releases the old vector and market once Excel disconnects them, that equal creators share, that a failure owns nothing and that closing the workbook empties the store; its `processes` group runs two hidden Excels at once and checks that every handle carries its own Excel's process ID, that a handle from one Excel names nothing in the other, and that a workbook saved by one is recreated under the other's ID; run it with no group named before merging a change to ownership or registration, for its `edits`, `books` and `quit` groups too. The smoke it builds the add-in, opens a hidden Excel of its own, types the input cells, places one formula per row and compares each cell's displayed text with the text expected. It then closes the workbook, asks the add-in to prepare for quitting, and verifies that its Excel process exits, releasing the add-in file for the next build. A process that remains is stopped and the check fails. The process is identified from that Excel's window handle, never by selecting all Excel processes. Without Excel it stops and says so, and the check fails. It never touches an Excel you have open. The workbook reader and Excel timing runner use the same cleanup; [host.md](host.md#when-a-hidden-excel-quits) explains why it is needed.

CI runs everything but those two steps, on a Windows runner, in three jobs. One runs format, lint, types, the Python tests and the two self-tests, the busy Excel's and the session's, with `ruff format --check .` so CI never rewrites a file. One builds the host, runs the host's tests, and builds the host runner so that it keeps compiling. The third runs `.\measure.ps1` and uploads `profiles\`, and gates nothing.

Any part alone:

```powershell
uv run ruff format .                              # formatting
uv run ruff check --fix .                         # lint
uv run pyright                                    # types
uv run pytest -n auto                             # every Python test
uv run pytest tests\performance                   # the pins alone
dotnet test host\Goosedove.Host.Tests -c Release  # the host's tests, no Excel needed
.\tools\excel_busy_selftest.ps1                   # how the Excel tools wait for a busy Excel, no Excel needed
.\tools\excel_session_selftest.ps1                # a hidden Excel whose start fails is still ended, no Excel needed
.\tools\excel_smoke.ps1                           # the add-in in a hidden Excel
.\tools\excel_lifetime.ps1 -Groups core,processes,trades,valuation             # handles living and dying in a hidden Excel
.\tools\excel_lifetime.ps1                          # every lifetime group, before merging ownership changes
```

`uv run pytest -n auto` already runs the pins, and the documentation link check of section 11; the fifth line is for when the pins are what you are working on. The host's tests start Python themselves, finding the project's own with `uv run python`, so they need no config file and no Excel. Never add `# type: ignore` or `# noqa` to get a step green; fix the code. And after pulling:

```powershell
uv sync --locked
```

## 8. Loading the add-in in Excel by hand

`.\tools\excel_dev.ps1` does all of this for you and is the way to try formulas day to day, on a new workbook; `.\tools\excel_dev.ps1 workbooks\handles.xlsx` opens a saved one instead, fully recalculated so that every handle in it belongs to this session and not to the one that saved it. `workbooks/` holds the workbooks we keep, one per topic, the shared object for talking about a function on a real sheet: open it, try things, write a line in its `notes` column, save, commit. `.\tools\excel_show.ps1 workbooks\handles.xlsx` prints a workbook as its cells show, in a hidden Excel with the add-in loaded, one line per cell with its formula and its text, so two people read the same thing and a review can quote it. Do the steps below by hand when the add-in must live somewhere else, or run against a Python that is not the project's.

1. Build it. Either `dotnet build host\Goosedove.Host -c Release`, or dot-source `tools\host_build.ps1` and call `Build-HostAddIn -Root <the repository>`, which builds Release, writes the config beside the result, and returns the path.
2. Load `host\Goosedove.Host\bin\Release\net48\Goosedove.Host-AddIn64.xll`. 64-bit Excel only: the add-in loads Python's own DLL into Excel's process, and the project's Python is 64-bit, which `tests\test_smoke.py` checks. The `Goosedove.Host-AddIn.xll` beside it is the 32-bit build and cannot load that Python.
3. Put `goosedove.cfg` beside the `.xll`. Two keys, one per line:

   ```
   pythondll=C:\...\python313.dll
   pythonpath=C:\...\goosedove\src;C:\...\site-packages
   ```

   `pythondll` is the path of the file that is Python itself. `pythonpath` is the folders Python looks in, separated by semicolons: the repository's `src`, so `goosedove` is importable, and the folder holding the installed packages, so numpy is. The reader trims each line, skips blank lines and lines starting with `#`, and takes the last value when a key appears twice. Every other line needs an `=`, or start-up fails and `=GoosedoveStatus()` says so.
4. `tools\host_build.ps1` writes that file from the project's own Python. It asks the environment for three things and joins them:

   ```powershell
   uv run python -c "import sys, sysconfig; print(sys.base_prefix); print(sysconfig.get_paths()['purelib']); print(f'python{sys.version_info.major}{sys.version_info.minor}.dll')"
   ```

   The first line and the third, joined with a backslash, are `pythondll`; the repository's `src` and the second line, a semicolon between them, are `pythonpath`. The file is written as plain ASCII and git ignores it, so an add-in deployed anywhere else needs one of its own.
5. For a Python elsewhere, run that same command with that Python and write the two lines by hand. That Python needs the package's dependencies importable from the folders `pythonpath` names, and it must be 64-bit.
6. Tell Excel to load the file. File > Options > Add-ins, Manage: Excel Add-ins, Go, Browse, pick the `.xll`, OK: it loads now and every time Excel starts until you clear the tick. Double-clicking the `.xll` loads it for that one session instead.
7. Type `=GoosedoveStatus()`, then `=Ping()`, then `=Add(1,2)`. The first says whether Python started, the second which copy of the code is running, the third that a call crosses the seam and comes back. `Add` is a probe, so the function wizard will not offer it; type it in full.

## 9. Where to look

| What | Where |
|---|---|
| the bridge: the declared types, the accept and result rules, registration, the prepared path, `describe`, `Ping` | `src/goosedove/excel/bridge.py` |
| the probes | `src/goosedove/excel/probes.py` |
| the catalogue, the one place a new module of worksheet functions is named | `src/goosedove/excel/__init__.py` |
| the host: start-up, the config reader, registration, the scan, the way out, `GoosedoveStatus`, `HostAdd` | `host/Goosedove.Host/AddIn.cs`, with the counter in `WorkCounter.cs` |
| the host's own tests, which need no Excel | `host/Goosedove.Host.Tests/` |
| the check that the project's Python is the 64-bit one the host needs | `tests/test_smoke.py` |
| the exact messages, pinned | `tests/unit/test_type_validation.py`, `test_range_validation.py`, `test_result_validation.py`, `test_bridge.py` |
| the pins: the ledgers, the ceilings, the three test-only looks, the host's counts | `tests/performance/test_seam_budgets.py`, `test_seam_allocation.py`, `conftest.py`, `HostWorkBudgets.cs` |
| the profiler, the three runners, the summary, the before-and-after tool and its comparison | `tools/performance/measure_python.py`, `profile_workload.py`, `Goosedove.Host.Measure/`, `measure_excel.ps1`, `summarize.py`, `before_after.ps1`, `compare.py` |
| the smoke test in a hidden Excel, Excel by hand, the build and the config it writes | `tools/excel_smoke.ps1`, `tools/excel_dev.ps1`, `tools/host_build.ps1` |
| the whole check, and the Python-side measurement | `check.ps1`, `measure.ps1` |
| the pull request template | `.github/PULL_REQUEST_TEMPLATE.md` |
| the documentation link check, section 11, and the decision numbers' own test | `tools/check_doc_links.py`, `tests/test_doc_links.py`, `tests/test_doc_decision_numbers.py` |
| what CI runs | `.github/workflows/ci.yml` |
| the rules, the tenets, and the general learnings | `AGENTS.md`, `PRINCIPLES.md`, [golden-rules.md](../golden-rules.md) |

## 10. What each page owns

One owner per fact. A page says what the code does today, and for anything else it links to the owner; a change edits the owners it changed and the references that no longer hold, and leaves the other pages to their links. The rule is in [AGENTS.md](../../AGENTS.md); this table is the map.

| The fact | The owner |
|---|---|
| an instrument's fields: names, meanings, types, choices and rules | `src/goosedove/instruments/definitions.py`; `_ShowInstrument` spills it, and `tests/unit/test_instruments.py` holds the grid on its page equal to the spill |
| a worksheet function's signature and its Excel help | its declaration, the annotations and the docstring, which registration reads; `tests/unit/test_help.py` pins the words |
| what a function does today: its behaviour, units, limitations and a worked example | its page under `docs/library/` |
| what may cross into Python, and the order refusals come in | [inputs.md](inputs.md) |
| what may come back, and how the cell shows it | [outputs.md](outputs.md) |
| a handle's text, publication, sharing and release | [handles.md](handles.md) |
| how the host or the bridge carries a rule out | [host.md](host.md) and [bridge.md](bridge.md), and the comment beside the code, each linking to the rule it carries out |
| exact messages, hand-worked numbers, work counts and ceilings | the tests that pin them; a page keeps a derivation worth reading and names the test file, not every case |
| why a change was made, and the evidence at that revision | its pull request; [history.md](history.md) for what was declined or parked |
| a proposed behaviour or an open decision | its ticket under `docs/engineering-tickets/`, marked as proposed; a ticket that has been built is the plan as it was, and the pages above say what is |

Keep the contracts precise through any cleanup: units, accepted inputs, financial meaning, the order of refusals and intentional limitations stay as they are. When the code, a test and a page disagree, record the disagreement for its own decision; do not pick one by editing the other two.

## 11. Checking the links

`uv run python tools/check_doc_links.py` follows every local link in the repository's Markdown and names the ones that no longer resolve; `tests/test_doc_links.py` runs the same check, so `.\check.ps1` and CI fail on a broken reference before it ships. It sees the working tree of the Git-indexed files: `git ls-files` says which files exist and their text is read from disk, so an edit saved but not committed counts, a staged new page counts, and a page that exists only untracked, in another checkout or in an open pull request is a missing target until it is added here.

The repository scan requires a Git checkout and the Git executable. During setup from a source ZIP, pytest explicitly skips that scan because the archive has no `.git` entry. The checker's fixture tests still run when Git is installed and explicitly skip when it is not; the parser-only tests, decision-number checks and library tests still run. A broken Git checkout remains a failure. CI checks the repository links before distribution; a ZIP install does not need Git metadata or a Git installation.

The Markdown is read by markdown-it-py, a development dependency, and the HTML it finds by Python's own parser, so what is a link, what a reference resolves to, what is code or a comment and what a heading says are the parsers' to decide. The check owns the rest: the file inventory, the path a destination names and its spelling, case included, the file or directory it names, and the identifiers a fragment must match, GitHub's spelling of each heading with `-1`, `-2` on a repeated one, plus any explicit `<a id>` or `<a name>` anchor, which may not repeat or shadow a heading's. Checked: inline links, images and reference links, same-page and cross-page fragments, encoded and `<...>` destinations with a query string ignored; a directory is valid when it holds an indexed file present on disk. Not checked, by design: what the parser does not render as a link, such as a reference without a definition or an example in code or a comment; external links, which are never fetched; a fragment on a target that is not Markdown, such as a source line or a PDF page. A drive or UNC destination is reported as not portable; a `file:` destination is text to the parser, so it is no link at all. The decision numbers of the Decided sections of [inputs.md](inputs.md) and [outputs.md](outputs.md) are held unique by `tests/test_doc_decision_numbers.py`, apart from the link check; a new rule takes a named section, as [NUL in input text](inputs.md#nul-in-input-text) does.

Each line of output names the page, the line its block starts on, the reason and the destination as the parser read it, with the resolved path after an arrow when it differs: `docs/seam/host.md:60: unknown fragment: inputs.md#old-input-rule`. Fix the reference: retarget it, or remove the link and keep the words. A historical reference to removed material takes a commit-pinned link, and one whose target cannot be established is brought back for a decision, not excused.
