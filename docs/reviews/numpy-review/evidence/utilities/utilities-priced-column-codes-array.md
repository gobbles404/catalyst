as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-4/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.MarketHistory.futures.360 | 243.91 (243.91..390.61) | 202.76 (202.76..372.05) | -17% |  | 53,627 -> 53,819 (+0%) | numpy.array: 2->3 | same |
| read.Market.futures.360 | 232.55 (232.55..405.44) | 195.97 (195.97..366.57) | -16% |  | 50,827 -> 51,019 (+0%) | numpy.array: 2->3 | same |
| read.Calendar.futures.3630 | 543.76 (543.76..866.99) | 497.60 (497.60..768.07) | -8% |  | 251,938 -> 251,938 (+0%) | same | same |
| read.MarketHistory.futures.3630 | 1643.06 (1643.06..2400.74) | 1461.47 (1461.47..2147.93) | -11% |  | 634,944 -> 634,944 (+0%) | numpy.array: 2->3 | same |
| read.Market.futures.3630 | 1583.93 (1583.93..1910.14) | 1199.89 (1199.89..1793.82) | -24% |  | 505,381 -> 505,573 (+0%) | numpy.array: 2->3 | same |
| read.MarketHistory.futures.36000 | 17307.74 (17307.74..23212.28) | 14134.69 (14134.69..16311.89) | -18% | down | 6,222,147 -> 6,222,147 (+0%) | numpy.array: 2->3 | same |
| read.Market.futures.36000 | 11519.72 (11519.72..18027.82) | 11170.41 (11170.41..11979.14) | -3% |  | 5,004,787 -> 5,004,979 (+0%) | numpy.array: 2->3 | same |
| read.Market.gasdaily.12m | 219.57 (219.57..373.20) | 195.26 (195.26..207.59) | -11% | down | 48,506 -> 48,698 (+0%) | numpy.array: 2->3 | same |
| read.MarketHistory.gasdaily.12m | 202.49 (202.49..357.43) | 202.21 (202.21..310.89) | -0% |  | 51,226 -> 51,418 (+0%) | numpy.array: 2->3 | same |
| read.MarketHistory.iferc.120m | 145.01 (145.01..242.10) | 139.65 (139.65..234.77) | -4% |  | 18,987 -> 18,123 (-5%) | numpy.array: 2->3 | same |
