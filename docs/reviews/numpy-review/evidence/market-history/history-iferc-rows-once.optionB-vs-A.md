as-is tree: scratch/verify/market-history/trees/c4a/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.IfercFixings.120 | 18.73 (18.73..24.71) | 33.84 (33.84..65.95) | +81% | up | 10,600 -> 6,560 (-38%) | ndarray.setflags: 1->2; numpy.array: 1->2 | same |
| create.IfercFixings.1200 | 157.59 (157.59..173.21) | 284.77 (284.77..334.26) | +81% | up | 42,888 -> 81,932 (+91%) | ndarray.setflags: 1->2; numpy.array: 1->2 | same |
| create.MarketHistory.iferc.120m | 32.21 (32.21..61.65) | 12.15 (12.15..20.01) | -62% | down | 6,488 -> 2,373 (-63%) | numpy.fromiter: 1->0 | same |
| create.MarketHistory.iferc.1200m | 228.19 (228.19..442.80) | 17.05 (17.05..20.79) | -93% | down | 81,516 -> 19,653 (-76%) | numpy.fromiter: 1->0 | same |
| history.iferc.shuffled120m | 31.54 (31.54..39.01) | 12.90 (12.90..19.86) | -59% | down | 6,488 -> 2,373 (-63%) | numpy.fromiter: 1->0 | same |
| history.iferc.shuffled1200m | 238.04 (238.04..418.85) | 17.82 (17.82..28.73) | -93% | down | 81,516 -> 19,653 (-76%) | numpy.fromiter: 1->0 | same |
| read.MarketHistory.iferc.120m | 143.32 (143.32..159.74) | 142.56 (142.56..153.95) | -1% |  | 18,987 -> 18,987 (+0%) | same | same |
