as-is <repo> vs proposed worktrees/wf_0d4f8983-1f8-3, 3 rounds, best of rounds (min of 7 timeit repeats each)

| case | as-is us | proposed us | ratio | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|
| iferc 120m in order | 35.10 | 29.35 | 0.84 | 11,520 | 6,488 |
| iferc 120m shuffled | 36.13 | 31.07 | 0.86 | 11,520 | 6,488 |
| iferc 1200m shuffled | 293.30 | 261.70 | 0.89 | 95,220 | 81,516 |
| iferc 10000m shuffled | 2303.00 | 2006.47 | 0.87 | 831,204 | 720,700 |
