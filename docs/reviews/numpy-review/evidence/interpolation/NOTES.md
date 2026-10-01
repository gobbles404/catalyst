# Interpolation group: verification notes

Worktree: `worktrees/wf_9922a729-5fc-1` (branch `worktree-wf_9922a729-5fc-1`, base 40fab53 = main at #118).
Function: `interpolate_discount_factors` in `src/goosedove/globals/interpolation.py`, called once by `discount_curve` (`src/goosedove/globals/discount_curve.py` line 82) after the builder's checks.

Each candidate was committed alone, measured, then reverted, so every commit's diff is that candidate only. The last commit, cc24895, cherry-picks the one recommended candidate (interp-hold-as-reverse-cummax) back on. The tree at HEAD is main plus that candidate.

| commit | candidate | verdict |
|---|---|---|
| 6a6f47b (reverted by 3f3d8b6) | interp-gapless-table-is-copied-not-filled | design-fork |
| 172d613 (reverted by 79eb720), re-applied as cc24895 | interp-hold-as-reverse-cummax | recommend |
| a7ff09d (reverted by 48a1167) | interp-offsets-one-temporary | marginal |
| 90c6a61 (reverted by b35b974) | interp-counts-one-allocation (`.view` variant) | marginal (moot once cummax lands) |
| 607c8d7 (reverted by 7f2e670) | interp-day-grid-from-int64 | reject |
| 4e62034 (reverted by 92a7fce) | interp-hold-only-when-a-slope-underflows | reject |

## Scripts (all run with `<repo>/.venv/bin/python`)

- `equiv.py [--file X.py] [--draws N] [--sanity] [--show]`: as-is against proposed, in one process. It loads both module files under two names and compares values bit for bit (the int64 view, so -0.0 and +0.0 count as different), dtype, shape, C-contiguity, writeable, owndata, memory shared with the inputs, whether the inputs were changed, and the exception type and message. Warnings count as errors. The in-contract set has 25,037 or 50,037 cases: the unit tests' examples, the review's 1e-307 case, a constructed 3-ulp/5-day dip, one anchor, two anchors 1,048,573 days apart, daily and sparse anchors at 2 to 36,500 days, strided factors (the seam's `numeric_slots[:, 1]`) and read-only inputs, plus five random families (anchors, wide into subnormals, gapless, gapless-wide, neighbours a few ulp_min apart). The out-of-contract set has 42 cases: NaN, +/-inf, 0, -0.0, negative, rising, NaT first, middle and last, duplicate or decreasing dates, empty arrays and mismatched lengths. `--sanity` checks the as-is code against itself with the hold removed: it finds 72 mismatches in 2,037 cases, so the checker does catch a dip. Outputs are in `equiv_c*.txt`, `equiv_final.txt` and `equiv_sanity.txt`.
- `e2e.py`: run with PYTHONPATH set to either tree. It goes through the seam (`_CreateDiscountCurve`, then `util_ReadHandle`) and calls `discount_curve` from Python, and prints a digest per case. Diff `e2e_asis.txt` against `e2e_c*.txt`; only the first line, which names the tree, should differ.
- `micro.py [--file X.py]`: the bare function, timed with timeit (min of repeats), tracemalloc peak and numpy ledger, at daily 100 and 10,000, 12 anchors over 100 and 10,000 days, 1,000 anchors over 10,000 days, and 2 anchors over 1,048,574 days. Outputs are in `micro_c*.md`.
- `hold_micro.py`: the hold step alone, in all five forms the group proposed (asis, view, out, cummax, guard), each checked bit for bit. Output is in `hold_micro.md`.
- `steps_micro.py`: the offsets step and the grid step alone. Output is in `steps_micro.md`.
- `guard_brute.py`: 200,000 segments in four regimes (normal, the TINY boundary, deep subnormal, a few ulps over long gaps). It checks that a line never dipped below its right anchor while the guard stayed silent. Output is in `guard_brute.md`.
- `interp_slope_form.py`: shows that numpy 2.5.2's interp computes its slope as `(b-a)/d`, not `(b-a)*(1/d)`. It agreed with division on 5,071 of 5,071 cases where the two differ, in both branches. The guard's proof rests on this.
- `mismatch_builder.py`, `grid_base.py`: small probes of `discount_curve` from Python (factor count against date count, and the frozen dates' `.base`).
- `bench_harness.py` / `bench_compare.py`: copies of the shared harness with four more scenarios: `create.DiscountCurve.daily.365`, `daily.36500`, `anchors12.36500` and `anchors1200.36500`. The per-candidate tables are `interp-*.md`.

Timing on this box is very noisy. The as-is daily 3,631 median ran from 154 µs (noise_floor.md) to 274 µs across these runs, with spreads up to 2x inside a single run. Only counts (peak bytes, ledgers, passes) are firm evidence. The isolated hold timings in `hold_micro.md` are the cleanest clock evidence.

## Findings beyond the candidates

1. `discount_curve` does not check that it got one factor per date, and does not refuse NaT, when called from Python. The seam establishes both: one table body, and `bridge._as_days` from validated serials. The builder does not. Today a Python caller with mismatched lengths, or a NaT in the middle, gets a numpy message by accident ("fp and xp are not of the same length.", "repeats may not contain negative values."). Every candidate that removes `np.repeat` or skips `np.interp` loses that accidental refusal:
   - cummax and guard return a curve for a middle NaT.
   - The first version of the gapless copy returned a curve of 3 dates and 5 factors. I fixed it by also requiring `factors.size` in the condition.

   Nothing in Excel reaches this, and PRINCIPLES says nothing but Excel calls the Python, but it is out-of-contract behaviour that moves.
2. The seam passes `numeric_slots[:, j]`, a strided view, as `factors`. Every path here produces a fresh contiguous array, so nothing keeps a view of the seam's buffer.
3. Hypothesis health checks (`too_slow`) fail now and then under load in unrelated schedule tests (`test_futures_schedule`, `test_gas_daily_schedule`, `test_iferc_schedule`: `test_any_columns_with_one_row_per_code_are_kept_aligned`), on as-is and proposed alike. They pass when rerun alone with the same seed.
4. pyright run as `cd WT && pyright` reports 518 errors because the worktree has no `.venv`, so imports do not resolve. With `--pythonpath <repo>/.venv/bin/python` it reports 0 errors and 0 warnings on the final tree.

## Per candidate

### interp-gapless-table-is-copied-not-filled: design-fork
- Equivalence: 0 mismatches in 25,037 in-contract cases. Out of contract, one case moves: a NaT in the middle of an otherwise gapless column now builds a curve instead of numpy's "repeats may not contain negative values.". The length-mismatch case was fixed by the `factors.size` condition.
- Counts at daily 3,631 through the seam: peak 216,235 -> 99,435 B (59.6 -> 27.4 B/day). Ledger: astype 3->2, repeat 1->0, arange 2->1, asarray 2->1, copy 0->1. Passes over N in the interpolation: about five (grid, x-grid, interp, repeat, maximum) -> two (grid, copy). Daily 365: 23,541 -> 11,253. Daily 36,500: 2,155,506 -> 986,898. Anchor shapes are unchanged.
- Bare function: daily 10,000 at 416 -> 12.5 µs and 480,928 -> 160,352 B.
- Why a fork: it conflicts with golden-rules 5 / tenet 3 "One path ... no singleton branch". It also conflicts with the pin that says a daily table and a dozen anchors run the same functions and the same ledger. The owner accepted 216,443 "up from 129,027 when a daily table was copied rather than filled" in #70.

### interp-hold-as-reverse-cummax: recommend
- Equivalence: 0 mismatches in 50,037 in-contract cases, including about 10,000 neighbour draws where the hold changes values. Unit tests pass, and the interpolation and discount_curve hypothesis tests pass under 8 seeds. Out of contract it relies on the builder: finite factors (discount_curve.py line 49, `~np.isfinite`), non-increasing factors (line 60, `rises`), and strictly increasing dates (line 71, `unordered`). Out-of-contract inputs therefore give different numbers, and a middle NaT, which the builder does not refuse but the seam never sends, now builds a curve.
- Counts: the hold step goes from 8N + 24M bytes of temporaries (240,480 B at daily 10,000; 29,720 B at 12 anchors over 3,631 days) to 448 B. Passes over N in the hold go from 2 (repeat write, maximum read 2 and write 1) to 1 (accumulate). The whole-call peak moves only 216,235 -> 215,907 (daily 3,631) and 89,570 -> 89,242 (12 anchors), because the peak is inside np.interp, so no allocation ceiling moves. Ledger: astype 3->2, repeat 1->0, accumulate 0->1.
- Clock (hold alone, `hold_micro.md`): daily 3,631 36.2 -> 14.8 µs; daily 10,000 92 -> 39; 12 anchors over 3,631 days 10.7 -> 14.4; 12 anchors over 10,000 days 14.6 -> 37.8; 2 anchors over 1,048,574 days 2.5 -> 4.2 ms. The accumulate is a sequential scan, so it costs per day whatever the anchors are. It is faster for daily tables and slower for sparse anchors at long spans: +4 µs on a call of about 150 µs at the pinned dozen-anchor case.
- Pins that move: `CURVE_NUMPY` in tests/performance/test_seam_budgets.py, which fails both curve ledger tests. New value: `{"ndarray.any": 5, "ndarray.astype": 2, "ndarray.setflags": 2, "numpy.arange": 2, "numpy.asarray": 2, "ufunc.accumulate": 1, "ufunc.reduce": 5}`. Two comments become stale: test_seam_budgets.py:594, and test_seam_allocation.py:173/185 ("the anchor(s) each day runs to").

### interp-offsets-one-temporary: marginal
- Equivalence: 0 mismatches in 25,037 cases, and 0 out of contract.
- The offsets step alone: 10,000 anchors 160,776 -> 80,224 B and 38.7 -> 8.8 µs; 100 anchors 2,376 -> 1,024 B. The whole-call peak is unchanged at every size. The ledger grows by two: astype 3->4, view 0->1.
- No pin's count goes down, and the ledger goes up.

### interp-counts-one-allocation: marginal (moot under cummax)
- I used the `.view(np.int64)` variant. Equivalence: 0 mismatches.
- Ledger: astype 3->2, view 0->1. The whole-call peak goes up by 16 B (the view's header). Hold-step peak is unchanged (240,480 B at daily 10,000), because the repeat buffer sets that peak, not the counts. Time is within noise.
- Cummax deletes these lines entirely.

### interp-day-grid-from-int64: reject
- Values are equal, but the curve's frozen `dates` change from an owned array to a view whose `.base` is a writeable int64 array (`grid_base.py`). That loosens copy-then-freeze. A NaT at the first or last date now raises RuntimeWarning "overflow encountered in scalar subtract" (an error under filterwarnings=error) instead of numpy's ValueError. Ledger view 0->2, peak +224 B. It saves 0.7 to 1.7 µs.

### interp-hold-only-when-a-slope-underflows: reject
- It is exact. There were 0 mismatches in 50,037 cases. In `guard_brute.py`, 11,120 of 200,000 segments dipped and the guard fired on every one. numpy's slope is division (`interp_slope_form.py`), so the proof holds. Duplicate dates (out of contract) now raise "divide by zero" RuntimeWarning, and a middle NaT now builds a curve.
- The finding said the guard costs about what the hold costs. On this box it costs less: hold alone 6.0 vs 14.6 µs at 12 anchors over 10,000 days, and 6.8 µs vs 2.5 ms at 2 anchors over 1,048,574 days. It is slower only at 100 days (12.7 vs 7.6 µs daily).
- Rejected under golden-rules 5 / tenet 3 "One path". It gives two paths and two ledgers depending on the data (any +1, reduce +1, and repeat/astype only near underflow). Cummax gets the counts on one path. If the owner wants the clock rather than the counts, this is the alternative to weigh. The decision belongs to the owner.
