# bridge-in: verification notes

Worktree: worktrees/wf_1c4545af-6ae-1 (branch worktree-wf_1c4545af-6ae-1, base 40fab53 = main at #118).
Python: <repo>/.venv/bin/python (3.13.12, numpy 2.5.2), PYTHONPATH=<tree>/src.

## Commits (in order)

| commit | candidate | verdict | state |
|---|---|---|---|
| 633e7de | bridge-date-column-in | recommend (parked item, re-measured) | kept |
| 9bfda53 | bridge-table-text-column | recommend | kept |
| d028e5a | bridge-scalar-date-in | recommend (parked item, re-measured) | kept |
| cfc8e06 | bridge-kind-column-looks-as-reductions | recommend (small) | kept |
| bf4f68d | bridge-one-cell-empty-not-nested-list | marginal | reverted by 7ca9f84 |
| 4bf7297 | bridge-cell-item-instead-of-flat | marginal | reverted by fd80f18 |
| f5c0c05 | bridge-mixed-empty-text-index-already-known | reject | reverted by 319e46a |
| (none) | bridge-cells-from-buffers-note | marginal (note only) | measured in buffers_note.py |

`candidate_diffs.patch` holds `git show` of every candidate commit.

## Tools in this directory

- `eqlib.py CASES.py --proposed WT/src`: runs a case file in fresh processes under the as-is tree
  (<repo>/src) and the proposed tree and compares every outcome bit for bit (array
  bytes, dtype, shape, C/F flags, writeable; exception type, message, cell/value/expected/reason),
  with warnings as errors.
  Case files: `cases_dates.py` (394), `cases_random.py` (6,672 seeded random date ranges and
  tables over 17 schemas), `cases_tables.py` (713), `cases_scalars.py` (381), `cases_mixed.py`
  (3,190). Outputs: `eq_*.txt`.
- `micro.py MICRO.py --asis A/src --proposed B/src`: least-of-7 timeit, tracemalloc peak and numpy
  ledger of isolated operations, sides alternating in fresh processes. Case files `micro_dates.py`,
  `micro_tables.py`, `micro_scalars.py`, `micro_mixed.py`; outputs `micro_*.md`.
- `pinprobe.py WT`: copies tests/performance, makes the ledger fixtures record instead of fail,
  runs it, prints every ledger pin's before -> after. Outputs `pins_c1.txt` ... `pins_final.txt`
  (cumulative; diff consecutive files for one candidate's moves).
- `kind_look_variants.py`, `exhaustive_scalar_date.py`, `buffers_note.py`: one-question scripts.
- `trees/`: exported source trees (main + one candidate, or a candidate and its parent) used as
  bench sides so each candidate is measured alone.
- bench_compare tables: `bridge-date-column-in.md`, `bridge-table-text-column.md`,
  `bridge-scalar-date-in.md`, `bridge-kind-column-looks-as-reductions.md`,
  `bridge-cell-item-instead-of-flat.md`, `bridge-mixed-empty-text-index-already-known.md`,
  `combined_recommended.md` (the four kept, together, against main).

Noise: the box is shared; timing spreads were often 2x. Read only rows that moved consistently
across sizes and runs; counts (peak, ledgers) are deterministic.

## Findings in brief

1. Dates in (c1): success path is floor once, min/max/all reductions, then shift and cast in the
   floor's own buffer (copyto over 1-D flat views, no overlap copy). 17 -> 9 B/cell peak:
   FirstOfDates 10k 171,192 -> 90,449 B, 100 cells 2,892 -> 1,408 B; holiday calendar 100
   2,892 -> 2,208, 1,000 18,192 -> 16,608. Rejected range pays one more floor+min pass (peak
   unchanged, 90,352 -> 90,449; time ~+10-20 us at 10k, the 'reject' row moved up). The kinds
   mask OR-ed into a rejected date range is dropped: the host writes NaN for text/blank/missing
   (host/Goosedove.Host/AddIn.cs:417,430,436) and 1.0/0.0 for booleans (:423), as does
   Cells.from_rows via _classify, so the slots alone flag every non-number. A first variant that
   reused the floor in the rejection mask raised the rejected peak to 110,384 B and was dropped.
2. Table text column (c2): the slice texts[t::T]; with one text column it is the host tuple
   itself (identity verified). SumQuantity 2,500x4: 135,184 -> 43,940 B, ~330 -> ~100 us;
   contract specifications 120 rows: 122 -> 71 us. Equivalence over 713 + 4,000 random tables.
3. Scalar date (c3): np.datetime64(int + EPOCH_DAYS, 'D'). Exhaustively equal over all
   2,958,405 serials. _date 2.49 -> 0.71 us; _CreateValuationDate 6.7-7.3 -> 4.3-4.5 us, peak
   1,144 -> 272 B. No ledger moves.
4. Kind looks (c4): number column `kinds.max() != NUMBER_CODE` (new unit test pins number as the
   lowest code); text/boolean `min()/max()`; the mask only on failure. On top of c1-c3:
   SumQuantity peak 26,048 -> 23,548 B; +2 numpy calls per 4-column table. Proposal's
   `kinds.any()` measured worse in bytes (iterator buffer 907 B at 25 rows) and was not used.
5. One-cell (c5): 0.3-0.7 us per promoted scalar, peak -24..-64 B; no pin moves -> marginal.
6. _cell item (c6): failure path only, 0.3 us per named cell, whole rejected calls unchanged within
   noise; adds ndarray.item to the rejected-table numpy ledger -> marginal.
7. Mixed empty-text index (c7): the peak it aimed at did not move (103,372 -> 103,372 B: the peak is
   _bad_mixed's flatnonzero, not _cell's prefix mask); splits a deliberately uniform pin -> reject.
8. cells_from_buffers note (c8): current form is as fast as any; a fixed 2^40 ctypes type or
   PyMemoryView_FromMemory removes per-size type creation (first sight ~27 us per call vs ~6 warm
   at 2-3k cells) and ~1.5 MB RSS over 10,000 distinct sizes (tracemalloc sees only 18 KB of it);
   memoryview is slower warm. No pin moves -> marginal; the fixed type is borderline ambient state.

## Flake seen once

One run of tests/unit (c1+c2, while a benchmark and pinprobe ran concurrently) reported
1 failed / 1270 passed without -rf; 9 later runs on the same and later trees all passed
(1271/1272). Most hypothesis tests keep the default 200 ms deadline; load is the likely cause.
The failing test name was not captured.
