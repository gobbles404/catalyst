as-is tree: scratch/verify/utilities/trees/after_c1/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-4/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.MarketHistory.futures.360 | 210.57 (210.57..351.93) | 214.86 (214.86..283.81) | +2% |  | 53,819 -> 53,819 (+0%) | numpy.asarray: 2->1 | same |
| read.Market.futures.360 | 212.26 (212.26..358.01) | 204.19 (204.19..237.58) | -4% |  | 51,019 -> 51,019 (+0%) | numpy.asarray: 2->1 | same |
| read.MarketHistory.futures.3630 | 1458.69 (1458.69..1798.05) | 1435.51 (1435.51..1594.19) | -2% |  | 634,944 -> 634,944 (+0%) | numpy.asarray: 2->1 | same |
| read.Market.futures.3630 | 1241.73 (1241.73..1727.88) | 1267.06 (1267.06..1818.27) | +2% |  | 505,573 -> 505,573 (+0%) | numpy.asarray: 2->1 | same |
| read.MarketHistory.futures.36000 | 13862.27 (13862.27..20290.93) | 14846.88 (14846.88..20992.57) | +7% |  | 6,222,147 -> 6,222,147 (+0%) | numpy.asarray: 2->1 | same |
| read.Market.futures.36000 | 10516.84 (10516.84..18388.69) | 11390.85 (11390.85..15954.08) | +8% |  | 5,004,979 -> 5,004,979 (+0%) | numpy.asarray: 2->1 | same |
| read.MarketHistory.iferc.120m | 136.81 (136.81..230.02) | 156.71 (156.71..247.19) | +15% |  | 18,123 -> 18,123 (+0%) | numpy.asarray: 2->1 | same |
