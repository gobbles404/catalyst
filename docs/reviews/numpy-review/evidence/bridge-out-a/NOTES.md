# Group bridge-out-a: verification notes

Worktree: worktrees/wf_1c4545af-6ae-2 (branch worktree-wf_1c4545af-6ae-2, base 40fab53 = main at #118)

Commits:

| commit | candidate | verdict |
|---|---|---|
| f63a8ac | bridge-serials-out | recommend |
| 84ce5a5 | bridge-table-column-writes-into-slots | recommend |
| 5260e3f | bridge-table-text-gather (form F: slice copy, no singleton branch) | recommend |
| 3a5011c | bridge-mixed-out-looks | recommend |
| 91a574c | bridge-mixed-out-ascii-units | design-fork |
| 6a29f69 | revert of 91a574c, so the tree holds the recommended set only | |

Run everything with `PYTHONPATH=<tree>/src <repo>/.venv/bin/python <script>`.
Pyright needs `--pythonpath <repo>/.venv/bin/python` because the worktree has no .venv.

## Files

- `eqlib.py`: loads the as-is bridge (<repo>/src/.../bridge.py as `asis_bridge`) beside the worktree's, and compares bit for bit (dtype, shape, C-contiguity, writeable), or by exception type and message. Warnings are errors.
- `eq_serials.py` covers candidates 1 and 2: _serials, _date_out, _date_column_out, _date_row_out and table date columns. Inputs: NaT, outside dates, edges, empty, one cell, read-only, strided, reversed, sizes 100, 3,631 and 36,630, and int64 extremes. Output: `eq_serials.final.out`.
- `eq_table.py` covers candidates 2 and 3: MixedArray.table over every column kind (f2/f4/f8 with NaN, inf, -0.0 and subnormals; bool; i1/i8/u4/u8; days; a 2^53 bound first, middle or last; seconds, months, timedelta, complex, object, unicode, 2-D, masked, list), 0 to 2 heading rows, 0/1/2/3/5 text columns in every order, 0 to 36,630 rows, and every failure branch. It also checks that the str objects are identical. Output: `eq_table.final.out`.
- `eq_mixed_out.py` covers candidates 4 and 5: 3,000 random records plus F-order, read-only and strided variants, every branch at the first, middle and last cell of 1x1, 1x7, 7x1 and 100x100, text limits and malformed records. Output: `eq_mixed_out.final.out`.
- `eq_text_units.py` covers candidate 5: 600 random text tuples over ASCII, Latin-1, BMP and astral text around MAX_TEXT, plus lone surrogates. Output: `eq_text_units.final.out`, run on the final tree where candidate 5 is reverted. The run with candidate 5 applied gave 611 cases and 0 differences.
- Micro-benchmarks: `shift_forms.py` (+ `.out`), `small_peak.py`, `inplace_constant.py`, `out_constant.py`, `table_micro.py` (+ `.asis*.out`, `.c1.out`, `.c2.out`), `gather_forms.py` (+ `.out`), `mixed_micro.py` (+ `.asis.out`, `.c4.out`, `.c5.out`), `text_rule_micro.py` (+ `.out`).
- Whole-call tables (bench_compare, 5 rounds):
  - `bridge-serials-out.md` (as-is vs c1)
  - `bridge-table-column-writes-into-slots.md` (as-is vs c1+2)
  - `bridge-table-text-gather.md` (as-is vs c1..3)
  - `bridge-mixed-out-looks.md` (c3 vs c4, isolated)
  - `bridge-mixed-out-ascii-units.md` and `.rerun.md` (c4 vs c5, isolated)
  - `final_recommended_set.md` (as-is vs c1..4)
  - `trees/c3` and `trees/c4` are `git archive` snapshots used as the isolated bases.
- `patch1.py`..`patch5.py` apply each candidate in order. The commits are authoritative; their diffs are in `diff_*.patch`.
- `final_performance.txt`: the budget-test run on the final tree.

## Findings that matter beyond the numbers

1. **A numpy constant at exactly one element.** An in-place ufunc whose output is also one of its inputs (`a -= x`, `a |= b`, `np.logical_not(a, out=a)`) allocates about 1 KB of traced memory when the array has exactly one element. At two elements or more it allocates 0 to 208 B (`inplace_constant.py`, `out_constant.py`). Two pins see it:
   - The valuation-date reader rises from 1,671 to 2,102 B and fails its 2*SLACK = 2,048 ceiling.
   - A one-cell `_mixed_out` rises from 492 to 1,298 B, which is not pinned.

   Every form that avoids it costs more at size:
   - `np.subtract(counted, E, dtype=f8)` adds a buffered cast of up to 64 KB.
   - `(counted - E).astype(f8)` adds 8 B per cell.

   So the right fix is to re-pin that one ceiling, for example to 3*SLACK.
2. **Pick the shift form by bytes, not by time.** The int-to-float shift has several forms:
   - `astype` then `-=` peaks at 8 B per cell, the output itself.
   - `np.subtract(..., dtype=float64)` buffers the cast, so 16 B per cell up to 64 KB.
   - `(c - E).astype()` peaks at 16 B per cell.
   - Written into the strided slot column with `[...] = counted; -= E`, the peak is 208 B at any size. It is a strided pass, about 11 us at 3,631 cells against 5 us contiguous, but it replaces a 20 us as-is path.
3. **One message changes on an absurd input.** For the single day `np.datetime64(2**63-1, 'D')` (int64 max), the as-is code raises an internal `OverflowError: Overflow in datetime64 - datetime64 subtraction`, which the seam turns into `#ERROR f: OverflowError: ...`. Candidates 1 and 2 name the cell instead: "is a date outside 1900-03-01 to 9999-12-31". Days at max-25569 and max-25570 already gave equal outcomes on both trees. No unit test pins the as-is text, and only a Python-built array can produce this day.
4. **Text gather.** The reviewers' one-column branch (C) breaks the One path tenet (PRINCIPLES.md, "N of one is a group of one"), so I did not take it. The general zip form (B) is slower than as-is at one column: 170 vs 126 us at 3,631 rows. The implemented form F has no branch. It copies each text column into its strided slice of one list, then makes one tuple:
   - 1 column: about 3.5x faster at 3,631 rows (126 -> 34 us) and 2.7x at 36,630 (1,737 -> 638 us).
   - 2 columns: about 4.4x faster at 3,631 rows (294 -> 67 us).
   - 5 columns: about 5.8x faster at 3,631 rows (1,071 -> 185 us).
   - Peak is the same 16 B per text as as-is.

   C would also halve the peak at one column (8 B per text), for a singleton branch. That is the owner's call if ever wanted.
5. **mixed-out-looks relies on kinds and slots having the same shape.** That holds for every builder in the package:
   - `MixedArray.table`: `np.empty`/`np.full((top + rows, width))`, bridge.py:139-140.
   - `utilities.py:143-147`: `(rows, width + 1)` for both.
   - `_mixed`, bridge.py:491, from `Cells`.
   - `_one_cell`, bridge.py:521.

   With mismatched shapes, the as-is code broadcast silently and handed the host arrays of different shapes. The proposal raises a numpy ValueError. A float kinds array holding NaN changes from a RuntimeWarning to a ValueError. Both are outside the record's declared types, and no typed input diverges.
6. **ascii-units is a design-fork, not a recommend.** It is exactly equivalent (611 text cases, 0 differences) and removes real work. In isolation:
   - Below the limit: 8,767 -> 92 B, and the 2-byte-per-character encode is gone.
   - 7,260 texts: 334,775 -> 218,507 B.
   - 73,260 texts: 3.37 MB -> 2.20 MB.
   - Whole call: EchoMixed mixed 62,117 -> 34,302 B; ContractSpecifications.120 16,135 -> 11,560; MarketHistory.futures.3630 616,568 -> 534,093.

   But the ASCII case is a specific path that does not go through the general UTF-16 count, which is what the One path tenet forbids. No O(1) branch-free UTF-16 count exists in Python, so this needs the owner's call. No pin moves at pinned sizes.
7. **A flaky unit test, unrelated to these changes.** `tests/unit/test_iferc_schedule.py::test_any_columns_with_one_row_per_code_are_kept_aligned` failed once under load, during the candidate-4 run. It is a hypothesis test that does not touch bridge.py, so the likely cause is the 200 ms deadline. It passed in six seeded reruns and in every other full run, including the final one: 1,271 passed.

## Pins on the final tree (c1..c4)

The final run had 10 failing budget pins and 93 passing. Every failure is a ledger or ceiling moving with the source:

- **test_seam_allocation::test_a_creator_of_a_small_object_and_its_reader_stay_small**: the valuation-date reader is now 2,102 B against a 2*SLACK = 2,048 ceiling. The cause is the one-element in-place constant; re-pin to 3*SLACK.
- **test_seam_budgets::test_a_mixed_array_out_takes_three_looks_whatever_it_holds[numbers]** and **[mixed]**:
  - Package ledger: loses `_bad_mixed: 1`.
  - Numpy ledger: `ndarray.any 3->1`, plus `ndarray.max: 1` and `ndarray.all: 1`.
- **test_a_reader_is_a_text_call_one_lookup_and_a_table_out** (the curve reader):
  - Package ledger: `_serials: 1` -> `_not_days: 1`, and `_bad_mixed: 1` gone.
  - Numpy ledger: `ndarray.any 5->1`, plus `ndarray.view: 1`, `ndarray.min: 1`, `ndarray.max: 2` and `ndarray.all: 1`.
- **test_reading_an_index_back_costs_one_row**:
  - Package ledger: `_bad_mixed` gone.
  - Numpy ledger: `numpy.array 4->3`, `ndarray.ravel 1->0`, `ndarray.any 5->3`, plus `ndarray.max: 1` and `ndarray.all: 1`.
- **test_reading_a_calendar_back_rebuilds_nothing**, **test_reading_a_market_history_back_rebuilds_nothing** and **test_reading_a_market_back_rebuilds_nothing[futures, Gas Daily, IFERC]**:
  - Package ledger: `_serials: 1` -> `_not_days: 1`, and `_bad_mixed` gone.
  - Numpy ledger: `ndarray.any 5->1`, `numpy.array 2->1`, `ndarray.ravel 1->0` (market: `2->1`), plus `view: 1`, `min: 1`, `max: 2` and `all: 1`.
  - These per-scenario numpy diffs are read from `final_recommended_set.md`. That harness uses the same ledgers as conftest.

Ceilings that only fall, so their tests still pass:

- Curve reader: 128,381 -> 80,567 B. That is 11 B per cell against the pinned 18*cells.
- EchoMixed over numbers: 50,536 -> 20,449. That is 2 B per cell against the 6*N pin.
- EchoMixed over the mixed column: 72,213 -> 62,117.
- Holiday-calendar reader: 3,850 -> 1,763.
- FuturesSchedule.120 reader: 7,803 -> 7,341.
- Calendar 3,630 reader: 251,938 -> 247,612.
- MarketHistory 3,630 reader: 634,944 -> 616,568.
- EchoDates 10k: 251,256 -> 171,192.
