# Measuring

How the seam is measured, and how to read a number. Two questions drive it: does the bridge carry values correctly, and how does its cost grow. Correctness is the tests' job and is not repeated here. This file is about cost: what is counted, what is timed, where the reports land, and what each number includes and leaves out.

The rule from CLAUDE.md holds throughout: work is measured by counts, and counts are tests; time is measured by tools, and no timing gates a merge.

## The probes

Every measurement drives the probes in `src/goosedove/excel/probes.py`: hidden worksheet functions, one per thing the host can tell apart, each doing no work beyond proving its fact, so its cost is the seam's cost. The knobs are how many calls, how many cells in, and how many cells out.

| Probe | Knob |
|---|---|
| `Zero()` | the floor of one call |
| `Add(a, b)` | a scalar call with two arguments |
| `Times(x, factor=1.0)` | an omitted argument |
| `SumArray(values)` | cells in, any shape, one number out |
| `Dot(a, b)` | two ranges in one call |
| `EchoColumn(values)` | the round trip: N in, N out |
| `RowSums(values)` | one answer per input row, the shape of pricing every row |
| `Grid(rows, cols)` | cells out from two numbers in |
| `EchoText`, `EchoBoolean`, `EchoRow`, `Fail` | correctness rows; not run for capacity |
| `HostAdd(a, b)` | the floor under every probe: a C# function with the host's argument shape and no Python, so Excel and Excel-DNA's share of a call is measured beside the seam's; it lives in `AddIn.cs`, hidden like the probes |

## Counts, as tests

**Python, `tests/performance/test_seam_budgets.py`.** Two ledgers per probe, both exact and both deterministic. `call_profile` lists the seam's own functions that ran and how many times: `Registered.run`, the prepared path, then `_validate`, `_numbers`, the probe, the result rule. `numpy_calls` lists the numpy C calls cProfile saw: `ndarray.copy`, `ndarray.sum`, `ndarray.all`, `ufunc.reduce`, `numpy.frombuffer`, `numpy.ascontiguousarray`. A range whose summary from the host says all numbers, or all text, takes no look at its kinds, so nothing numpy did appears on an accepted range in; a rejected range finds its first bad cell with `argmax`, and `ndarray.any` appears only where a value must be checked, the date paths. That second ledger is measured, not derived; a ufunc applied by an operator, such as the kinds compare, raises no cProfile event and is not in it. `tests/performance/test_seam_allocation.py` pins the peak of the Python heap during one warm call with `tracemalloc`, which sees numpy's data buffers and not the host's.

**Host, `tests/performance/HostWorkBudgets.cs`.** The host reports what it did to a `WorkCounter` the observer supplies; a worksheet call passes none, so the worksheet path builds nothing. Every increment sits at a boundary, never inside the cell loop.

| Counter | What the host did |
|---|---|
| `trips` | calls into Python: the function's prepared path, and `cells_from_buffers` once per range |
| `name_lookups` | Python attributes fetched by their text name; a prepared call makes none |
| `objects_built` | Python objects the host made: each scalar; a range's rows, columns and summary of kinds, its text when it has any, and the two buffer addresses when the buffers grow |
| `cells_scanned` | cells visited by the scan, the Excel error that stopped it included |
| `text_cells` | text cells collected in that scan |
| `buffers_allocated`, `buffer_bytes` | managed arrays made, and their payload bytes: for a range in only when the kept buffers grow to a larger range than any before, and for an array out |
| `result_copies`, `result_cells` | copies made of an array on its way to Excel, and its cells |

The same file pins what the host's own runtime allocates per call, four ways, with `GC.GetAllocatedBytesForCurrentThread`: a ceiling on a warm scalar call, a ceiling on a warm range in at ten thousand cells, and the bytes per added cell in and per added cell out between a thousand and ten thousand cells. Scope: the CLR heap on this thread only. Not Python, not numpy, not Excel-DNA.

A seam change states its counts before and after. A change that moves no counter is not the change it claims to be.

**Before and after, every row.** A seam change is also measured across the whole seam, not only where it aimed. `tools/performance/before_after.ps1` checks the change's base out into a temporary worktree, runs the three runners on the base and on this tree in one session, one runner at a time on each side, and `compare.py` writes `profiles/compare.md`: every timed row of every layer with the before and after medians and their batch spreads, every host counter that differs, and the allocation figures. A row counts as moved only when its two batch spreads do not overlap, and even then a change with no effect moves rows by a few percent within one session: the rename that changed nothing moved a third of the rows, most by under 5% and a few by more where one side's early batches ran slow. Read a move as real when it is large, consistent across sizes, and where the change aimed; a large move where it did not aim is the finding. The pull request pastes the report whole.

## Time, as tools

Each runner warms once, checks the answer, calibrates the number of calls until a batch takes about 50 ms, runs five batches, checks the last result of each batch outside the clock, and writes every batch as one row. `per_call_us` is a batch mean, never a percentile of single calls. Beside each CSV sits an environment file naming the revision, the hashes of the seam's source and the host's assembly, the runtimes, and one sentence saying what the clock includes.

