# market-history group: verification notes

Worktree: `worktrees/wf_0d4f8983-1f8-3` (branch `worktree-wf_0d4f8983-1f8-3`, from main 40fab53, PR #118).
Python: `<repo>/.venv/bin/python` (3.13.12, numpy 2.5.2), with `PYTHONPATH=<tree>/src` (and `:<tree>` where the unit-test helpers are imported).

## Commits left in the worktree (oldest first)

| commit | what | state |
|---|---|---|
| dd32929 | history-dated-binders-slices-and-count | **kept (recommend)** |
| d136dc3 | history-gas-daily-scalars | measured, reverted by ad00b7c (reject) |
| 0961572 | history-iferc-permutation | **kept (recommend)** |
| 63f473c | history-iferc-rows-once option A (np.fromiter) | measured, reverted by 0746260 (marginal) |
| 27279ab | history-iferc-rows-once option B (rows on IfercFixings) | measured, reverted by c4aeb00 (design fork) |

The final tree is main plus dd32929 and 0961572 (only `src/goosedove/market/market_history.py` changes).

## Verdicts

1. **history-dated-binders-slices-and-count: recommend.** Uses v3 of the proposal, the plain count, because the closed-day invariant is established upstream. `futures_fixings.py:70-75` refuses any date that is not a business day under `np.busdaycalendar(holidays=index.holiday_calendar.holiday)`. `calendar.py:121` prices with `np.is_busday(dates, holidays=<same list>)`. `market_history.py:71` requires the two to share one index object. The unit property `test_no_fixing_over_the_calendars_index_falls_on_a_day_it_closes` pins this. Gas Daily prices every day (`calendar.py:169`). The fixings' dates strictly increase (`futures_fixings.py:63-68`; Gas Daily is consecutive, `gas_daily_fixings.py:52-60`). The calendar's days are consecutive (`calendar.py:119/167` use `np.arange`). `is_fixed` is the prefix of length `first_unfixed` (`calendar.py:122/170`, counted at 232). The late rule therefore makes every row fixed.
   - Two refinements over the proposals, both there to keep exact equivalence on inputs that only a Python caller can make:
     - The late rule tests the last date with one scalar comparison and searches only on failure. A comparison with NaT is False, as the old mask's was. An unconditional `searchsorted` would sort NaT last and would refuse a single NaT Gas Daily print that the old code passed.
     - `_every_fixed_day` keeps `if missing.any()` on the slow path. With a NaT valuation date, `first_unfixed` is 0 but the late rule passes everything. The old code then returns a history whose rows are unfixed days. Without the guard the new code would refuse it and name `dates[0]`.
   - These inputs are unreachable through the seam. `bridge._date` makes every date from a whole serial in range, and `ValuationDate` comes from `_CreateValuationDate`. They are still equal now.
2. **history-gas-daily-scalars: reject.** It breaks tenet 3 "One path" (golden rule 5): after candidate 1 the dated binders share one general path (`_inside` + `_every_fixed_day`), and this re-implements the coverage rule and the naming of the first missing day for Gas Daily alone with scalar arithmetic. Its incremental counts over candidate 1 are within noise at the pinned size: peak 4,770 -> 4,514 B at 12 months, time flat. The numpy ledger only trades `searchsorted 2 + view 1` for `numpy.arange 1 + generic.astype 1`. It is also not exactly equivalent on a NaT valuation date (unreachable): the old code returns 9 rows and this raises `fixings has no fixing for 2026-09-10`. What it does save is real but narrow: about 8 us at 3,652 all-fixed days, about 22 us at 10,950, and on the failure path O(1) naming (44,512 -> 1,987 B).
3. **history-iferc-permutation: recommend.** Exact. It relies on each code being given once and being a month of the index (`iferc_fixings.py:59-70`, the strike-off set) and on `is_fixed` being the prefix (`calendar.py:190-200,232`). The unfixed rule establishes `rows < first_unfixed` in the same function before the count relies on it. The result is bit-identical: `argsort` of a permutation has no ties, so `rows[order]` is `arange` and `prices[order]` equals the scatter.
4. **history-iferc-rows-once.** Option A (`np.fromiter`) is marginal: exact, about 10 to 17% faster whole-call at 120 and 1,200 months, consistent across sizes. Its peak is unchanged (6,488 / 81,516 B, because the dict dominates), and its only ledger change is `numpy.array -> numpy.fromiter`, so no count moves. Option B (rows held on `IfercFixings`) is a design fork: it adds a field to a record. The history drops from 6,488 to 2,373 B and from 32 to 12 us at 120 months, and from 81,516 to 19,653 B and from 228 to 17 us at 1,200. `_CreateIfercFixings` pays for it: +81% time (18.7 -> 33.8 us at 120, 158 -> 285 us at 1,200), and peak 10,600 -> 6,560 B at 120 but 42,888 -> 81,932 B at 1,200. Its pin `test_iferc_fixings_are_two_columns_...` moves (`numpy.array` 1 -> 2, `ndarray.setflags` 1 -> 2).

## Files

- `show_group.py`: prints this group's candidates from `find/groups.json`.
- `equiv_runner.py` + `equiv.py`: exact equivalence, as-is against the worktree, in fresh processes.
  - 9,093 seeded cases: 3,000 random each for futures, Gas Daily and IFERC; 20 each at 3,630 days, 36,000 days, 120 Gas Daily months and 120 IFERC months; 5 at 1,200 IFERC months.
  - Edge cases: a 26,000-row futures series against a 360-day calendar, a 26,000-print series against 365 days, a single NaT print under four valuation dates, and NaT valuation dates for both dated kinds.
  - Prices include NaN, +/-inf, +/-0.0, +/-5e-324 and 1e308.
  - Warnings are raised as errors.
  - Compared: rows and prices as raw bytes, dtype, shape, C-contiguity, writeable flag, memory sharing with the fixings, and the exception type and message.
  - `equiv_detail.py` lists the named cases. Outputs: `equiv_c1.txt`, `equiv_c2.txt` (the one difference), `equiv_c3.txt`, `equiv_c4a.txt`, `equiv_c4b.txt`, `equiv_final.txt`, `equiv_final_detail.txt`.
- `props.py`: the repo's four hypothesis properties for the history, at 1,500 examples each, with warnings as errors (`props_final.txt`).
- `pins.py`: the budget pins as tests/performance measures them (`call_profile`, `numpy_calls`, `least_peak`). Outputs: `pins_asis.txt`, `pins_c1.txt` (taken before the late rule became a scalar compare, so it shows 3 searchsorted), `pins_c2.txt`, `pins_c3.txt`, `pins_c4a.txt`, `pins_final.txt`.
- `micro.py` + `micro_compare.py`: the builder alone (`market_history`), min of 7 timeit repeats and the least tracemalloc peak. Outputs: `micro_c1.md`, `micro_c2_vs_c1.md`, `micro_c2_vs_asis.md`, `micro_c3.md`, `micro_c4a_vs_c3.md`, `micro_c4b_vs_c4a.md`.
- `bench_harness.py` and `bench_compare.py`: copies of the shared ones, adding the `history.*` scenarios (long series, all fixed, 36,000 days, shuffled IFERC, and five failure paths). Outputs: `history-dated-binders-slices-and-count.md`, `history-gas-daily-scalars.md`, `history-gas-daily-scalars.vs-c1.md`, `history-iferc-permutation.md`, `history-iferc-rows-once.optionA-vs-c3.md`, `history-iferc-rows-once.optionB-vs-A.md`, `final_combined.md`.
- `trees/c1`, `trees/c3`, `trees/c4a`: src+tests snapshots at those commits, used as the "as-is" side for incremental comparisons.
- `*.diff`: `git show` of each candidate commit.

## Final state (dd32929 + 0961572)

- ruff check: clean. ruff format --check: 78 files already formatted.
- pyright: run with `--pythonpath <repo>/.venv/bin/python`, because the worktree has no `.venv`; without it numpy does not resolve and 520 import errors appear. Result: 0 errors, 0 warnings.
- Unit tests: 1271 passed.
- Performance tests: 3 failed, 100 passed. The failing pins:
  - `test_a_market_history_is_two_handles_in_and_the_calendar_kept` and `test_a_gas_daily_history_is_two_handles_in_and_the_calendar_kept`:
    - call ledger adds `_inside: 1`.
    - numpy ledger moves from `{any 2, astype 1, zeros 1, setflags 2, ufunc.reduce 2}` to `{ndarray.copy 1, ndarray.searchsorted 2, ndarray.setflags 2, ndarray.view 1}`.
    - the line `"ndarray.searchsorted" not in calls` must be reworded: these are two scalar placements over the fixings, and nothing of the calendar is rebuilt.
  - `test_an_iferc_history_is_two_handles_in_and_the_calendar_kept`:
    - numpy ledger moves from `{numpy.array 1, any 2, zeros 1, argsort 1, setflags 2, ufunc.reduce 2}` to `{numpy.array 1, ndarray.max 1, ufunc.reduce 1, numpy.arange 1, numpy.empty 1, ndarray.setflags 2}`.
    - `"numpy.arange" not in calls` must be reworded: the arange is the fixed rows, not the calendar.
- Allocation ceilings all still pass, and could be tightened:

  | history | peak before -> after | ceiling |
  |---|---|---|
  | futures, 360 days | 3,520 -> 1,756 B | 4,208 |
  | futures, 3,630 days | 16,600 -> 1,756 B | none |
  | Gas Daily, 365 days | 7,404 -> 4,780 B | 12,998 |
  | IFERC, 120 months | 11,520 -> 6,520 B | 14,048 |

  The futures history's peak no longer grows with the calendar.
