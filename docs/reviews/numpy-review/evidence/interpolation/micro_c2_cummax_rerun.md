as-is <repo>/src/goosedove/globals/interpolation.py
proposed interp_c2_cummax.py

| shape | as-is us (min) | proposed us (min) | change | peak B as-is -> proposed | numpy ledger diff |
|---|---:|---:|---:|---:|---|
| daily 100 | 19.77 | 12.04 | -39% | 5,728 -> 5,432 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| daily 10000 | 407.93 | 285.37 | -30% | 480,928 -> 480,632 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a12 100 | 19.00 | 11.51 | -39% | 3,616 -> 3,320 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a12 10000 | 138.57 | 131.03 | -5% | 241,216 -> 240,920 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a1000 10000 | 286.82 | 136.44 | -52% | 264,928 -> 264,632 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |
| a2 1048574 | 15404.22 | 17000.77 | +10% | 25,166,752 -> 25,166,456 | ndarray.astype: 1->0; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 |

as-is ledger, a12 10000: {'ndarray.astype': 1, 'ndarray.repeat': 1, 'numpy.asarray': 1, 'numpy.arange': 2}
