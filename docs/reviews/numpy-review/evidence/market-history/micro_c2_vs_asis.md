as-is <repo> vs proposed worktrees/wf_0d4f8983-1f8-3, 3 rounds, best of rounds (min of 7 timeit repeats each)

| case | as-is us | proposed us | ratio | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|
| gas 12m / 254 prints (bench 12m) | 23.11 | 9.88 | 0.43 | 7,388 | 4,399 |
| gas 120m / 100 prints | 22.72 | 9.64 | 0.42 | 17,192 | 1,935 |
| gas 120m all fixed / 3,652 prints | 61.72 | 12.70 | 0.21 | 95,736 | 58,799 |
| gas 360m all fixed / ~10,950 prints | 142.37 | 17.95 | 0.13 | 285,666 | 175,679 |
| gas 12m / 26,000-print series | 169.43 | 10.01 | 0.06 | 442,720 | 4,463 |
