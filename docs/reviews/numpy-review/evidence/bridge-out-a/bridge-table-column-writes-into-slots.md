as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| look.EchoDates.10k | 143.47 (143.47..177.65) | 89.47 (89.47..365.73) | -38% |  | 251,256 -> 171,192 (-32%) | ndarray.any: 3->1; ndarray.astype: 2->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1 |
| read.ValuationDate | 53.56 (53.56..91.06) | 48.87 (48.87..188.27) | -9% |  | 1,671 -> 2,102 (+26%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.DiscountCurve.3631 | 103.11 (103.11..232.57) | 79.42 (79.42..144.68) | -23% |  | 128,381 -> 102,524 (-20%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.FuturesSchedule.120 | 85.63 (85.63..140.22) | 67.56 (67.56..156.56) | -21% |  | 7,803 -> 7,803 (+0%) | ndarray.any: 7->3; ndarray.max: 0->2; ndarray.min: 0->2; ndarray.view: 0->2 | _not_days: 0->2; _serials: 2->0 |
| read.HolidayCalendar.100 | 49.21 (49.21..93.44) | 40.14 (40.14..55.38) | -18% |  | 3,850 -> 2,212 (-43%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.ContractSpecifications.120 | 76.43 (76.43..141.17) | 71.33 (71.33..102.96) | -7% |  | 16,841 -> 16,841 (+0%) | same | same |
| read.Index | 62.73 (62.73..107.44) | 61.88 (61.88..69.89) | -1% |  | 1,137 -> 1,233 (+8%) | same | same |
| read.FuturesFixings.2600 | 91.91 (91.91..161.00) | 66.18 (66.18..101.92) | -28% |  | 92,296 -> 73,656 (-20%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.PriceVector.10000 | 57.02 (57.02..110.29) | 56.33 (56.33..110.81) | -1% |  | 140,812 -> 140,812 (+0%) | same | same |
| read.Calendar.futures.360 | 116.02 (116.02..321.39) | 104.80 (104.80..156.08) | -10% |  | 26,308 -> 25,533 (-3%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.futures.360 | 228.16 (228.16..434.29) | 197.71 (197.71..260.68) | -13% |  | 53,523 -> 53,523 (+0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.Market.futures.360 | 229.00 (229.00..389.99) | 203.04 (203.04..370.77) | -11% |  | 50,827 -> 50,811 (-0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.Calendar.futures.3630 | 504.06 (504.06..662.84) | 442.06 (442.06..768.27) | -12% |  | 251,938 -> 249,128 (-1%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.futures.3630 | 1522.61 (1522.61..2570.33) | 1423.26 (1423.26..2879.13) | -7% |  | 634,944 -> 634,944 (+0%) | ndarray.any: 6->4; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.Market.futures.3630 | 1053.71 (1053.71..1455.19) | 1193.42 (1193.42..3536.37) | +13% |  | 505,381 -> 505,365 (-0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.gasdaily.12m | 218.53 (218.53..326.56) | 191.68 (191.68..380.33) | -12% |  | 51,226 -> 51,226 (+0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.iferc.120m | 147.27 (147.27..247.98) | 129.59 (129.59..188.40) | -12% |  | 18,987 -> 18,987 (+0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.Calendar.iferc.1200m | 233.55 (233.55..457.95) | 227.17 (227.17..463.97) | -3% |  | 86,588 -> 86,588 (+0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
