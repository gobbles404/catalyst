as-is <repo>/src/goosedove/globals/interpolation.py
proposed worktrees/wf_9922a729-5fc-1/src/goosedove/globals/interpolation.py

| shape | as-is us (min) | proposed us (min) | change | peak B as-is -> proposed | numpy ledger diff |
|---|---:|---:|---:|---:|---|
| daily 100 | 34.79 | 33.73 | -3% | 5,728 -> 5,744 | ndarray.astype: 1->0; ndarray.view: 0->1 |
| daily 10000 | 406.50 | 401.21 | -1% | 480,928 -> 480,944 | ndarray.astype: 1->0; ndarray.view: 0->1 |
| a12 100 | 19.55 | 18.67 | -5% | 3,616 -> 3,632 | ndarray.astype: 1->0; ndarray.view: 0->1 |
| a12 10000 | 126.93 | 127.92 | +1% | 241,216 -> 241,232 | ndarray.astype: 1->0; ndarray.view: 0->1 |
| a1000 10000 | 180.11 | 174.16 | -3% | 264,928 -> 264,944 | ndarray.astype: 1->0; ndarray.view: 0->1 |
| a2 1048574 | 16970.01 | 16888.14 | -0% | 25,166,752 -> 25,166,768 | ndarray.astype: 1->0; ndarray.view: 0->1 |

as-is ledger, a12 10000: {'ndarray.astype': 1, 'ndarray.repeat': 1, 'numpy.asarray': 1, 'numpy.arange': 2}
