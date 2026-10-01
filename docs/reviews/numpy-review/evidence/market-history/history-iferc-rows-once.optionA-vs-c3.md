as-is tree: scratch/verify/market-history/trees/c3/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.MarketHistory.iferc.120m | 37.05 (37.05..68.19) | 30.79 (30.79..57.08) | -17% |  | 6,488 -> 6,488 (+0%) | numpy.array: 1->0; numpy.fromiter: 0->1 | same |
| create.MarketHistory.iferc.1200m | 250.40 (250.40..450.06) | 212.28 (212.28..417.24) | -15% |  | 81,516 -> 81,516 (+0%) | numpy.array: 1->0; numpy.fromiter: 0->1 | same |
| history.iferc.shuffled120m | 35.37 (35.37..62.95) | 31.87 (31.87..59.04) | -10% |  | 6,488 -> 6,488 (+0%) | numpy.array: 1->0; numpy.fromiter: 0->1 | same |
| history.iferc.shuffled1200m | 270.78 (270.78..290.26) | 231.18 (231.18..440.36) | -15% |  | 81,516 -> 81,516 (+0%) | numpy.array: 1->0; numpy.fromiter: 0->1 | same |
