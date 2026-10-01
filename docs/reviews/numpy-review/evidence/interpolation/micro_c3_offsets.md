as-is <repo>/src/goosedove/globals/interpolation.py
proposed worktrees/wf_9922a729-5fc-1/src/goosedove/globals/interpolation.py

| shape | as-is us (min) | proposed us (min) | change | peak B as-is -> proposed | numpy ledger diff |
|---|---:|---:|---:|---:|---|
| daily 100 | 19.77 | 19.60 | -1% | 5,728 -> 5,728 | ndarray.astype: 1->2; ndarray.view: 0->1 |
| daily 10000 | 404.72 | 352.48 | -13% | 480,928 -> 480,928 | ndarray.astype: 1->2; ndarray.view: 0->1 |
| a12 100 | 19.12 | 17.92 | -6% | 3,616 -> 3,616 | ndarray.astype: 1->2; ndarray.view: 0->1 |
| a12 10000 | 124.08 | 122.62 | -1% | 241,216 -> 241,216 | ndarray.astype: 1->2; ndarray.view: 0->1 |
| a1000 10000 | 158.13 | 151.07 | -4% | 264,928 -> 264,928 | ndarray.astype: 1->2; ndarray.view: 0->1 |
| a2 1048574 | 16576.76 | 17204.45 | +4% | 25,166,752 -> 25,166,752 | ndarray.astype: 1->2; ndarray.view: 0->1 |

as-is ledger, a12 10000: {'ndarray.astype': 1, 'ndarray.repeat': 1, 'numpy.asarray': 1, 'numpy.arange': 2}
