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

## Counts, as tests

**Python, `tests/performance/test_seam_budgets.py`.** Two ledgers per probe, both exact and both deterministic. `call_profile` lists the seam's own functions that ran and how many times: `call`, `_validate`, `_numbers`, the probe, the result rule. `numpy_calls` lists the numpy C calls cProfile saw: `ndarray.copy`, `ndarray.any`, `ufunc.reduce`, `numpy.frombuffer`, `numpy.ascontiguousarray`. That second ledger is measured, not derived; a ufunc applied by an operator, such as the kinds compare, raises no cProfile event and is not in it. `tests/performance/test_seam_allocation.py` pins the peak of the Python heap during one warm call with `tracemalloc`, which sees numpy's data buffers and not the host's.

**Host, `tests/performance/HostWorkBudgets.cs`.** The host reports what it did to a `WorkCounter` the observer supplies; a worksheet call passes none, so the worksheet path builds nothing. Every increment sits at a boundary, never inside the cell loop.

| Counter | What the host did |
|---|---|
| `trips` | calls into Python: the seam's `call`, and `cells_block` once per range |
| `name_lookups` | Python attributes fetched by their text name |
| `objects_built` | Python objects the host made: the name, the argument list, each scalar, the five values that carry a range |
| `cells_scanned` | cells visited by the range loop, the Excel error that stopped it included |
| `text_cells` | text cells collected in that loop |
| `buffers_allocated`, `buffer_bytes` | managed arrays made for a range in or a block out, and their payload bytes |
| `result_copies`, `result_cells` | copies made of a block on its way to Excel, and its cells |

The same file pins three managed-allocation ceilings with `GC.GetAllocatedBytesForCurrentThread`: bytes per warm scalar call, bytes per added input cell, bytes per added output cell. Scope: the CLR heap on this thread only. Not Python, not numpy, not Excel-DNA.

A seam change states its counts before and after. A change that moves no counter is not the change it claims to be.

## Time, as tools

Each runner warms once, checks the answer, calibrates the number of calls until a batch takes about 50 ms, runs five batches, checks the last result of each batch outside the clock, and writes every batch as one row. `per_call_us` is a batch mean, never a percentile of single calls. Beside each CSV sits an environment file naming the revision, the hashes of the seam's source and the host's assembly, the runtimes, and one sentence saying what the clock includes.

| Command | Clock | Includes | Leaves out |
|---|---|---|---|
| `uv run python tools/performance/measure_python.py` | `bridge.call` on `Cells` built before the clock | validation, the probe, result conversion; `cells_block` from buffers as its own scenario | the host, Excel, building the inputs |
| `dotnet run --project tools/performance/Goosedove.Host.Measure -c Release` | the registered delegate | marshaling, the trip into Python, validation, the probe, result conversion, the way back to a .NET value; plus `Marshal.Append` alone and `Marshal.FromPython` alone with the GIL held outside the clock | Excel and Excel-DNA |
| `uv run python tools/performance/summarize.py` | none | reads whatever CSVs exist under `profiles/` and writes `profiles/summary.md`, one table, a column per layer | |
| `uv run python tools/performance/profile_workload.py` | a sampling profiler over repeated calls | where a probe's time goes, as an HTML report per probe | how long one call took |

`measure.ps1` runs the Python side: the profiler, the Python runner, and the summary. The host runner has its own command above. CI runs `measure.ps1` and uploads `profiles/`; the host runner is built in CI so it keeps compiling and is never run there.

Sizes: 1, 100, 1,000, 10,000 and 100,000 cells. One hundred cells per call and a thousand calls per recalculation is the working workload; 100,000 is the control that shows scaling without defining the ordinary case. Rejections are timed as their own scenarios, because early failure does less work.

## How to read a number

- **Layers are separate clocks.** The Python runner, the host runner, and Excel time different spans of the same call. Read them side by side; never subtract one from another to name a stage's cost.
- **Excel's own price sits under every formula.** A C# function with no Python costs Excel and Excel-DNA about 3 µs per call; ten thousand cells cost about 430 µs to box before the host sees them; ten thousand results cost Excel about 2 ms to spill. A refactor is judged against the seam's share, not the whole.
- **Counts before time.** When a timing moves, the counters say what moved; when the counters move, the timing says whether it mattered.
- **Variation is part of the answer.** Large outputs vary several-fold between batches under garbage collection; the min and max beside the median carry that, and `batches.csv` records collection counts per batch.

## Where reports land

`profiles/`, ignored by git: `python-timing.csv`, `python-allocation.csv`, `python-environment.json`, `host-measure/batches.csv`, `host-measure/work.csv`, `host-measure/environment.json`, `summary.md`, and one HTML profile per probe.
