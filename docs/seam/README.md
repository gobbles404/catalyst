# The seam

The seam is the one place Excel and Python talk. When a cell holds `=Add(A1, B1)`, the seam carries the two cells into Python, checks that both are numbers, runs the function, and carries the answer back; nothing else in the code checks a type. It has two sides. The host is the C# add-in that Excel loads, one file, which reads the cells off the sheet, hands them over, and shows what comes back. The bridge is the Python side, one module, which checks every argument against the function's own signature once, runs the function, and converts every result once. Blank and missing are different facts, nothing is coerced, and a failure is text in the cell that names the function and what went wrong.

Where it stands: built, measured, and changed one step at a time, with a baseline at revision aaa5259 and one change on top of it, ahead of the first pricing function. Today the only worksheet functions are `Ping`, `GoosedoveStatus`, `HostAdd` and twelve probes, hidden functions that do no work beyond crossing the seam. The standing recommendation from the measurements is to declare pricing functions over arrays and never to read a range once per row.

These pages are for two readers: the owner, an Excel power user who is not a programmer, coming back after months and needing to find the way without memory; and an engineer maintaining the seam. Every term of art is defined the first time it appears on each page, and once more here under The words.

## Start here, by question

| The question | The page |
|---|---|
| What happens between typing a formula and seeing the answer? | [walk.md](walk.md): one call from the cell to the answer, in order, with diagrams of the layers it crosses and of what is copied and what is only pointed at |
| What may I send a function, and what happens when I send the wrong thing? | [inputs.md](inputs.md): what Excel sends, the rules, and the decisions taken |
| What may a function return, and what does the cell show? | [outputs.md](outputs.md): the result rules and the decisions taken |
| How do I add a function, a type or a probe, run the checks, load the add-in by hand, measure a change, or make a baseline? | [working.md](working.md): the recipes, and what a cell can show when something is wrong |
| How does the C# side work? | [host.md](host.md): start-up, registration, the scan of a range, the kept buffers, the way out, the errors, the counter |
| How does the Python side work? | [bridge.md](bridge.md): declaring a function, what registration resolves, the accept rules and the result rules, `Cells`, `MISSING`, the probes, and what is deliberately absent |
| How is it measured, and how do I read a number? | [measuring.md](measuring.md): the instruments, the commands, and the rules for reading |
| What are the numbers? | [baseline.md](baseline.md): the session at aaa5259, with the CSVs in [baseline/](baseline/) and every row paired with the first baseline in [baseline/since-024486f.md](baseline/since-024486f.md) |
| What was built, in what order, why, and what was tried and dropped? | [history.md](history.md): the timeline, the decisions and the tenet behind each, what was declined with the numbers that decided it, and what is open |

## When a cell looks wrong

Type `=GoosedoveStatus()`, which says whether Python started, then `=Ping()`, which says which goosedove Excel is running. `#NAME?` means the add-in is not loaded, or Python did not start so nothing was registered, or the name is misspelt. An Excel error such as `#N/A` is an error in one of the inputs, passed through unchanged. Text beginning `#ERROR Add:` is the bridge or the function itself; text beginning `#ERROR host:` is the host. The table of every case and what to do is in [working.md](working.md).

## The words

Each page defines these where it first uses them; here they are once, so the pages may share them.

- **The seam**: the one place Excel and Python talk. **The host**: its C# side, the add-in Excel loads. **The bridge**: its Python side, `bridge.py`.
- **A probe**: a hidden worksheet function that does no work beyond crossing the seam, so its cost is the seam's cost. `Add`, `SumArray` and `Grid` are probes.
- **A scalar**: one value. **An array**: a rectangle of values, always two-dimensional, even one row or one column. It is Excel's own word, and the earlier name for it was cut everywhere rather than kept beside it. **A range**: an array as it arrives from the sheet, cell by cell, before the seam has checked it.
- **A cell's kind**: which of five things a cell holds: number, text, boolean, blank, or missing. An Excel error is the sixth thing Excel can send, and it never crosses; the host returns it before Python runs.
- **Blank and missing**: a blank is an empty cell the formula referred to; missing is an argument the formula left out. `=Times(5, C2)` with C2 empty fails; `=Times(5)` takes the default.
- **A trip**: one crossing from the host into Python and back. A scalar call makes one; a range makes two, one to hand the cells over and one to run the function.
- **A look**: one pass over a whole range at once, in one operation. **A walk**: visiting cells one by one, which the seam avoids.
- **A buffer**: memory the host fills and holds still so Python can read it where it lies. The host keeps two, one of kinds and one of numbers, and grows them only for a range larger than any before.
- **The summary of kinds**: one bit per kind the host saw while scanning a range, so a range of only numbers is accepted without a look.
- **The prepared path**: `Registered.run`, the one Python function that checks a function's arguments, runs it and converts the result; the host fetches it once at registration and calls it on every recalculation.
- **Owning a range**: Python copying the host's two buffers into arrays of its own, so the host may fill the buffers again.
- **The way in** and **the way out**: an argument's path into Python, and a result's path back to the cell.
- **A counter**: a named tally of things the host did during one call, kept only when a test or a runner asks. **A ledger**: the Python side's list of which functions ran during one call, compared whole. **A ceiling**: the most memory a call may take, set at the measured figure plus a little room.
- **The pins**: the tests under `tests/performance` that hold the counts, the ledgers and the ceilings at exact values, so a seam change must say what it moved. The files are named budgets.
- **Warm**: measured after a first call has set everything up. **A session**: one sitting of the runners on one machine. **A baseline**: one session's numbers at a named revision. **A control**: a run at a larger size, kept to show how costs grow. **A floor**: the formula timed beside a case that shows Excel's own share, `HostAdd`, `SUM` or `+`.

