as-is tree: scratch/verify/utilities/trees/after_c3/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-4/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.Index | 62.80 (62.80..90.44) | 62.80 (62.80..110.97) | -0% |  | 1,137 -> 1,193 (+5%) | same | same |
| read.MarketHistory.futures.360 | 216.49 (216.49..353.15) | 193.53 (193.53..199.04) | -11% | down | 53,819 -> 43,363 (-19%) | numpy.array: 3->2; numpy.empty: 7->5 | MixedArray.shape: 1->0; calendar_table: 1->0 |
| read.Market.futures.360 | 209.92 (209.92..362.61) | 182.58 (182.58..264.63) | -13% |  | 51,019 -> 40,667 (-20%) | numpy.array: 3->2; numpy.empty: 6->4 | MixedArray.shape: 1->0; calendar_table: 1->0 |
| read.Calendar.futures.3630 | 487.82 (487.82..810.96) | 498.81 (498.81..619.24) | +2% |  | 251,938 -> 251,994 (+0%) | same | same |
| read.MarketHistory.futures.3630 | 1100.60 (1100.60..2262.75) | 1208.01 (1208.01..2277.92) | +10% |  | 634,944 -> 634,824 (-0%) | numpy.array: 3->2; numpy.empty: 7->5 | MixedArray.shape: 1->0; calendar_table: 1->0 |
| read.Market.futures.3630 | 1200.35 (1200.35..1287.28) | 1090.52 (1090.52..2054.44) | -9% |  | 505,573 -> 403,661 (-20%) | numpy.array: 3->2; numpy.empty: 6->4 | MixedArray.shape: 1->0; calendar_table: 1->0 |
| read.MarketHistory.futures.36000 | 14408.35 (14408.35..21671.68) | 11476.46 (11476.46..17948.80) | -20% |  | 6,222,147 -> 6,222,027 (-0%) | numpy.array: 3->2; numpy.empty: 7->5 | MixedArray.shape: 1->0; calendar_table: 1->0 |
| read.Market.futures.36000 | 11862.47 (11862.47..18227.33) | 10293.49 (10293.49..14978.84) | -13% |  | 5,004,979 -> 4,585,606 (-8%) | numpy.array: 3->2; numpy.empty: 6->4 | MixedArray.shape: 1->0; calendar_table: 1->0 |
| read.Market.gasdaily.12m | 215.28 (215.28..355.59) | 199.67 (199.67..295.19) | -7% |  | 48,698 -> 38,206 (-22%) | numpy.array: 3->2; numpy.empty: 6->4 | MixedArray.shape: 1->0; calendar_table: 1->0 |
| read.MarketHistory.iferc.120m | 139.66 (139.66..174.69) | 125.30 (125.30..241.96) | -10% |  | 18,123 -> 14,611 (-19%) | numpy.array: 3->2; numpy.empty: 7->5 | MixedArray.shape: 1->0; calendar_table: 1->0 |
