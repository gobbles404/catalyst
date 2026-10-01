as-is tree: scratch/verify/calendar/trees/after-repeat/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.Calendar.futures.360 | 45.94 (45.94..73.71) | 43.71 (43.71..96.94) | -5% |  | 8,572 -> 8,572 (+0%) | ndarray.searchsorted: 0->1; numpy.zeros: 0->1 | same |
| create.Calendar.futures.3630 | 98.13 (98.13..187.89) | 103.41 (103.41..188.21) | +5% |  | 66,677 -> 66,446 (-0%) | ndarray.searchsorted: 0->1; numpy.zeros: 0->1 | same |
| create.Calendar.futures.36000 | 654.27 (654.27..807.58) | 689.01 (689.01..986.41) | +5% |  | 649,228 -> 648,997 (-0%) | ndarray.searchsorted: 0->1; numpy.zeros: 0->1 | same |
| create.Calendar.gasdaily.12m | 35.62 (35.62..53.40) | 38.34 (38.34..60.62) | +8% |  | 7,905 -> 7,674 (-3%) | ndarray.searchsorted: 0->1; numpy.zeros: 0->1 | same |
| create.Calendar.gasdaily.120m | 58.24 (58.24..114.82) | 54.46 (54.46..97.39) | -6% |  | 67,287 -> 67,056 (-0%) | ndarray.searchsorted: 0->1; numpy.zeros: 0->1 | same |
| create.Calendar.iferc.120m | 24.13 (24.13..43.87) | 24.60 (24.60..37.09) | +2% |  | 10,504 -> 10,504 (+0%) | ndarray.searchsorted: 0->1; numpy.zeros: 0->1 | same |
| create.Calendar.iferc.1200m | 60.36 (60.36..93.84) | 59.02 (59.02..100.12) | -2% |  | 41,224 -> 41,224 (+0%) | ndarray.searchsorted: 0->1; numpy.zeros: 0->1 | same |
