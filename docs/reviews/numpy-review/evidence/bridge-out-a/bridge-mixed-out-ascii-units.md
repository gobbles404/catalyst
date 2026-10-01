as-is tree: scratch/verify/bridge-out-a/trees/c4/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.EchoMixed.mixed.10k | 129.95 (129.95..331.10) | 192.56 (192.56..247.03) | +48% |  | 62,117 -> 34,302 (-45%) | same | same |
| read.ContractSpecifications.120 | 54.54 (54.54..95.48) | 60.98 (60.98..128.21) | +12% |  | 16,135 -> 11,560 (-28%) | same | same |
| read.Calendar.futures.360 | 93.83 (93.83..162.19) | 87.90 (87.90..128.95) | -6% |  | 25,236 -> 25,236 (+0%) | same | same |
| read.MarketHistory.futures.360 | 180.62 (180.62..411.55) | 182.22 (182.22..340.91) | +1% |  | 53,403 -> 53,403 (+0%) | same | same |
| read.Market.futures.360 | 197.62 (197.62..357.44) | 192.50 (192.50..271.11) | -3% |  | 50,691 -> 50,691 (+0%) | same | same |
| read.Calendar.futures.3630 | 326.20 (326.20..645.88) | 326.74 (326.74..1409.34) | +0% |  | 247,612 -> 247,612 (+0%) | same | same |
| read.MarketHistory.futures.3630 | 1180.01 (1180.01..1773.74) | 1252.63 (1252.63..2816.73) | +6% |  | 616,568 -> 534,093 (-13%) | ndarray.any: 2->1; ndarray.max: 2->3; numpy.asanyarray: 1->2; numpy.empty: 7->8 | same |
| read.Market.futures.3630 | 826.91 (826.91..1868.82) | 825.68 (825.68..1678.91) | -0% |  | 505,245 -> 505,245 (+0%) | same | same |
