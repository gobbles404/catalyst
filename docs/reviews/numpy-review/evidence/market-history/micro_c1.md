as-is <repo> vs proposed worktrees/wf_0d4f8983-1f8-3, 3 rounds, best of rounds (min of 7 timeit repeats each)

| case | as-is us | proposed us | ratio | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|
| futures 360d / 76 fixings (bench 360) | 19.62 | 10.15 | 0.52 | 3,504 | 1,584 |
| futures 36000d / 76 fixings (bench 36000) | 28.30 | 10.73 | 0.38 | 146,064 | 1,584 |
| futures 3630d / 100 fixings | 21.63 | 10.43 | 0.48 | 16,824 | 1,584 |
| futures 3630d all fixed / ~2,600 fixings | 48.83 | 17.47 | 0.36 | 66,482 | 40,784 |
| futures 14,500d all fixed / ~10,000 fixings | 129.50 | 39.77 | 0.31 | 267,576 | 164,688 |
| futures 360d / 26,000-fixing series | 178.33 | 10.51 | 0.06 | 442,720 | 1,648 |
| gas 12m / 254 prints (bench 12m) | 23.10 | 10.84 | 0.47 | 7,388 | 4,608 |
| gas 120m / 100 prints | 22.88 | 10.28 | 0.45 | 17,192 | 2,144 |
| gas 120m all fixed / 3,652 prints | 59.00 | 20.79 | 0.35 | 95,736 | 59,008 |
| gas 360m all fixed / ~10,950 prints | 143.93 | 40.68 | 0.28 | 285,666 | 175,888 |
| gas 12m / 26,000-print series | 172.15 | 11.05 | 0.06 | 442,720 | 4,672 |
