as-is <repo>/src/goosedove/globals/interpolation.py
proposed worktrees/wf_9922a729-5fc-1/src/goosedove/globals/interpolation.py

| shape | as-is us (min) | proposed us (min) | change | peak B as-is -> proposed | numpy ledger diff |
|---|---:|---:|---:|---:|---|
| daily 100 | 20.44 | 12.16 | -41% | 5,728 -> 5,432 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| daily 10000 | 389.55 | 298.92 | -23% | 480,928 -> 480,632 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a12 100 | 18.64 | 11.75 | -37% | 3,616 -> 3,320 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a12 10000 | 139.07 | 130.78 | -6% | 241,216 -> 240,920 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a1000 10000 | 296.10 | 143.74 | -51% | 264,928 -> 264,632 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a2 1048574 | 15469.52 | 16902.93 | +9% | 25,166,752 -> 25,166,456 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |

as-is ledger, a12 10000: {'ndarray.astype': 1, 'ndarray.repeat': 1, 'numpy.asarray': 1, 'numpy.arange': 2}
