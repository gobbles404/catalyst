as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.ValuationDate | 52.86 (52.86..155.76) | 60.06 (60.06..117.42) | +14% |  | 1,671 -> 2,102 (+26%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.DiscountCurve.3631 | 100.27 (100.27..246.89) | 108.97 (108.97..227.22) | +9% |  | 128,381 -> 102,452 (-20%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.FuturesSchedule.120 | 88.21 (88.21..200.01) | 92.72 (92.72..130.41) | +5% |  | 7,803 -> 7,803 (+0%) | ndarray.any: 7->3; ndarray.max: 0->2; ndarray.min: 0->2; ndarray.ravel: 1->0; ndarray.view: 0->2; numpy.array: 1->0 | _not_days: 0->2; _serials: 2->0 |
| read.HolidayCalendar.100 | 47.92 (47.92..96.76) | 69.81 (69.81..110.25) | +46% |  | 3,850 -> 2,156 (-44%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.ContractSpecifications.120 | 76.33 (76.33..142.32) | 88.19 (88.19..98.93) | +16% |  | 16,841 -> 16,841 (+0%) | ndarray.ravel: 1->0; numpy.array: 1->0 | same |
| read.Index | 65.62 (65.62..125.00) | 64.24 (64.24..138.69) | -2% |  | 1,137 -> 1,233 (+8%) | ndarray.ravel: 1->0; numpy.array: 4->3 | same |
| read.FuturesFixings.2600 | 110.94 (110.94..286.59) | 90.70 (90.70..197.98) | -18% |  | 92,296 -> 73,584 (-20%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.view: 0->1 | _not_days: 0->1; _serials: 1->0 |
| read.PriceVector.10000 | 56.53 (56.53..239.99) | 91.04 (91.04..186.62) | +61% |  | 140,812 -> 140,756 (-0%) | same | same |
| read.Calendar.futures.360 | 124.66 (124.66..287.63) | 95.19 (95.19..231.80) | -24% |  | 26,308 -> 25,236 (-4%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 1->0; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.futures.360 | 318.37 (318.37..511.43) | 285.78 (285.78..717.36) | -10% |  | 53,523 -> 53,403 (-0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 1->0; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.Market.futures.360 | 354.11 (354.11..948.24) | 309.88 (309.88..571.79) | -12% |  | 50,827 -> 50,691 (-0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 2->1; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.Calendar.futures.3630 | 632.00 (632.00..1264.14) | 505.54 (505.54..908.17) | -20% |  | 251,938 -> 249,128 (-1%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 1->0; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.futures.3630 | 1463.94 (1463.94..3195.57) | 1998.60 (1998.60..3157.70) | +37% |  | 634,944 -> 634,824 (-0%) | ndarray.any: 6->4; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 2->1; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.Market.futures.3630 | 1793.92 (1793.92..2422.97) | 1683.86 (1683.86..3223.36) | -6% |  | 505,381 -> 505,245 (-0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 2->1; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.gasdaily.12m | 206.38 (206.38..649.01) | 190.74 (190.74..382.76) | -8% |  | 51,226 -> 51,106 (-0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 1->0; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.MarketHistory.iferc.120m | 187.81 (187.81..304.10) | 147.34 (147.34..259.73) | -22% |  | 18,987 -> 18,987 (+0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 1->0; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
| read.Calendar.iferc.1200m | 398.71 (398.71..575.35) | 235.33 (235.33..493.18) | -41% |  | 86,588 -> 86,588 (+0%) | ndarray.any: 5->3; ndarray.max: 0->1; ndarray.min: 0->1; ndarray.ravel: 1->0; ndarray.view: 0->1; numpy.array: 2->1 | _not_days: 0->1; _serials: 1->0 |
