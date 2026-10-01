as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| look.EchoDates.10k | 142.40 (142.40..245.79) | 86.29 (86.29..191.28) | -39% |  | 251,256 -> 171,192 (-32%) | ndarray.any: 3->1; ndarray.astype: 2->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.ValuationDate | 52.35 (52.35..89.18) | 46.96 (46.96..86.40) | -10% |  | 1,671 -> 2,142 (+28%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.DiscountCurve.3631 | 116.33 (116.33..198.27) | 91.51 (91.51..140.06) | -21% |  | 128,381 -> 102,524 (-20%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.FuturesSchedule.120 | 84.14 (84.14..186.91) | 78.42 (78.42..125.86) | -7% |  | 7,803 -> 7,803 (+0%) | ndarray.any: 7->3; ndarray.astype: 0->2; ndarray.max: 0->2; ndarray.min: 0->2; ndarray.view: 0->2 | same |
| read.HolidayCalendar.100 | 57.58 (57.58..91.10) | 45.88 (45.88..109.66) | -20% |  | 3,850 -> 2,478 (-36%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.ContractSpecifications.120 | 81.85 (81.85..125.94) | 85.00 (85.00..191.65) | +4% |  | 16,841 -> 16,841 (+0%) | same | same |
| read.Index | 60.99 (60.99..101.42) | 75.85 (75.85..180.49) | +24% |  | 1,137 -> 1,137 (+0%) | same | same |
| read.FuturesFixings.2600 | 88.77 (88.77..160.16) | 77.47 (77.47..154.78) | -13% |  | 92,296 -> 73,656 (-20%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.PriceVector.10000 | 60.58 (60.58..105.04) | 67.99 (67.99..128.75) | +12% |  | 140,812 -> 140,812 (+0%) | same | same |
| read.Calendar.futures.360 | 122.95 (122.95..221.21) | 108.20 (108.20..433.72) | -12% |  | 26,308 -> 25,533 (-3%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.MarketHistory.futures.360 | 219.38 (219.38..388.62) | 206.54 (206.54..403.96) | -6% |  | 53,523 -> 53,523 (+0%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.Market.futures.360 | 217.83 (217.83..389.63) | 228.07 (228.07..536.15) | +5% |  | 50,827 -> 50,811 (-0%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.Calendar.futures.3630 | 491.13 (491.13..1109.83) | 494.04 (494.04..931.20) | +1% |  | 251,938 -> 249,128 (-1%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.MarketHistory.futures.3630 | 1489.37 (1489.37..2479.78) | 1469.05 (1469.05..4008.06) | -1% |  | 634,944 -> 634,944 (+0%) | ndarray.any: 6->4; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.Market.futures.3630 | 1184.78 (1184.78..2007.61) | 1214.08 (1214.08..2569.51) | +2% |  | 505,381 -> 505,365 (-0%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.MarketHistory.gasdaily.12m | 247.55 (247.55..325.14) | 220.06 (220.06..504.79) | -11% |  | 51,226 -> 51,226 (+0%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.MarketHistory.iferc.120m | 153.27 (153.27..256.90) | 136.30 (136.30..392.37) | -11% |  | 18,987 -> 18,987 (+0%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
| read.Calendar.iferc.1200m | 251.70 (251.70..458.78) | 281.77 (281.77..518.34) | +12% |  | 86,588 -> 86,588 (+0%) | ndarray.any: 5->3; ndarray.astype: 0->1; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | same |
