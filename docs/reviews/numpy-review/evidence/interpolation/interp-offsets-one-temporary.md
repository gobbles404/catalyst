as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 271.85 (271.85..526.02) | 368.45 (368.45..624.80) | +36% |  | 216,235 -> 216,235 (+0%) | ndarray.astype: 3->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors12.3630 | 188.97 (188.97..360.51) | 193.45 (193.45..261.32) | +2% |  | 89,570 -> 89,570 (+0%) | ndarray.astype: 3->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.daily.365 | 111.98 (111.98..315.79) | 106.40 (106.40..237.74) | -5% |  | 23,541 -> 23,541 (+0%) | ndarray.astype: 3->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.daily.36500 | 3337.20 (3337.20..8090.98) | 2756.62 (2756.62..8526.43) | -17% |  | 2,155,506 -> 2,155,506 (+0%) | ndarray.astype: 3->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors12.36500 | 616.65 (616.65..1010.36) | 582.76 (582.76..1550.38) | -5% |  | 878,402 -> 878,402 (+0%) | ndarray.astype: 3->4; ndarray.view: 0->1 | same |
| create.DiscountCurve.anchors1200.36500 | 1263.45 (1263.45..2662.38) | 1142.99 (1142.99..2567.23) | -10% |  | 907,310 -> 907,310 (+0%) | ndarray.astype: 3->4; ndarray.view: 0->1 | same |
