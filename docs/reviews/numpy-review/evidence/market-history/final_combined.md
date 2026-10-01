as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.MarketHistory.futures.360 | 27.41 (27.41..28.90) | 15.82 (15.82..20.71) | -42% | down | 3,504 -> 1,743 (-50%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| create.MarketHistory.futures.3630 | 29.49 (29.49..33.27) | 16.15 (16.15..18.92) | -45% | down | 16,584 -> 1,743 (-89%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| create.MarketHistory.futures.36000 | 35.19 (35.19..48.36) | 15.36 (15.36..20.74) | -56% | down | 146,064 -> 1,743 (-99%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| create.MarketHistory.gasdaily.12m | 29.80 (29.80..39.73) | 16.65 (16.65..18.19) | -44% | down | 7,388 -> 4,767 (-35%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| create.MarketHistory.gasdaily.120m | 33.05 (33.05..36.74) | 16.35 (16.35..28.71) | -51% | down | 19,964 -> 4,767 (-76%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| create.MarketHistory.iferc.120m | 43.63 (43.63..52.09) | 36.98 (36.98..40.27) | -15% | down | 11,520 -> 6,488 (-44%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| create.MarketHistory.iferc.1200m | 275.61 (275.61..330.64) | 252.62 (252.62..259.06) | -8% | down | 95,220 -> 81,516 (-14%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| create.Market.futures.360 | 4.80 (4.80..5.70) | 4.59 (4.59..7.90) | -4% |  | 242 -> 244 (+1%) | same | same |
| create.Market.futures.3630 | 4.46 (4.46..5.21) | 4.56 (4.56..6.27) | +2% |  | 244 -> 244 (+0%) | same | same |
| history.futures.series26000x360 | 194.79 (194.79..349.16) | 15.68 (15.68..16.91) | -92% | down | 442,720 -> 1,746 (-100%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| history.futures.allfixed3630 | 59.22 (59.22..65.85) | 23.35 (23.35..37.05) | -61% | down | 66,482 -> 40,914 (-38%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| history.futures.days36000x30 | 41.55 (41.55..53.00) | 15.27 (15.27..17.89) | -63% | down | 146,064 -> 1,746 (-99%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| history.gasdaily.allfixed120m | 67.12 (67.12..119.29) | 27.11 (27.11..46.41) | -60% | down | 95,736 -> 59,138 (-38%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| history.gasdaily.series26000x12m | 185.81 (185.81..216.66) | 16.30 (16.30..17.07) | -91% | down | 442,720 -> 4,770 (-99%) | ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; ndarray.searchsorted: 0->2; ndarray.view: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _inside: 0->1 |
| history.iferc.shuffled120m | 45.04 (45.04..93.24) | 37.45 (37.45..61.64) | -17% |  | 11,520 -> 6,488 (-44%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| history.iferc.shuffled1200m | 321.28 (321.28..630.73) | 266.01 (266.01..379.12) | -17% |  | 95,220 -> 81,516 (-14%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| history.reject.futures.short3630 | 51.88 (51.88..107.33) | 40.51 (40.51..60.44) | -22% |  | 60,104 -> 35,088 (-42%) | ndarray.any: 2->1; ndarray.astype: 1->0; ndarray.searchsorted: 0->2; ndarray.view: 0->1; ufunc.reduce: 2->1 | _inside: 0->1 |
| history.reject.futures.late360 | 9.30 (9.30..10.92) | 8.09 (8.09..9.53) | -13% |  | 2,112 -> 1,914 (-9%) | ndarray.any: 1->0; ndarray.argmax: 1->0; ndarray.searchsorted: 0->1; ufunc.reduce: 1->0 | same |
| history.reject.gasdaily.short120m | 61.37 (61.37..65.80) | 44.15 (44.15..72.43) | -28% |  | 80,948 -> 44,512 (-45%) | ndarray.any: 2->1; ndarray.astype: 1->0; ndarray.searchsorted: 0->2; ndarray.view: 0->1; ufunc.reduce: 2->1 | _inside: 0->1 |
| history.reject.iferc.missing120m | 33.90 (33.90..61.68) | 34.87 (34.87..36.18) | +3% |  | 6,855 -> 6,648 (-3%) | ndarray.any: 2->0; ndarray.max: 0->1; ufunc.reduce: 2->1 | same |
| history.reject.iferc.unfixed120m | 33.17 (33.17..38.25) | 35.44 (35.44..41.65) | +7% |  | 6,482 -> 6,274 (-3%) | ndarray.any: 1->0; ndarray.max: 0->1 | same |
| read.MarketHistory.futures.360 | 203.36 (203.36..268.43) | 206.67 (206.67..226.65) | +2% |  | 53,627 -> 53,627 (+0%) | same | same |
| read.MarketHistory.futures.3630 | 1499.02 (1499.02..1736.22) | 1431.95 (1431.95..2180.22) | -4% |  | 635,048 -> 635,048 (+0%) | same | same |
| read.MarketHistory.gasdaily.12m | 215.23 (215.23..238.21) | 206.92 (206.92..234.88) | -4% |  | 51,226 -> 51,226 (+0%) | same | same |
| read.MarketHistory.iferc.120m | 151.70 (151.70..283.15) | 142.91 (142.91..163.27) | -6% |  | 18,987 -> 18,987 (+0%) | same | same |
