# Fixings group: verification notes

Worktree: `worktrees/wf_0d4f8983-1f8-2` (branch `worktree-wf_0d4f8983-1f8-2`, from main at 40fab53, PR #118).
numpy 2.5.2, Python 3.13.12 (the venv's interpreter, `<repo>/.venv/bin/python`).

## Commits (each candidate isolated; non-recommended ones reverted, so the tip = main + c2 + c4)

| commit | what |
|---|---|
| ed3a87e | holiday-busdaycal-once (design-fork), reverted by 1d7d3dc |
| 18276c9 | futures-fixings-wholeness-by-count (**recommend**) |
| 3c464d4 | futures-fixings-closed-by-all (marginal), reverted by 89a502d |
| 54feebe | gas-daily-consecutive-by-span (**recommend**) |
| 9e300f2 | builders-copy-of-fresh-seam-columns PROTOTYPE (design-fork), reverted by 0deb190 |

`diff_<id>.patch` is `git show` of each candidate's own commit.

## Verdicts

| id | verdict | the count that moves |
|---|---|---|
| holiday-busdaycal-once | design-fork | reader peaks fall (fixings 18,410 -> 10,362 B at 260 rows/1,000 holidays; calendar 360 days 8,588 -> 7,788 at 100 holidays), creator peak rises 17 -> 24 B/holiday (240,672 B at 10,000) and creator time about x5 at 10,000 holidays; ledgers unchanged. Adds a field to a library record and moves the normalization from each reader call to the creator: the owner's call. |
| futures-fixings-wholeness-by-count | recommend | `ndarray.any` 4 -> 3, `ufunc.reduce` 4 -> 3; peak 11,210 -> 8,511 B at 260 rows, 93,110 -> 69,367 at 2,600, 912,110 -> 677,767 at 26,000; one O(N) busday_offset pass, one 8 B/row column and one 1 B/row mask and one any() pass gone from the success path |
| futures-fixings-closed-by-all | marginal | ledger relabel only (`ndarray.any` -1, `ndarray.all` +1, `ufunc.reduce` unchanged); whole-call peak unchanged at 260/2,600/26,000 rows; one invert pass and a 1 B/row mask fewer in isolation; time within noise |
| gas-daily-consecutive-by-span | recommend | peak 13,100 -> 10,044 B at 365 days, 121,521 -> 92,169 at 3,650, 1,205,571 -> 913,419 at 36,500; `ndarray.view` +1 (no copy); 8 B/row column and one datetime add pass gone from the success path |
| builders-copy-of-fresh-seam-columns | design-fork | `numpy.array` 2 -> 0 (`numpy.asarray` 0 -> 2); peak 8,511 -> 6,303 B at 260 rows, 69,367 -> 45,424 at 2,600; gas 10,044 -> 7,429 at 365. Breaks the ownership rule: two unit tests fail ("assignment destination is read-only"), and a strided Python input is kept non-contiguous. |

## Files

- `eq_cases.py` / `eq_compare.py`: 13,950 equivalence cases run on two trees in fresh processes (pickled outcomes); `eq_breakdown.py` shows which failure branch each case reached. Outputs: `eq_<id>.txt`, `eq_final.txt`, `eq_breakdown.txt`.
- `variants_c4.py` / `variants_c4.txt`: why the gas-daily candidate takes the Python-int span with a size guard (the int64-subtract variant warns or raises IndexError; a datetime-only variant accepts `[d, NaT, d+2]`).
- `micro.py` and `micro_c1..c5.md`: isolated operations, timeit min-of-7 and tracemalloc peak.
- `peaks.py`, `peaks_*.txt`: `least_peak` exactly as `tests/performance/test_seam_allocation.py` measures it.
- `bench/`: copies of the shared harness and compare script, with added scenarios (`create.FuturesFixings.*.h1000/h10000`, `create.Calendar.futures.*.h1000/h10000`, `create.HolidayCalendar.10000`, `create.GasDailyFixings.36500`). Tables: `<id>.md`, `final_combined.md`. c3 and c5 were compared against an exported tree of the commit before them (`trees/after_c2`, `trees/after_c4`) so their tables are isolated.
- `run_tests.sh`: the unit and budget suites on the worktree.

## Caveats

- Timing on this box is very noisy (medians of the same tree differ by 2x between runs, other agents share the cores): read the peak and ledger columns, and the time only where the change is large and consistent.
- One full unit run (of seven on the c2 tree) reported `1 failed, 1270 passed` and the name was cut off by my `tail`; every other full run (five more on that tree and on each later state) and five reruns of the fixings and market files passed. Most likely a Hypothesis deadline under load; not reproducible.
- pyright needs `--pythonpath <repo>/.venv/bin/python` in the worktree (no `.venv` there); without it 518 import errors appear that are environmental.
