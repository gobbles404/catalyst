as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.Calendar.futures.360 | 41.05 (41.05..63.20) | 41.36 (41.36..63.59) | +1% |  | 8,572 -> 8,572 (+0%) | ndarray.repeat: 0->1; ndarray.searchsorted: 1->0; ndarray.view: 0->1; numpy.arange: 1->2 | same |
| create.Calendar.futures.3630 | 147.84 (147.84..238.56) | 101.50 (101.50..147.46) | -31% | down | 66,677 -> 66,677 (+0%) | ndarray.repeat: 0->1; ndarray.searchsorted: 1->0; ndarray.view: 0->1; numpy.arange: 1->2 | same |
| create.Calendar.futures.36000 | 945.94 (945.94..2254.01) | 676.26 (676.26..1095.76) | -29% |  | 649,228 -> 649,228 (+0%) | ndarray.repeat: 0->1; ndarray.searchsorted: 1->0; ndarray.view: 0->1; numpy.arange: 1->2 | same |
| create.Calendar.gasdaily.12m | 36.60 (36.60..55.87) | 37.85 (37.85..64.70) | +3% |  | 7,905 -> 7,905 (+0%) | ndarray.repeat: 0->1; ndarray.searchsorted: 1->0; ndarray.view: 0->1; numpy.arange: 1->2 | same |
| create.Calendar.gasdaily.120m | 102.98 (102.98..156.16) | 58.62 (58.62..92.40) | -43% | down | 67,287 -> 67,287 (+0%) | ndarray.repeat: 0->1; ndarray.searchsorted: 1->0; ndarray.view: 0->1; numpy.arange: 1->2 | same |
| read.Calendar.futures.360 | 118.37 (118.37..165.38) | 117.52 (117.52..180.78) | -1% |  | 26,308 -> 26,308 (+0%) | same | same |
| read.Calendar.futures.3630 | 491.72 (491.72..773.23) | 473.59 (473.59..765.74) | -4% |  | 251,938 -> 251,938 (+0%) | same | same |
