as-is <repo>/src/goosedove/globals/interpolation.py
proposed worktrees/wf_9922a729-5fc-1/src/goosedove/globals/interpolation.py

| shape | as-is us (min) | proposed us (min) | change | peak B as-is -> proposed | numpy ledger diff |
|---|---:|---:|---:|---:|---|
| daily 100 | 20.72 | 18.66 | -10% | 5,728 -> 5,432 | ndarray.any: 0->1; ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.reduce: 0->1 |
| daily 10000 | 431.47 | 349.35 | -19% | 480,928 -> 480,632 | ndarray.any: 0->1; ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.reduce: 0->1 |
| a12 100 | 18.68 | 18.06 | -3% | 3,616 -> 3,320 | ndarray.any: 0->1; ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.reduce: 0->1 |
| a12 10000 | 129.07 | 113.32 | -12% | 241,216 -> 240,920 | ndarray.any: 0->1; ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.reduce: 0->1 |
| a1000 10000 | 163.13 | 125.94 | -23% | 264,928 -> 264,632 | ndarray.any: 0->1; ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.reduce: 0->1 |
| a2 1048574 | 17016.32 | 14180.72 | -17% | 25,166,752 -> 25,166,456 | ndarray.any: 0->1; ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.reduce: 0->1 |

as-is ledger, a12 10000: {'ndarray.astype': 1, 'ndarray.repeat': 1, 'numpy.asarray': 1, 'numpy.arange': 2}
