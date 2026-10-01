# utilities group: verification notes

Worktree: worktrees/wf_1c4545af-6ae-4 (base 40fab53, PR #118).
Commits, in order: bb8585b (c1 codes-array), accc3f6 (c2 fill-once), 9e284e3 (c3 market-live-rows),
7001e1e (c4 doubled-rectangle, design fork), b6115d2 (revert c4), 37ac3e3 (revert c3).
The final tree is as-is plus c1 and c2 only (`git diff 40fab53`: utilities.py, +17 -12).

## Verdicts

| id | verdict | why |
|---|---|---|
| utilities-priced-column-codes-array | recommend | identical output; the codes fill is 2.2x faster at 3,630+ rows (micro_codes.out); the table alone is 9-15% faster at 360-3,630 days, and at 3,630 days the two sides' spreads do not overlap; the `on + 2` temporaries go (IFERC readers' peak -832/-864 B). Costs +1 `numpy.array` on the ledger (2->3) and +192 B peak elsewhere |
| utilities-priced-column-fill-once | recommend (ride-along) | identical; `numpy.asarray` 2->1; one 32 B/row write pass fewer. Time and peak are within noise and unchanged |
| utilities-market-live-rows | marginal (reverted) | identical, and the invariant holds (calendar.py:119/122, 167/170, 190/197/200, 232). The operation is 12-45% faster, but no pinned count moves: the ledger and the peak are the same, and the whole call is within noise |
| utilities-priced-column-doubled-rectangle | design-fork (reverted) | identical; table peak -28 B/row (-10,352 B at 360 days, -1,008,272 B at 36,000); `numpy.empty` 7->5 / 6->4; `calendar_table` and `MixedArray.shape` leave the package ledger. It needs a seam signature change (`spare=`), a builder record that is not a valid result until the caller fills it in, and the calendar headings spelled twice. +56 B on every other table reader |

## Files
- equiv_dump.py / equiv_compare.py: the equivalence check, 1,250 library cases plus 4 seam cases on each tree, run in fresh processes. Output: equiv_c1.out, equiv_c2.out, equiv_c3.out, equiv_c4.out (each cumulative against as-is) and equiv_final.out.
- run_property.py (+ .out): the repo's two hypothesis properties for the market reader, 2,000 examples each, on the worktree with c1-c3.
- micro_codes.py, micro_slots.py, micro_live.py (+ .out): the isolated operations, timeit min-of-repeats and tracemalloc.
- micro_reader.py: shown(obj) alone, A/B in fresh processes over 5 rounds. Reports: micro_reader_c1.md (as-is vs c1), _c2_isolated.md (c1 vs c2), _c3_isolated.md (c2 vs c3), _c4_isolated.md (c3 vs c4), _final.md (as-is vs c1+c2).
- bench_harness.py / bench_compare.py: copies of the shared harness, adding read.MarketHistory.futures.36000, read.Market.futures.36000 and read.Market.gasdaily.12m. Tables: utilities-*.md (each candidate against the tree before it) and final_recommended_vs_asis.md.
- pin_values.py (+ pin_values_*.out): the values the history and market reader pins measure on each tree.
- trees/after_c{1,2,3,4}: `git archive` exports of the intermediate trees, used as the "as-is" side for the isolated A/Bs.
- diff_c{1..4}.patch: `git show` of each candidate commit.

## Pins on the final tree (c1+c2)
Four budget pins fail, all in tests/performance/test_seam_budgets.py, and all on the numpy ledger only:
- test_reading_a_market_history_back_rebuilds_nothing: numpy.array 2 -> 3, numpy.asarray 2 -> 1
- test_reading_a_market_back_rebuilds_nothing[a futures market / a Gas Daily market / an IFERC market]: numpy.array 2 -> 3, numpy.asarray 2 -> 1

The allocation pins all pass. Their new measured values (as-is -> final): history at 360 days 53,627 -> 53,819; futures market 50,931 -> 51,123; Gas Daily market 48,610 -> 48,802; IFERC market 20,163 -> 19,331. The ceilings are unchanged (56,048 / 56,048 / 56,798 / 23,048).

## Caveats
- Time on this box is noisy, and whole-call spreads overlap on most rows. The counts are the evidence.
- The c1 ledger count of `numpy.array: 2 -> 3` stands on its own. The reviewer's "stays 2" assumed bridge-out's table-text-gather lands too.
- pyright has to be run with `--pythonpath <repo>/.venv/bin/python` in the worktree. Without it, it cannot see numpy and the other packages and reports 518 spurious errors.
