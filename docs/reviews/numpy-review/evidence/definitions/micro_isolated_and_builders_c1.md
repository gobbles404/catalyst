isolated operations, numpy 2.5.2, timeit min of 9 repeats; peak is tracemalloc over one run

| operation | n | as-is us (min) | proposed us (min) | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|---:|
| C1 finite look, all finite | 100 | 1.94 | 1.41 | -27% | 392 | 293 |
| C1 finite look, NaN last (failure path) | 100 | 2.58 | 2.56 | -1% | 392 | 520 |
| C2 order, datetime64 vs int64 view | 100 | 2.28 | 2.34 | +3% | 547 | 643 |
| C2 span, datetime64 scalars vs int64 view | 100 | 3.44 | 0.59 | -83% | 1,016 | 328 |
| C3 lot below one, mask.any vs min() | 100 | 1.89 | 0.96 | -49% | 300 | 128 |
| C3 fee negative, mask.any vs min() | 100 | 1.95 | 0.97 | -50% | 300 | 128 |
| C4 lot whole, + isinf | 100 | 2.06 | 3.44 | +67% | 1,092 | 1,092 |
| C4 fee 0 or more, < 0 vs ~(>= 0) | 100 | 1.87 | 2.36 | +26% | 300 | 392 |
| C1 finite look, all finite | 3,631 | 3.67 | 2.98 | -19% | 7,454 | 3,824 |
| C1 finite look, NaN last (failure path) | 3,631 | 4.45 | 4.31 | -3% | 7,454 | 7,582 |
| C2 order, datetime64 vs int64 view | 3,631 | 8.60 | 4.59 | -47% | 4,078 | 4,174 |
| C2 span, datetime64 scalars vs int64 view | 3,631 | 3.44 | 1.25 | -64% | 1,016 | 328 |
| C3 lot below one, mask.any vs min() | 3,631 | 4.19 | 2.48 | -41% | 3,831 | 128 |
| C3 fee negative, mask.any vs min() | 3,631 | 2.86 | 1.89 | -34% | 3,831 | 128 |
| C4 lot whole, + isinf | 3,631 | 4.77 | 8.36 | +75% | 32,871 | 32,871 |
| C4 fee 0 or more, < 0 vs ~(>= 0) | 3,631 | 2.99 | 3.90 | +31% | 3,831 | 7,454 |
| C1 finite look, all finite | 10,000 | 6.05 | 4.71 | -22% | 20,192 | 10,193 |
| C1 finite look, NaN last (failure path) | 10,000 | 6.46 | 6.52 | +1% | 20,192 | 20,320 |
| C2 order, datetime64 vs int64 view | 10,000 | 19.57 | 8.29 | -58% | 10,447 | 10,543 |
| C2 span, datetime64 scalars vs int64 view | 10,000 | 4.43 | 0.61 | -86% | 1,016 | 328 |
| C3 lot below one, mask.any vs min() | 10,000 | 5.01 | 3.19 | -36% | 10,200 | 128 |
| C3 fee negative, mask.any vs min() | 10,000 | 3.90 | 2.82 | -28% | 10,200 | 128 |
| C4 lot whole, + isinf | 10,000 | 8.27 | 15.23 | +84% | 90,192 | 90,192 |
| C4 fee 0 or more, < 0 vs ~(>= 0) | 10,000 | 4.29 | 5.37 | +25% | 10,200 | 20,192 |

builders called directly, min over 3 interleaved processes; as-is <repo>/src/goosedove/__init__.py, proposed worktrees/wf_9922a729-5fc-2/src/goosedove/__init__.py

| builder | as-is us (min) | proposed us (min) | change | as-is peak B | proposed peak B |
|---|---:|---:|---:|---:|---:|
| discount_curve daily 100 | 35.47 | 34.98 | -1% | 5,970 | 5,970 |
| discount_curve daily 3631 | 146.24 | 138.56 | -5% | 157,803 | 157,803 |
| discount_curve daily 10000 | 456.80 | 485.23 | +6% | 431,670 | 431,670 |
| contract_specifications 12 | 14.73 | 26.89 | +83% | 1,920 | 1,920 |
| contract_specifications 120 | 22.73 | 25.02 | +10% | 10,504 | 10,504 |
| contract_specifications 1200 | 121.45 | 122.16 | +1% | 41,224 | 41,224 |
| contract_specifications 10000 | 1138.91 | 1153.48 | +1% | 655,624 | 655,624 |
