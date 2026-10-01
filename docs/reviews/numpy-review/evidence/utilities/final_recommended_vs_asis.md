as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-4/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.MarketHistory.futures.360 | 232.13 (232.13..406.65) | 198.42 (198.42..447.23) | -15% |  | 53,627 -> 53,819 (+0%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
| read.Market.futures.360 | 214.34 (214.34..383.52) | 209.48 (209.48..442.50) | -2% |  | 50,827 -> 51,019 (+0%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
| read.MarketHistory.futures.3630 | 1484.10 (1484.10..1726.91) | 1498.40 (1498.40..2838.50) | +1% |  | 634,944 -> 634,944 (+0%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
| read.Market.futures.3630 | 1321.07 (1321.07..1876.48) | 1174.11 (1174.11..1740.06) | -11% |  | 505,381 -> 505,573 (+0%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
| read.MarketHistory.futures.36000 | 16135.43 (16135.43..23051.66) | 15808.21 (15808.21..26943.49) | -2% |  | 6,222,147 -> 6,222,147 (+0%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
| read.Market.futures.36000 | 10779.77 (10779.77..12707.60) | 11154.71 (11154.71..11921.25) | +3% |  | 5,004,787 -> 5,004,979 (+0%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
| read.Market.gasdaily.12m | 222.68 (222.68..422.90) | 199.53 (199.53..366.11) | -10% |  | 48,506 -> 48,698 (+0%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
| read.MarketHistory.iferc.120m | 145.00 (145.00..290.44) | 135.14 (135.14..172.75) | -7% |  | 18,987 -> 18,123 (-5%) | numpy.array: 2->3; numpy.asarray: 2->1 | same |
