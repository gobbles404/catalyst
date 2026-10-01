# bridge-out-b: verification notes

Worktree: `worktrees/wf_1c4545af-6ae-3`, branched from main at 40fab53 (#118).
Python is the repo venv's (3.13.12), numpy 2.5.2. Every script here runs with
`PYTHONPATH=<WT>/src <repo>/.venv/bin/python -W error <script>` from this directory;
`common.py` loads the as-is `bridge.py` (from <repo>/src) under another module name
beside the worktree's, so the two can be called side by side.

## Commits in the worktree

| commit | candidate | verdict |
|---|---|---|
| acedcbf | bridge-date-out-scalar-int | recommend |
| 8a41093 | bridge-finite-reductions | reject (reverted by 5de3e0a) |
| cacc690 | bridge-beyond-exact-reductions | recommend |
| 1c593a6 | bridge-table-empty-not-full | recommend (small) |
| 5de3e0a | Revert of 8a41093 | |

The per-candidate diffs are `diff_<id>.txt` (git show of each commit).

## 1. bridge-date-out-scalar-int: recommend

`_date_out` no longer builds a one-cell array and runs `_serials` over it. One scalar subtraction,
`day - EXCEL_EPOCH`, and its int64 view give the serial; NaT minus anything stays NaT (the int64
minimum, which no difference of two days can be, since the epoch is -25,569 and no day is below
min+1); a day count too large for the subtraction raises numpy's own OverflowError, as the column
path does.

I committed this form, not the reviewer's (`int(day.view(np.int64)) - EPOCH_DAYS` in Python ints),
because the reviewer's form changes a failure message. On the top 25,568 day counts (from
int64 max - 25,568 upward) as-is raises `OverflowError: Overflow in datetime64 - datetime64
subtraction`, and the column rule still raises it, while the reviewer's form says `result is a
date outside ...` (micro_date_out.py prints all three). The committed form keeps that message.
The reviewer's form is about 1.6 us faster again (1.5 against 3.1 us) and would suit only if the
owner wants the overflow named as a date outside the calendar, and then in the column rule too.

- Equivalence: eq_date_out.py, 2,064 inputs, 0 differ (eq_date_out.txt). eq_hypothesis.py `date_out`: 3,000 int64 day counts, the overflowing top included.
- Micro (micro_date_out.txt): 11.6 -> 3.1 us per call; peak 1,185 -> 952 B; numpy ledger {ndarray.any: 2, numpy.array: 1, numpy.datetime_data: 1, ufunc.reduce: 2} -> {generic.view: 1, numpy.datetime_data: 1}.
- Whole call (bridge-date-out-scalar-int.md, a probe added to my harness copy, since no repo probe returns a Date): out.Date.const 12.92 -> 4.25 us (-67%, moved), out.Date.echo 16.83 -> 6.67 us (-60%, moved); package ledger loses `_serials: 1`.
- Pins: none move, because no budget test returns a Date. history.md's open item "The scalar date path" covers the way in (3.27 us) and the round trip (11.14 us). This candidate is the way-out half and leaves the way in alone. A budget pin for a scalar date out would be worth adding with it.

## 2. bridge-finite-reductions: reject (slower, more numpy calls)

`min()` and `max()` in place of `isfinite` + `all()`: the values are exactly equivalent
(eq_finite.py, 1,309 rule calls including NaN, +-inf, subnormals, -0.0, extremes, F-order,
strided, read-only, big-endian, every integer dtype; 0 differ). The finite mask goes, so peak
falls by N bytes (EchoColumn 10k 10,385 -> 320 B). But the work is not less. Two 8-byte read passes replace one
8-byte read, a 1-byte write and a 1-byte read (16N bytes touched instead of 10N), and the numpy
ledger gains a call (all: 1 -> min: 1, max: 1; ufunc.reduce +1). The failure path pays the
reductions and then the mask.
- Micro (micro_finite.txt): 100: 2.59 -> 2.90 us (+12%); 10k: 5.65 -> 6.60 (+17%); 100k: 37.5 -> 33.7 (-10%). With a NaN in the middle: +6%, +32%, +56%.
- Whole call (bridge-finite-reductions.md): slower at every size, +4% to +31% on best medians (EchoColumn 10k +18%, FloatColumn 10k +31%, Grid 10k +21%, FloatColumn 100k +19%). Both reviewers measured it slower too.
- Pins that would move: four ledgers (test_a_column_out_copies_nothing, test_a_row_out_costs_what_a_column_out_costs, test_one_answer_per_row_itemized, test_an_array_out_from_nothing_in_itemized), each `ndarray.all: 1` -> `ndarray.max: 1, ndarray.min: 1` with `ufunc.reduce` +1. The allocation ceilings (N + SLACK, 9N + SLACK) still pass and could tighten to SLACK and 8N + SLACK.

## 3. bridge-beyond-exact-reductions: recommend

`_beyond_exact` now answers yes or no from `max()` and `min()` compared as Python ints, which are
exact for every int64 and uint64 and need no NEP 50 out-of-range comparison. `_first_beyond_exact`
builds the two masks only to name the cell. `_beyond_exact` keeps its name, so the package ledger
still reads `_beyond_exact: 2` on the index reader.

The `array.size > 0` guard is needed, not a re-check. `_finite` refuses an empty array before it
gets here, but `MixedArray.table` -> `_table_column` does not: a table whose body has no rows
reaches it with an empty int column (eq_table.py "zero rows int"), and `max()` of an empty array
raises ValueError.
- Equivalence: eq_finite.py (the int paths through _column_out/_row_out/_array_out: int64/uint64 edges at 2^53, 2^53+1, int64 min/max, uint64 2^63 and 2^64-1, i8/u8/i32, bad cell first/middle/last, F-order) and eq_table.py (477 tables, int columns of every width at every position, zero rows): 0 differ. eq_hypothesis.py `int_column_out` and `table`.
- Micro (micro_beyond.txt), the look alone on int64: 1 cell 3.79 -> 1.63 us; 100: 4.17 -> 1.94; 10k: 11.86 -> 4.51; 100k: 89.2 -> 27.6 us. Peak 30,288 -> 128 B at 10k (3 masks of N bytes gone). Four passes become two, and three allocations become none.
- Whole call (bridge-beyond-exact-reductions.md): IntColumn 100 -26%, 10k -32%, 100k -21% (peak 100,481 -> 90,385 at 10k); read.Index -9%; tables with an int column -5 to -11%. The box was loaded during this run, so the spreads overlap and only the counts are firm.
- Pin that moves: test_reading_an_index_back_costs_one_row, numpy ledger `ndarray.any: 5 -> 3`, `ndarray.max: 2`, `ndarray.min: 2` (new), `ufunc.reduce: 5 -> 7`. Its comment becomes "the two counts' exactness looks, a max and a min each, then the mixed road's three".

## 4. bridge-table-empty-not-full: recommend (small)

With no text column, the slots are allocated by `np.empty` and only the heading rows are filled
with NaN, because `_table_column` writes every body slot of every non-text column: each of its
four returns is a full-length column, and any refusal raises before the slots are read. With a
text column, `np.full` stays, since one fill of the whole rectangle beats a strided fill per text
column (the reviewer's strided variant is timed in micro_table.py as "strided us"). The text
columns are gathered by a list comprehension up front, which 3.13 inlines. An earlier `any(genexpr)`
version added `MixedArray.table.<locals>.<genexpr>` to seven package ledgers, so I dropped it.
- Equivalence: eq_table.py, 477 tables (and eq_hypothesis.py `table`). Each case runs after poisoning the allocator with a freed array of 123456.75, so an unwritten slot would show up. I checked that the poison does land in the next np.empty of the same shape. Compared: kinds and slots byte for byte, texts, then what _mixed_out hands the host. 0 differ.
- Counts: one 8-byte write pass over the body is gone from tables of numbers, dates and booleans only. That is 58,144 B written down to 16 B for a 3,633-day curve, and 1,172,256 down to 32 at 36,632 x 4. The numpy ledger loses `numpy.asarray: 1`, np.full's own asarray of the NaN. Peak is unchanged for number tables and +32 B for tables with a text column, because the list of text columns is alive one column earlier.
- Time: the fill alone 2.86 -> 0.87 us at 3,634 x 2 and 41.9 -> 0.85 us at 36,633 x 4 (micro_table.txt). Whole calls (bridge-table-empty-not-full.md) are within noise. The pass is 2 to 40 us inside readers of 50 to 3,000 us, so the clock cannot read it.
- Pin that moves: test_a_reader_is_a_text_call_one_lookup_and_a_table_out (the curve reader), `numpy.asarray: 1` removed. Its comment "numpy.empty: 2 # the kinds, and the slots underneath numpy's full" becomes false and should read "the kinds, and the slots". Readers with a text column (index, calendar, market, history) are unchanged.

## Final state (1, 3 and 4 applied, 2 reverted)

- ruff check: all checks passed. ruff format --check: 78 files already formatted.
- pyright (strict): 0 errors, 0 warnings, run as `pyright --pythonpath <repo>/.venv/bin/python`. Without `--pythonpath`, the worktree has no venv and pyright reports unresolved imports.
- tests/unit: 1271 passed.
- tests/performance: 101 passed, 2 failed, both pins expected to move: test_a_reader_is_a_text_call_one_lookup_and_a_table_out (`numpy.asarray: 1` gone) and test_reading_an_index_back_costs_one_row (`ndarray.any 5 -> 3`, `ndarray.max 2`, `ndarray.min 2`, `ufunc.reduce 5 -> 7`).
- Combined whole-call table: combined.md.

## Files

- common.py: loads as-is and proposed side by side; outcome and value comparison.
- eq_date_out.py, eq_finite.py, eq_table.py, eq_hypothesis.py: equivalence (outputs in *.txt).
- micro_date_out.py, micro_finite.py, micro_beyond.py, micro_table.py: isolated timings, peaks, ledgers.
- bench/bench_harness.py, bench/bench_compare.py: a copy of the shared harness with out.* scenarios (a probe returning a Date, prebuilt float/int columns and grids, tables built by MixedArray.table inside the call) and probe.EchoColumn.100.
- <id>.md: bench_compare tables, each candidate alone against main (snapshots under snap/).
- run_tests.sh: unit and budget tests on the worktree with totals.

## Combined (combined.md, final tree against main, 5 rounds)

out.Date.const -69% (moved), out.Date.echo -60% (moved), out.IntColumn.100 -32% (moved), out.IntColumn.10k -32% (moved),
out.Table.int.100k -33% (moved); read.Index -16%, read.DiscountCurve.3631 -9%, out.Table.num4.10k -16%, all within spread;
the control probe.EchoColumn.10k -1%, its ledgers the same. Equivalence was rerun on the final tree: eq_*_final.txt and
eq_hypothesis.txt, 0 differ.

Note: cacc690's diff shows two lines of 8a41093 as trailing context, because it was committed on top of it. The revert
5de3e0a removes 8a41093 cleanly and leaves `_finite` with as-is's isfinite/all.
