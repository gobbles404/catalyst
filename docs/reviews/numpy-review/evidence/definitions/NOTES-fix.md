# specs-bounds-as-reductions: fix

Worktree worktrees/wf_9922a729-5fc-2, fix commit 671e9f1
("fix(specs-bounds-as-reductions): reduce each fee column over every element, axis=None").

Flaw (refute/definitions-equivalence): `np.fmin.reduce(fees)` reduces along axis 0 only; as-is
`(fees < 0.0).any()` reduces over every element. A 2-D fee array (Python-only; the seam hands 1-D
columns) changed outcome.

Fix: `np.fmin.reduce(fees, axis=None)`; comment gains "over every element, as min is". Lots keep
`.min()` (already all-element).

Evidence
- refuter shapes.py: as-is (fix_shapes_goosedove.txt) and fixed (fix_shapes_wf_9922a729-5fc-2.txt)
  are byte-identical, 11/11. The pre-fix candidate (fix_shapes_prefix.txt) differed on both 2-D cases.
  As-is on a 2-D failure raises IndexError ("index 1 is out of bounds for axis 0 with size 1"):
  argmax of the mask is a flat index applied to axis 0, an accident of the as-is code; parity kept,
  not repaired (the seam cannot produce it). Scalar (0-d) inputs also match (IndexError on failure).
- NaN cases (fix_nan.py): [nan,-1] refused row 2, [-1,nan] row 1, [nan,0,-2] row 3, [nan,nan] and
  [3,nan] accepted; identical to as-is.
- equiv.py: specs 144/144 identical, curve 50/50 identical (equiv_fix_*.txt).
- ruff check/format clean, pyright 0 errors, tests/unit and tests/performance pass (exit 0); no pin
  moved; the existing ledger pin (ndarray.any 9->6, ndarray.min +1) still holds — fmin.reduce is a
  ufunc method, not recorded in the ledger.
- bench (bench_fix_local.txt, 3 rounds): peak bytes unchanged at 12/120/1,200/12,000 and on the
  fee-last rejection; ledger ndarray.any 9->6, ndarray.min 0->1. The saving is the three masks not
  built (tracemalloc peak is set elsewhere, so it does not show in peak bytes). Builder timings are
  noise; the checks in isolation: 1,200 fees mask 2.29us vs fmin(axis=None) 1.24us; 12,000
  3.70 vs 3.04; axis=None costs nothing over axis=0.
