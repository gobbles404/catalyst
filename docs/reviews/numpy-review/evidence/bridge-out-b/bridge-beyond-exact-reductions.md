as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-out-b/snap/beyond/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.Index | 61.64 (61.64..109.12) | 55.85 (55.85..104.92) | -9% |  | 1,137 -> 1,129 (-1%) | ndarray.any: 5->3; ndarray.max: 0->2; ndarray.min: 0->2; ufunc.reduce: 5->7 | same |
| out.IntColumn.100 | 10.04 (10.04..11.37) | 7.42 (7.42..10.75) | -26% |  | 1,481 -> 1,285 (-13%) | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 2->3 | same |
| out.Table.num4.100 | 60.80 (60.80..69.65) | 57.71 (57.71..90.87) | -5% |  | 6,664 -> 6,664 (+0%) | ndarray.any: 6->5; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 6->7 | same |
| out.Table.int.100 | 37.54 (37.54..61.50) | 33.77 (33.77..63.94) | -10% |  | 2,190 -> 2,190 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 4->5 | same |
| out.FloatColumn.10k | 8.12 (8.12..17.43) | 7.88 (7.88..13.41) | -3% |  | 10,289 -> 10,289 (+0%) | same | same |
| out.IntColumn.10k | 28.45 (28.45..43.31) | 19.24 (19.24..37.30) | -32% |  | 100,481 -> 90,385 (-10%) | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 2->3 | same |
| out.Table.num4.10k | 272.57 (272.57..415.88) | 251.76 (251.76..446.36) | -8% |  | 560,856 -> 560,856 (+0%) | ndarray.any: 6->5; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 6->7 | same |
| out.Table.int.10k | 72.90 (72.90..141.69) | 69.07 (69.07..133.12) | -5% |  | 140,790 -> 140,790 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 4->5 | same |
| out.IntColumn.100k | 219.45 (219.45..367.61) | 173.45 (173.45..282.75) | -21% |  | 1,000,481 -> 900,385 (-10%) | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 2->3 | same |
| out.Table.num4.100k | 2989.86 (2989.86..3780.50) | 2960.29 (2960.29..4384.69) | -1% |  | 5,600,856 -> 5,600,856 (+0%) | ndarray.any: 6->5; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 6->7 | same |
| out.Table.int.100k | 431.83 (431.83..664.09) | 384.97 (384.97..536.28) | -11% |  | 1,400,790 -> 1,400,790 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 4->5 | same |
| out.Table.int.1 | 35.42 (35.42..49.86) | 31.92 (31.92..57.09) | -10% |  | 810 -> 810 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 4->5 | same |
