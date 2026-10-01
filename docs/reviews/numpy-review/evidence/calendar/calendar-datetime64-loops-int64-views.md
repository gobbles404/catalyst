as-is tree: scratch/verify/calendar/trees/after-repeat/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 249.08 (249.08..445.95) | 255.68 (255.68..318.05) | +3% |  | 216,235 -> 216,347 (+0%) | ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors12.3630 | 145.53 (145.53..197.69) | 159.66 (159.66..236.22) | +10% |  | 89,570 -> 89,682 (+0%) | ndarray.view: 0->1 | same |
| create.FuturesFixings.260 | 73.91 (73.91..119.13) | 77.30 (77.30..93.93) | +5% |  | 11,194 -> 11,306 (+1%) | ndarray.view: 0->1 | same |
| create.FuturesFixings.2600 | 243.36 (243.36..270.89) | 256.73 (256.73..404.52) | +5% |  | 93,094 -> 93,206 (+0%) | ndarray.view: 0->1 | same |
| create.FuturesFixings.26000 | 1919.85 (1919.85..2947.28) | 1619.36 (1619.36..2439.73) | -16% |  | 912,094 -> 912,206 (+0%) | ndarray.view: 0->1 | same |
| create.Calendar.futures.360 | 41.73 (41.73..85.07) | 45.84 (45.84..68.64) | +10% |  | 8,572 -> 8,668 (+1%) | generic.astype: 0->1; ndarray.view: 1->3 | same |
| create.Calendar.futures.3630 | 107.63 (107.63..165.59) | 107.25 (107.25..123.97) | -0% |  | 66,677 -> 66,644 (-0%) | generic.astype: 0->1; ndarray.view: 1->3 | same |
| create.Calendar.futures.36000 | 715.20 (715.20..911.41) | 694.94 (694.94..878.12) | -3% |  | 649,228 -> 649,195 (-0%) | generic.astype: 0->1; ndarray.view: 1->3 | same |
| create.Calendar.gasdaily.12m | 38.50 (38.50..58.00) | 43.98 (43.98..88.03) | +14% |  | 7,905 -> 7,891 (-0%) | generic.astype: 0->1; ndarray.view: 1->2 | same |
| create.Calendar.gasdaily.120m | 59.23 (59.23..126.45) | 60.45 (60.45..119.72) | +2% |  | 67,287 -> 67,158 (-0%) | generic.astype: 0->1; ndarray.view: 1->2 | same |
| create.Calendar.iferc.120m | 24.28 (24.28..49.98) | 29.73 (29.73..48.01) | +22% |  | 10,504 -> 10,504 (+0%) | generic.astype: 0->1; ndarray.view: 0->1 | same |
| create.Calendar.iferc.1200m | 59.64 (59.64..78.15) | 68.30 (68.30..120.02) | +15% |  | 41,224 -> 41,224 (+0%) | generic.astype: 0->1; ndarray.view: 0->1 | same |
| create.MarketHistory.futures.360 | 26.43 (26.43..50.85) | 29.01 (29.01..47.38) | +10% |  | 3,504 -> 3,551 (+1%) | generic.astype: 0->1; ndarray.astype: 1->0; ndarray.view: 0->1 | same |
| create.MarketHistory.futures.3630 | 33.40 (33.40..47.24) | 31.95 (31.95..50.30) | -4% |  | 16,584 -> 16,631 (+0%) | generic.astype: 0->1; ndarray.astype: 1->0; ndarray.view: 0->1 | same |
| create.MarketHistory.futures.36000 | 34.90 (34.90..64.20) | 37.41 (37.41..70.63) | +7% |  | 146,064 -> 146,111 (+0%) | generic.astype: 0->1; ndarray.astype: 1->0; ndarray.view: 0->1 | same |
| create.MarketHistory.gasdaily.12m | 31.30 (31.30..52.27) | 31.12 (31.12..59.39) | -1% |  | 7,388 -> 7,435 (+1%) | generic.astype: 0->1; ndarray.astype: 1->0; ndarray.view: 0->1 | same |
| create.MarketHistory.gasdaily.120m | 33.33 (33.33..54.82) | 32.66 (32.66..55.02) | -2% |  | 19,964 -> 20,011 (+0%) | generic.astype: 0->1; ndarray.astype: 1->0; ndarray.view: 0->1 | same |
