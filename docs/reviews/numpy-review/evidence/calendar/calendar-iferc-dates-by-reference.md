as-is tree: scratch/verify/calendar/trees/after-repeat/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.Calendar.iferc.120m | 23.95 (23.95..40.26) | 23.02 (23.02..25.64) | -4% |  | 10,504 -> 10,504 (+0%) | numpy.array: 1->0 | same |
| create.Calendar.iferc.1200m | 62.30 (62.30..87.66) | 55.75 (55.75..87.63) | -11% |  | 41,224 -> 41,224 (+0%) | numpy.array: 1->0 | same |
| create.MarketHistory.iferc.120m | 42.73 (42.73..65.89) | 43.45 (43.45..75.57) | +2% |  | 11,520 -> 11,520 (+0%) | same | same |
| create.MarketHistory.iferc.1200m | 276.26 (276.26..384.05) | 272.88 (272.88..324.68) | -1% |  | 95,220 -> 95,220 (+0%) | same | same |
| read.Calendar.iferc.1200m | 235.98 (235.98..299.83) | 247.63 (247.63..414.01) | +5% |  | 86,692 -> 86,692 (+0%) | same | same |
