as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-out-b/snap/final/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.EchoColumn.10k | 8.93 (8.93..11.72) | 8.88 (8.88..12.00) | -1% |  | 10,385 -> 10,385 (+0%) | same | same |
| read.DiscountCurve.3631 | 109.30 (109.30..168.99) | 99.19 (99.19..179.64) | -9% |  | 128,381 -> 128,381 (+0%) | numpy.asarray: 1->0 | same |
| read.Index | 67.26 (67.26..108.35) | 56.52 (56.52..95.43) | -16% |  | 1,137 -> 1,129 (-1%) | ndarray.any: 5->3; ndarray.max: 0->2; ndarray.min: 0->2; ufunc.reduce: 5->7 | same |
| out.Date.const | 14.91 (14.91..25.78) | 4.61 (4.61..7.66) | -69% | down | 1,185 -> 952 (-20%) | generic.view: 0->1; ndarray.any: 2->0; numpy.array: 1->0; ufunc.reduce: 2->0 | _serials: 1->0 |
| out.Date.echo | 17.29 (17.29..24.92) | 6.85 (6.85..12.88) | -60% | down | 1,217 -> 1,144 (-6%) | generic.view: 0->1; ndarray.any: 2->0; numpy.array: 1->0; ufunc.reduce: 2->0 | _serials: 1->0 |
| out.IntColumn.100 | 10.52 (10.52..19.57) | 7.13 (7.13..9.86) | -32% | down | 1,481 -> 1,285 (-13%) | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 2->3 | same |
| out.Table.int.100 | 37.06 (37.06..47.11) | 32.48 (32.48..37.63) | -12% |  | 2,190 -> 2,190 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; numpy.asarray: 1->0; ufunc.reduce: 4->5 | same |
| out.IntColumn.10k | 28.26 (28.26..45.62) | 19.29 (19.29..23.40) | -32% | down | 100,481 -> 90,385 (-10%) | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 2->3 | same |
| out.Table.num4.10k | 295.11 (295.11..457.93) | 248.97 (248.97..346.13) | -16% |  | 560,856 -> 560,856 (+0%) | ndarray.any: 6->5; ndarray.max: 0->1; ndarray.min: 0->1; numpy.asarray: 1->0; ufunc.reduce: 6->7 | same |
| out.Table.int.10k | 86.14 (86.14..124.86) | 64.54 (64.54..107.04) | -25% |  | 140,790 -> 140,790 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; numpy.asarray: 1->0; ufunc.reduce: 4->5 | same |
| out.IntColumn.100k | 234.62 (234.62..331.00) | 173.87 (173.87..293.79) | -26% |  | 1,000,481 -> 900,385 (-10%) | ndarray.any: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 2->3 | same |
| out.Table.int.100k | 521.01 (521.01..811.30) | 347.69 (347.69..409.87) | -33% | down | 1,400,790 -> 1,400,790 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; numpy.asarray: 1->0; ufunc.reduce: 4->5 | same |
| out.Table.int.1 | 39.39 (39.39..60.97) | 31.45 (31.45..41.26) | -20% |  | 810 -> 810 (+0%) | ndarray.any: 4->3; ndarray.max: 0->1; ndarray.min: 0->1; numpy.asarray: 1->0; ufunc.reduce: 4->5 | same |
