# Fix: history-dated-binders-slices-and-count (group market-history)

Worktree worktrees/wf_0d4f8983-1f8-3, fix commit 0e739eb on top of 0746260.

Flaw (equivalence refuter): `_inside` returned `(fixing_dates[first:last] - start).view(np.intp)`, so
`MarketHistory.fixed_rows` was a view (OWNDATA False) over a writeable timedelta64[D] temporary that
`.base` exposed; writing through `.base` changed the "frozen" rows ([0..4] -> [99,1,2,3,4]).

Fix: `.astype(np.intp)` in place of `.view(np.intp)`: a copy over the inside run only, so the rows
own their data, are C-contiguous, have no base, and `_frozen` freezes them. Docstring sentence
"viewed as whole numbers" -> "copied as whole numbers so the record owns its rows".

Evidence (all under fixrun/):
- refuter run.py: 45 cases, fixed vs as-is identical on every field (bytes, dtype, shape, flags
  string, base-is-None for both columns; error type+message); all 29 successes OWNDATA, C-contig,
  frozen, base None. base.py: fixed and as-is both print owndata True base None; the unfixed
  candidate (HEAD~1) prints owndata False base (m8[D], writeable) and is mutated through .base.
- equiv.py with the runner extended by rows/prices owndata and base-is-None: 9093/9093 identical
  vs as-is; the same extended runner on the unfixed candidate (--quick) reports 260/993 differing.
- props.py: 4 hypothesis properties x 1500 examples pass.
- ruff check/format, pyright: clean. Unit tests: pass (exit 0).
- Budget tests: 3 fail, all pins that move with source (futures + Gas Daily: call_profile lacks
  `_inside: 1`; numpy ledger now {ndarray.astype 1, ndarray.copy 1, ndarray.searchsorted 2,
  ndarray.setflags 2} and the `"ndarray.searchsorted" not in calls` assertion; IFERC pin belongs to
  history-iferc-permutation, also in this worktree). Allocation ceilings pass.
- Ledger vs candidate: ndarray.view 1 -> 0, ndarray.astype 0 -> 1 (as-is also has astype 1).
- least_peak (pins.py): futures 360 / 3630: as-is 3520 / 16600, candidate 1756 / 1756, fixed
  1760 / 1760; gas daily 365: as-is 7404, candidate 4780, fixed 4784.
- bench_compare peak (3 rounds): futures.360 3,504 -> 1,728; futures.3630 16,584 -> 1,728;
  futures.36000 146,064 -> 1,728; gasdaily.12m 7,388 -> 4,752; gasdaily.120m 19,964 -> 4,752.
  Rejection paths (verifier harness): short3630 60,104 -> 40,320 (candidate 35,088);
  gasdaily short120m 80,948 -> 58,992 (candidate 44,512). Saving survives.
