# definitions group: what is here and how to rerun it

Worktree: worktrees/wf_9922a729-5fc-2 (branch from main at #118, 40fab53)

Commits, one per candidate (each with its budget pin moved in the same commit):
- f4433c0 curve-finite-look-as-all (recommend; kept)
- 931e380 curve-order-and-span-on-int64-view (reject; reverted by bfbbe3c)
- f6cd8b7 specs-bounds-as-reductions (recommend; kept)
- 859b4d5 specs-inf-lot-and-nan-fee-correctness (design-fork; reverted by b403fce so the final tree holds only the recommended pair)

Files:
- equiv.py: as-is against proposed, each side in its own process with warnings as errors; 50 curve cases and 144 specification cases; arrays compared by their bytes, plus dtype, shape, C-contiguity, writeable flag and memory ownership; failures by type and message. `--only curve|specs`; `EQUIV_SHOW=1` prints every as-is outcome.
  Outputs: equiv_c1.txt, equiv_c2.txt, equiv_c3.txt, equiv_c4.txt, equiv_c1_c2_c3.txt, equiv_final_c1_c3.txt.
- specs_min_counterexample.py: why the fee rule uses np.fmin.reduce and not ndarray.min. The reviewers' min() version accepts [nan, -1.0], which is refused today.
- micro.py: the isolated operations at 100, 3,631 and 10,000 elements, and each builder called directly in each tree.
  Outputs: micro_isolated_and_builders_c1.md (isolated table), micro_builders_c1_to_c4.md, micro_builders_final_c1_c3.md.
- bench/: a copy of the shared harness plus these scenarios: curve daily 365/36,500; specifications 12/1,200/12,000; and three rejections (rises-last, unordered-last, fee-last).
  Compare tables: curve-finite-look-as-all.md, curve-order-and-span-on-int64-view.cumulative.md (C1+C2 against as-is), specs-bounds-as-reductions.md, specs-inf-lot-and-nan-fee-correctness.vs-asis.md and .vs-c3.md (C4 alone, against trees/after-c3, a git archive of f6cd8b7).

Reading the clocks: load average was about 5 on 4 cores. In the same runs an untouched scenario (create.Index.futures) moved by 18%, and identical code by up to 26%. No timing in these tables beats that noise. The counts are the evidence: peak bytes, the two ledgers, and passes over the data.
