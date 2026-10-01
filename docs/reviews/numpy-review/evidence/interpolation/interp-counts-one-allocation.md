as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 263.02 (263.02..721.15) | 245.93 (245.93..500.48) | -6% |  | 216,235 -> 216,251 (+0%) | ndarray.astype: 3->2; ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors12.3630 | 149.24 (149.24..200.24) | 147.57 (147.57..268.10) | -1% |  | 89,570 -> 89,586 (+0%) | ndarray.astype: 3->2; ndarray.view: 0->1 | same |
| create.DiscountCurve.daily.365 | 130.08 (130.08..205.64) | 104.52 (104.52..228.15) | -20% |  | 23,541 -> 23,557 (+0%) | ndarray.astype: 3->2; ndarray.view: 0->1 | same |
| create.DiscountCurve.daily.36500 | 2755.01 (2755.01..4974.53) | 2636.58 (2636.58..4515.86) | -4% |  | 2,155,506 -> 2,155,522 (+0%) | ndarray.astype: 3->2; ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors12.36500 | 586.76 (586.76..860.12) | 570.24 (570.24..808.04) | -3% |  | 878,402 -> 878,418 (+0%) | ndarray.astype: 3->2; ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors1200.36500 | 1202.14 (1202.14..2958.34) | 1229.30 (1229.30..2155.70) | +2% |  | 907,310 -> 907,326 (+0%) | ndarray.astype: 3->2; ndarray.view: 0->1 | same |
