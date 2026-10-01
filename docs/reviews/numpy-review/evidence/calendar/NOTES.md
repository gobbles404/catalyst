# Group 'calendar': verification notes

Worktree: worktrees/wf_0d4f8983-1f8-1 (branch worktree-wf_0d4f8983-1f8-1, from main 40fab53, PR #118).

Commits, in order (each candidate isolated; non-recommended ones reverted with `git revert`):

| commit | candidate | verdict | state |
|---|---|---|---|
| 5c008b2 | calendar-contract-by-repeat | recommend | kept |
| 1031f7c / 198b26e | calendar-fixed-prefix-by-search | reject | reverted |
| bc31823 / 4b19d6c | calendar-datetime64-loops-int64-views | reject | reverted |
| d53f603 / 447c0ad | calendar-iferc-dates-by-reference | design-fork | reverted |

Final tree == 5c008b2 (`git diff 5c008b2 HEAD` is empty). On it: ruff check clean, ruff format clean (78 files),
pyright (strict, `--pythonpath <repo>/.venv/bin/python`) 0 errors 0 warnings, tests/unit 1271 passed,
tests/performance 103 passed.

## Files

- `eq_runner.py` / `eq_compare.py` - calendar equivalence: 868 schedules x 11 valuation days = 9,548 calls on the
  as-is tree and a proposed tree in fresh processes; compares column bytes, dtype, shape, C-contiguity, writeable,
  first_unfixed (and its type), the sources kept by reference, identity of dates with the schedule column, or the
  exception type and message. Warnings are errors. Run: `python eq_compare.py <tree> <tag>`. Outputs `eq_<tag>.txt`.
- `eq_views_runner.py` / `eq_views_compare.py` - the non-calendar sites of the int64-views candidate (discount_curve,
  futures_fixings, futures and Gas Daily histories), 248 calls. Output `eqv_int64views.txt`.
- `hyp_equiv.py` - hypothesis property, as-is calendar module (loaded from <repo>/src by file) vs the
  proposed one, 3,000 examples per kind over the seam's whole day range (1900-01-01..9999-12-31), rule-breaking
  schedules included. Outputs `hyp_repeat.txt`, `hyp_prefix.txt`.
- `micro.py` -> `micro.md` - isolated operations, timeit min-of-7 and tracemalloc peak, at 100/360/10,000/36,000.
- `peaks.py` - the allocation tests' own `least_peak` over the calendar creators at three sizes per kind.
- `<id>.md` - bench_compare tables; `<id>.diff` - `git show` of each candidate commit.
- `trees/after-repeat`, `trees/prefix` - `git archive` exports used as the as-is side to isolate stacked candidates.

## calendar-contract-by-repeat: recommend

`np.searchsorted(expiries, dates)` / `np.searchsorted(last, dates)` -> `np.repeat(np.arange(1, M), gaps)` /
`np.repeat(np.arange(M), lengths + 1)`. The repeat counts are written inline so the M-length temporaries die before
the flags are made: with a named `spans` local the peak rose +448 B (13 contracts) .. +10,112 B (1,221); inline it is
+16 B at 360 days and 0 at 3,630 and 36,630 (least_peak: 8,620->8,636; 66,200->66,200; 661,300->661,300; gas
7,953->7,969, 67,335->67,351). The invariants it needs are established upstream in the same function: gaps >= 1 by
the order rule (calendar.py 106-112), lengths >= 1 by the backwards rule (147-153), the lengths laid end to end by the
gap rule (155-161), and the sum equals dates.size because dates is the arange of the same ends.

Equivalence: 9,548 calls, 9,526 identical; hypothesis 3,000 x 3 identical. The 22 differences are one Python-only
input: a NaT in the middle of future_expiry (fut.nat.1, fut.nat.6). The order rule does not see NaT (NaT compares
False), so today searchsorted runs over an unsorted array and silently returns a wrong calendar (row 1 gets 0 days,
row 2 gets 60); the proposal raises numpy's `ValueError: repeats may not contain negative values.` The seam cannot send
NaT: bridge.py `_date` (405-411) and `_dates`/`_not_dates` (427-449) accept only whole serials in
[FIRST_SERIAL, LAST_SERIAL]. A NaT at either end raises numpy's arange message in both trees.

Counts: numpy ledger futures and Gas Daily calendars `ndarray.searchsorted 1 -> 0`, `numpy.arange 1 -> 2`,
`ndarray.view 0 -> 1`, `ndarray.repeat 0 -> 1` (net +2 C calls, each O(M)). Passes over the N days: one either way,
but each day costs one store instead of a binary search of log2(M) compares (4 at 13 contracts, 7 at 121, 10 at 1,221).
Clock (whole call, 5 rounds, noisy box): futures 3,630 days 147.8 -> 101.5 us (-31%, moved), 36,000 945.9 -> 676.3
(-29%), gas 120 months 103.0 -> 58.6 (-43%, moved); 360 days and 12 months flat (+1%, +3%). Isolated: 10k days
142.6/195.2 -> 9.4/10.7 us; 36k days 1,038/637 -> 18 us; but at 90 days slower (1.9 -> 4.6 us).

## calendar-fixed-prefix-by-search: reject

Equivalent on every seam-reachable input (hypothesis 3,000 x 3 identical; a seconds-unit valuation day also matched),
but not on two Python-built inputs, where it changes a number silently: a NaT valuation day (as-is: nothing fixed,
first_unfixed 0; proposed: everything fixed, first_unfixed = size; 828 calls), and a NaT publication day in an IFERC
schedule (the order rule does not catch it; 10 calls). The invariant 'as_of is a real day and the dates are sorted' is
established only at the seam, not by `valuation_date` or `iferc_schedule`. And the saving does not show: whole call
within noise at every size (-6%..+8%), peak -231 B, numpy ledger +2 calls in all three calendar ledgers
(`ndarray.searchsorted 0 -> 1`, `numpy.zeros 0 -> 1`). Isolated it removes one of two passes over N (13.3 -> 2.8 us at
10k days) but is a wash at 360 days (2.09/2.49 -> 1.92/2.45) and slower at 100 (+12..17%).

## calendar-datetime64-loops-int64-views: reject

Slower at the working size: isolated is_fixed 1.43 -> 3.05 us at 360 days (+114%), 1.23 -> 2.85 at 100 (the scalar
conversion costs more than the loop); faster only at 10k+ (12.95 -> 6.46, 41.6 -> 14.2). Whole call: no scenario moved;
calendar iferc 120m +22%, 1200m +15%, gas 12m +14%, futures 360 +10% (noise-level but all one way at the small sizes);
FuturesFixings 26,000 -16% (not moved). Peak bytes up +47..+112 B on 13 of 17 scenarios; numpy ledgers +1..+3 calls
(`ndarray.view`, `generic.astype`), the histories trade `ndarray.astype` for `generic.astype` + `ndarray.view`.
Not equivalent on Python-only inputs: a datetime64[s] valuation day is compared as seconds against day counts, so every
day is fixed (848 calendar calls differ, 30 of them IFERC schedules with a NaT publication day; 8 history calls then fail
with 'fixings has no fixing for ...'); NaT in an order check now raises the library's own order message instead of
numpy's arange/repeat/isoformat error or a silent wrong calendar (44 calendar calls, 20 curve and fixings calls). All
seam-reachable cases identical (curve, fixings, histories, calendars). The history-offset half alone is a real time win
at 10k+ fixings (55 -> 30 us, 134 -> 70 us) with no peak change; it could be proposed separately if the owner wants it.

## calendar-iferc-dates-by-reference: design-fork

Drops the IFERC calendar's copy of the schedule's frozen publication days. Values, dtype, shape, flags identical on
all 2,277 successful IFERC calls; the only difference is identity (`calendar.dates is schedule.publication_date`).
Unit test `test_every_iferc_month_is_one_row_dated_by_its_publication_day` fails on its `is not` assertion, which pins
the documented ownership decision ('copied so the calendar owns them'): the owner's call. Saving: one `numpy.array`
call and 8 B per month retained per live calendar (1,216 B at 120 months, 9,856 at 1,200, 80,256 at 10,000); peak
unchanged (10,504 / 41,224: the codes' set dominates); clock within noise (-4%, -11%).

## Incidental

- `tests/unit/test_contract_specifications.py::test_any_distinct_names_and_their_columns_are_kept_aligned` failed
  once under load (load average 7) and passed on rerun; it has hypothesis's default 200 ms deadline and does not touch
  the calendar. Not a candidate defect.
- pyright must be run with `--pythonpath <repo>/.venv/bin/python` in a worktree (no .venv there);
  without it it reports 518 unresolved-import errors.
