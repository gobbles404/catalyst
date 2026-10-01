as-is tree: scratch/verify/bridge-out-a/trees/c3/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-out-a/trees/c4/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.EchoMixed.numbers.10k | 33.28 (33.28..62.75) | 29.65 (29.65..55.40) | -11% |  | 50,536 -> 20,449 (-60%) | ndarray.all: 0->1; ndarray.any: 3->1; ndarray.max: 0->1 | _bad_mixed: 1->0 |
| probe.EchoMixed.mixed.10k | 127.97 (127.97..255.09) | 127.20 (127.20..188.87) | -1% |  | 72,213 -> 62,117 (-14%) | ndarray.all: 0->1; ndarray.any: 3->1; ndarray.max: 0->1 | _bad_mixed: 1->0 |
| read.ValuationDate | 56.90 (56.90..91.95) | 49.97 (49.97..85.79) | -12% |  | 2,102 -> 2,102 (+0%) | ndarray.all: 0->1; ndarray.any: 3->1; ndarray.max: 1->2 | _bad_mixed: 1->0 |
| read.DiscountCurve.3631 | 81.13 (81.13..197.07) | 73.62 (73.62..122.28) | -9% |  | 102,452 -> 80,567 (-21%) | ndarray.all: 0->1; ndarray.any: 3->1; ndarray.max: 1->2 | _bad_mixed: 1->0 |
| read.Index | 57.49 (57.49..99.75) | 70.55 (70.55..92.01) | +23% |  | 1,233 -> 1,233 (+0%) | ndarray.all: 0->1; ndarray.any: 5->3; ndarray.max: 0->1 | _bad_mixed: 1->0 |
| read.Calendar.futures.360 | 96.20 (96.20..184.86) | 87.80 (87.80..142.58) | -9% |  | 25,236 -> 25,236 (+0%) | ndarray.all: 0->1; ndarray.any: 3->1; ndarray.max: 1->2 | _bad_mixed: 1->0 |
| read.MarketHistory.futures.360 | 187.51 (187.51..406.25) | 181.20 (181.20..365.22) | -3% |  | 53,403 -> 53,403 (+0%) | ndarray.all: 0->1; ndarray.any: 3->1; ndarray.max: 1->2 | _bad_mixed: 1->0 |
| read.Calendar.futures.3630 | 342.18 (342.18..570.86) | 330.06 (330.06..490.34) | -4% |  | 249,128 -> 247,612 (-1%) | ndarray.all: 0->1; ndarray.any: 3->1; ndarray.max: 1->2 | _bad_mixed: 1->0 |
| read.MarketHistory.futures.3630 | 1318.51 (1318.51..1871.43) | 1324.06 (1324.06..1998.85) | +0% |  | 634,824 -> 616,568 (-3%) | ndarray.all: 0->1; ndarray.any: 4->2; ndarray.max: 1->2 | _bad_mixed: 1->0 |