## Where the code is

| What | Where |
|---|---|
| the host: start-up, registration, the scan, the way out, `HostAdd`, `GoosedoveStatus` | `host/Goosedove.Host/AddIn.cs`, with the counter in `WorkCounter.cs` and the settings in `Goosedove.Host.csproj` |
| the host's tests, started without Excel | `host/Goosedove.Host.Tests/` |
| the bridge, the probes, and the catalogue that imports every module of worksheet functions | `src/goosedove/excel/bridge.py`, `probes.py`, `__init__.py` |
| the messages, pinned | `tests/unit/test_type_validation.py`, `test_range_validation.py`, `test_result_validation.py`, `test_bridge.py` |
| the pins | `tests/performance/test_seam_budgets.py`, `test_seam_allocation.py`, `conftest.py`, `HostWorkBudgets.cs` |
| the runners, the summary, the before-and-after tool | `tools/performance/` |
| the smoke test in a hidden Excel, Excel by hand, the build | `tools/excel_smoke.ps1`, `tools/excel_dev.ps1`, `tools/host_build.ps1` |
| the whole check, and the Python-side measurement | `check.ps1`, `measure.ps1` |
| the pull request template | `.github/PULL_REQUEST_TEMPLATE.md` |

## How to check and measure

```bash
uv sync --locked
```

After pulling. Then the whole check, which runs format, lint, types, the Python tests, the host's tests, and last the smoke test in a hidden Excel, which needs Excel and which CI cannot run:

```bash
.\check.ps1
```

The runners, one per clock: `.\measure.ps1` for the Python side, `dotnet run --project tools/performance/Goosedove.Host.Measure -c Release` for the host, and `.\tools\performance\measure_excel.ps1` for Excel, with `-Rows 10000` for the control. A seam change runs `.\tools\performance\before_after.ps1` on an idle machine and pastes its report whole. To try formulas by hand, `.\tools\excel_dev.ps1` builds the add-in and opens it in a fresh Excel. Each command and what its clock includes is in [measuring.md](measuring.md); the recipes are in [working.md](working.md).

The rule behind all of it: work is counted, and the counts are tests; time is a record, and no timing gates a merge. The pins move with the source in the same pull request, because they are the claim a change makes; a baseline document lands in a pull request of its own, because it is the record.

## This directory is the map

Every page here moves with the code it describes, and nothing about the seam is written anywhere else.

- A new declared type moves [inputs.md](inputs.md), [outputs.md](outputs.md) if it can be returned, and the two tables in [bridge.md](bridge.md).
- A change to the host moves [host.md](host.md), the steps in [walk.md](walk.md), and the pins in `HostWorkBudgets.cs`.
- A change to the bridge moves [bridge.md](bridge.md) and the Python pins.
- A new probe moves `probes.py`, the three runners, the smoke test, the pins, and the probe tables in [measuring.md](measuring.md) and [bridge.md](bridge.md).
- A new baseline replaces [baseline.md](baseline.md) whole, with its CSVs and a new paired-rows file, and adds a row to the timeline and the two-baselines table in [history.md](history.md).
- Anything tried and declined, or found and parked, goes in [history.md](history.md), so it is not proposed again from memory.

A seam change states its counts before and after in the pull request, under the template's six headings: What, Counts, Tenets, Conflicts, Checked in Excel, Not done. When a rule and a tenet conflict, the tenet decides; the pull request names the tenet under Tenets and the fork under Conflicts. The tenets are in [PRINCIPLES.md](../../PRINCIPLES.md), the general learnings in [golden-rules.md](../golden-rules.md), the rules in `CLAUDE.md`, and the setup in the repository's [README.md](../../README.md).
