as-is scratch/verify/market-history/trees/c1 vs proposed worktrees/wf_0d4f8983-1f8-3, 3 rounds, best of rounds (min of 7 timeit repeats each)

| case | as-is us | proposed us | ratio | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|
| gas 12m / 254 prints (bench 12m) | 10.74 | 9.85 | 0.92 | 4,608 | 4,399 |
| gas 120m / 100 prints | 9.85 | 9.64 | 0.98 | 2,144 | 1,935 |
| gas 120m all fixed / 3,652 prints | 20.63 | 13.36 | 0.65 | 59,008 | 58,799 |
| gas 360m all fixed / ~10,950 prints | 41.32 | 19.24 | 0.47 | 175,888 | 175,679 |
| gas 12m / 26,000-print series | 11.05 | 10.52 | 0.95 | 4,672 | 4,463 |