| Command | Clock | Includes | Leaves out |
|---|---|---|---|
| `uv run python tools/performance/measure_python.py` | each function's prepared path, held once, on `Cells` built before the clock | validation, the probe, result conversion; `cells_from_buffers` from buffers as its own scenario | the host, Excel, building the inputs |
| `dotnet run --project tools/performance/Goosedove.Host.Measure -c Release` | the registered delegate | marshaling, the trip into Python, validation, the probe, result conversion, the way back to a .NET value; plus two stage rows, `way in` (`Marshal.ToPython` alone) and `way out` (`Marshal.FromPython` alone), with the GIL held outside the clock | Excel and Excel-DNA |
| `.\tools\performance\measure_excel.ps1` | `Range.Calculate` or `Application.Calculate` over COM in a hidden Excel | everything a user feels: Excel, Excel-DNA, the host, Python, and the COM round trips | startup, building the sheets, checking answers |
| `uv run python tools/performance/summarize.py` | none | reads whatever CSVs exist under `profiles/` and writes `profiles/summary.md`, one table, a column per layer | |
| `.\tools\performance\before_after.ps1` | the three runners above, on the base of the change and on this tree, one runner at a time on each | every row of every layer, side by side, in `profiles/compare.md` | nothing; a row that moved where the change did not aim is the finding |
| `uv run python tools/performance/profile_workload.py` | a sampling profiler over repeated calls | where a probe's time goes, as an HTML report per probe | how long one call took |

`measure.ps1` runs the Python side: the profiler, the Python runner, and the summary. The host runner and the Excel runner have their own commands above; run the summary again after either, and it adds their columns. CI runs `measure.ps1` and uploads `profiles/`; the host runner is built in CI so it keeps compiling and is never run there.

Sizes: 1, 100, 1,000, 10,000 and 100,000 cells. One hundred cells per call and a thousand calls per recalculation is the working workload; 100,000 is the control that shows scaling without defining the ordinary case. Rejections are timed as their own scenarios, because early failure does less work.

**The Excel runner** answers the question the other two cannot: how a formula's shape changes what a user waits for. Every case has a native control beside it, and every answer is checked before and after timing.

| Sweep | Cases | Knob |
|---|---|---|
| call count | `=Add(Ai,Bi)` beside `=HostAdd(Ai,Bi)` and `=Ai+Bi`, down 100, 1,000 and 10,000 rows | what one call costs, and Excel's share of it |
| cells in | a hundred copies of `=SumArray(A1:A_N)` beside `=SUM(A1:A_N)`, N in 100, 1,000, 10,000 | what a cell in costs |
| cells out | a hundred copies of `=Grid(N,1)` spilled | what a cell out costs |
| the same answers three ways | 1,000 `=Times(Ai)` filled down, ten `=EchoColumn` over hundred-row arrays, one `=EchoColumn(A1:A1000)`; and RowSums over A1:J1000 in the same three arrangements | whether batching pays, and from how many rows |
| edit one input | each arrangement after its middle input changes, beside the same write with nothing dependent | what a user pays for one change |

A single `Range.Calculate` costs about 0.4 ms over COM before any formula runs, which is why single-formula cases are placed a hundred times and timed as one range. `per_call_us` is per formula the recalculation reaches, `per_recalc_us` per recalculation; for the batching rows the second is the one to read. The row count of the arrangements is the `-Rows` parameter: 1,000 is the working workload and writes `excel-timing.csv`; `-Rows 10000` is the control and writes `excel-timing-rows10000.csv` beside it, which the summary does not read. Two facts about Excel shape the edit rows and are recorded in the environment file: `Range.Calculate` leaves its cells dirty, so an edit batch is preceded by one cleaning `Application.Calculate` off the clock; and a recalculation with any dirty cell does bookkeeping for every formula in the workbook, so each arrangement lives in a workbook of its own.

## How to read a number

- **Layers are separate clocks.** The Python runner, the host runner, and Excel time different spans of the same call. Read them side by side; never subtract one from another to name a stage's cost.
- **Excel's own price sits under every formula.** `HostAdd`, a C# function with no Python, is the floor under every scalar call; `=SUM` and `=A1+B1` are the floors under ranges and arithmetic. A refactor is judged against the seam's share, not the whole.
- **An edit is mostly Excel.** Writing one cell over COM and asking Excel to recalculate costs about a millisecond before any formula runs; the `no formula` row measures it. What the arrangements add on top of that row is the formula work one change reaches: one row's call, one array, or the whole sheet.
- **Counts before time.** When a timing moves, the counters say what moved; when the counters move, the timing says whether it mattered.
- **Variation is part of the answer.** Large outputs vary several-fold between batches under garbage collection; the min and max beside the median carry that, and `batches.csv` records collection counts per batch.

## The baseline

[baseline.md](baseline.md) holds one session's numbers at a named revision, the CSVs they were read from in `docs/seam/baseline/`, and what they say about how the library's formulas should be shaped. A seam change is judged against those rows. A new baseline replaces the last one whole, says what moved since it, and keeps the paired rows beside its CSVs; the earlier document and CSVs stay in git history at the revision the new one names.

## Where reports land

`profiles/`, ignored by git: `python-timing.csv`, `python-allocation.csv`, `python-environment.json`, `host-measure/batches.csv`, `host-measure/work.csv`, `host-measure/environment.json`, `excel-timing.csv`, `excel-timing-environment.json`, the same two with `-rows<N>` in the name for a control run, `summary.md`, and one HTML profile per probe.
