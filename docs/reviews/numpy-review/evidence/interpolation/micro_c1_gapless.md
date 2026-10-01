as-is <repo>/src/goosedove/globals/interpolation.py
proposed interp_c1_gapless.py

| shape | as-is us (min) | proposed us (min) | change | peak B as-is -> proposed | numpy ledger diff |
|---|---:|---:|---:|---:|---|
| daily 100 | 19.97 | 3.28 | -84% | 5,728 -> 1,952 | ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.repeat: 1->0; numpy.arange: 2->1; numpy.asarray: 1->0 |
| daily 10000 | 416.11 | 12.46 | -97% | 480,928 -> 160,352 | ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.repeat: 1->0; numpy.arange: 2->1; numpy.asarray: 1->0 |
| a12 100 | 19.75 | 18.77 | -5% | 3,616 -> 3,616 | same |
| a12 10000 | 139.14 | 140.52 | +1% | 241,216 -> 241,216 | same |
| a1000 10000 | 163.97 | 161.15 | -2% | 264,928 -> 264,928 | same |
| a2 1048574 | 16059.53 | 16755.73 | +4% | 25,166,752 -> 25,166,752 | same |

as-is ledger, a12 10000: {'ndarray.astype': 1, 'ndarray.repeat': 1, 'numpy.asarray': 1, 'numpy.arange': 2}
