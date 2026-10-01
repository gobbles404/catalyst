as-is <repo>/src/goosedove/globals/interpolation.py
proposed worktrees/wf_9922a729-5fc-1/src/goosedove/globals/interpolation.py

| shape | as-is us (min) | proposed us (min) | change | peak B as-is -> proposed | numpy ledger diff |
|---|---:|---:|---:|---:|---|
| daily 100 | 19.85 | 19.98 | +1% | 5,728 -> 5,952 | ndarray.view: 0->2 |
| daily 10000 | 389.37 | 393.65 | +1% | 480,928 -> 481,152 | ndarray.view: 0->2 |
| a12 100 | 19.08 | 19.20 | +1% | 3,616 -> 3,840 | ndarray.view: 0->2 |
| a12 10000 | 120.22 | 123.77 | +3% | 241,216 -> 241,440 | ndarray.view: 0->2 |
| a1000 10000 | 154.55 | 156.28 | +1% | 264,928 -> 265,152 | ndarray.view: 0->2 |
| a2 1048574 | 21136.68 | 21224.80 | +0% | 25,166,752 -> 25,166,976 | ndarray.view: 0->2 |

as-is ledger, a12 10000: {'ndarray.astype': 1, 'ndarray.repeat': 1, 'numpy.asarray': 1, 'numpy.arange': 2}
