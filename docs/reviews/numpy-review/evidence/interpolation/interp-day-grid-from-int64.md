as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 259.68 (259.68..484.03) | 298.81 (298.81..346.88) | +15% |  | 216,235 -> 216,459 (+0%) | ndarray.view: 0->2 | same |
| create.DiscountCurve.anchors12.3630 | 166.99 (166.99..202.68) | 156.71 (156.71..190.00) | -6% |  | 89,570 -> 89,794 (+0%) | ndarray.view: 0->2 | same |
| create.DiscountCurve.daily.365 | 113.93 (113.93..220.90) | 110.05 (110.05..278.56) | -3% |  | 23,541 -> 23,765 (+1%) | ndarray.view: 0->2 | same |
| create.DiscountCurve.daily.36500 | 2865.22 (2865.22..3157.93) | 2580.27 (2580.27..5186.17) | -10% |  | 2,155,506 -> 2,155,730 (+0%) | ndarray.view: 0->2 | same |
| create.DiscountCurve.anchors12.36500 | 610.35 (610.35..987.75) | 552.97 (552.97..842.52) | -9% |  | 878,402 -> 878,626 (+0%) | ndarray.view: 0->2 | same |
| create.DiscountCurve.anchors1200.36500 | 1278.58 (1278.58..1819.35) | 1122.98 (1122.98..1647.87) | -12% |  | 907,310 -> 907,534 (+0%) | ndarray.view: 0->2 | same |
| read.DiscountCurve.3631 | 123.04 (123.04..188.10) | 98.27 (98.27..333.19) | -20% |  | 128,381 -> 128,381 (+0%) | same | same |
