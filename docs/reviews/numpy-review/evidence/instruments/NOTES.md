# Group 'instruments': verification notes

Worktree: worktrees/wf_9922a729-5fc-3 (branch worktree-wf_9922a729-5fc-3, base 40fab53 = main at #118).
Python 3.13.12 from <repo>/.venv, numpy 2.5.2. Every script here takes the tree on PYTHONPATH and says which goosedove it imported.

## Verdicts

| # | candidate | commit | verdict | one line |
|---|---|---|---|---|
| 1 | instrument-ledger-regex-drops-dotted-builtins | 48125c6 | recommend | 15 numpy pins gain exactly one real entry each (count_nonzero x13, interp x2); nothing already counted moves |
| 2 | instrument-numpy-callables-ledger-sys-monitoring | d0ae041 | recommend | third ledger via sys.monitoring CALL; deterministic; sees busdaycalendar/is_busday/busday_offset/interp/named ufuncs; tool id moved 3 -> 4 (3 is Hypothesis's) |
| 3 | instrument-ufunc-ledger-traced-inputs | 034dbea (reverted 7182db8) | marginal | deterministic and exact by its own definition, but it changes what it measures (3 of 33 traced scenarios return '#ERROR returned a numpy Traced'), its counts depend on a mode and on where the library happens to drop the subclass, and 'touched' is operand bytes, not passes |
| 4 | instrument-creators-timed-with-release | 701e8bc | recommend | 14 creator rows in measure_python, 2 workloads in profile_workload; store flat across every row; release 0.23 us |
| 5 | instrument-date-probe-already-exists-in-conftest | d91a5c3 (reverted 15827b2) | design-fork | a source change to the add-in's hidden surface against a documented rule (bridge.md, working.md step 8); two call_profile pins gain the probe's own frame (the candidate said none); the parked item asks for rows in all three runners |
| 6 | instrument-retained-numpy-bytes-by-tracemalloc-domain | 5fbcf68 | recommend | exact retained bytes per creator from numpy's tracemalloc domain 389047, 0 after release; deterministic across two runs on all 37 creator scenarios |
| 7 | instrument-allocation-creators-release | 5562821 | recommend | 24 creator call sites move from least-of-three-retained to one call released inside it; figures equal or 16..96 B lower; same ceilings; the module retains 154 publications at the end instead of 311 |
| 8 | instrument-cells-from-buffers-new-size-scenario | 3d353e9 (reverted 06c62d2) | reject | the row as proposed times sizes 101..14,438 under a cells_in of 100 (144x), 2.4x at 10,000; its label and its peak are not the size it names |
| 9 | instrument-from-rows-empty | d4cf566 (reverted 1f6d817) | marginal | exact on 18 inputs incl. every failure path; removes np.full's copyto (one 8 B/cell write pass) but from_rows is off every clock and ledger, peak unchanged, time within noise (the Python loop is 8.4 ms at 10,000) |

Final tree = 1, 2, 4, 6, 7 applied (the others reverted on top): no file under src/ differs from main.
ruff check: All checks passed. ruff format --check: 78 files already formatted. pyright (strict, --pythonpath the venv): 0 errors, 0 warnings.
tests/unit: 1271 passed. tests/performance: 107 passed (103 as-is + 4 new), with xdist (-n 2) and without.
bench_compare of the final tree (final_tree.md, 5 rounds): every peak, numpy ledger and package ledger 'same'; every timing move inside the as-is spread.

## Evidence per candidate

1. regex_coverage.py -> regex_coverage.out. Over all 73 harness scenarios: 30 gain an entry, every as-is entry unchanged, gained = numpy.count_nonzero in 28, numpy.interp in 2; no numpy-named C call is left that neither pattern reads. Demonstration: _cell counting the text codes twice leaves the as-is ledger identical (True) and the fixed ledger at count_nonzero 2. Budget pins that failed and their new entries: patch_pins_regex.py.
2. monitor_ledger.py -> monitor_ledger.out. 53 of 73 scenarios call a numpy callable; every ledger identical on a second run. Hoisting np.busdaycalendar out of the fixings creator moves 'type:busdaycalendar' 1 -> 0 while the cProfile ledger and the package ledger stay equal (True, True). Pins added: patch_pins_callables.py.
3. traced_ledger.py -> traced_ledger.out; traced_leak.py -> traced_leak.out (no Traced array reaches a record: all 18 creator read-backs identical). FirstOfDates 10,000: 8 ufuncs, 740,000 bytes (74 B/cell) in full mode, 5 ufuncs 670,000 in transparent mode.
4. creators_rows.py -> creators_rows.out (store +0 on every row; 85 scenarios = 71 as-is + 14).
5. first_of_rows.py -> first_of_rows.out (package probe vs outside probe: same peaks to the byte at 1..100,000 cells; times within noise).
6. retained_bytes.py -> retained_bytes.out (domain self-check 32,768 of 32,768; settles kept as a view drops held by 20,800 = 8 x 2,600).
7. creator_peak_compare.py -> creator_peak_compare.out; store_count_plugin.py for the 311 -> 154 retention count.
8. new_size.py -> new_size.out; new_size_rows.py -> new_size_rows.out.
9. from_rows_equiv.py -> from_rows_equiv.out (runs each tree in its own subprocess).

## Things the candidates got wrong, found here

- 2: sys.monitoring tool id 3 is not free: hypothesis/internal/scrutineer.py uses MONITORING_TOOL_ID = 3. Implemented on 4.
- 3: RowSums does not run unchanged in full mode (the sum keeps the subclass and the result rule refuses it); EchoDates neither.
- 5: 'pins moved: none' is wrong; the probe defined in the package is counted by call_profile, so test_accepted_date_column_call_itemized gains "FirstOfDates": 1 and test_accepted_text_column_call_itemized gains "FirstOfNames": 1.
- 7: one released call is not perfectly constant either: the curve's figure drifts 216,387 -> 216,315 over five calls (16 B a call), contract specifications 13,283 -> 13,211; both stay under least_peak's figure and the ceiling.
- 8: the proposal's sizes iterator drifts with the calibration (2,048 iterations x 7 passes), so the row's cells_in is not the size it times except at 100,000.

## Not done

- No host (Scenarios.cs) or Excel runner rows for 4 or 5.
- No history.md row for any candidate; the open items 'No text probe and no date probe' and 'The numpy rearrangement of the date checks' are untouched.
- The memmove alternative to cells_from_buffers is measured in new_size.py for information only (equal values, dtype, shape, flags; 10.45 us at one size vs 8.81 us warm today, 18.18 vs 36.78 us when the size changes every call); it belongs to another group.
