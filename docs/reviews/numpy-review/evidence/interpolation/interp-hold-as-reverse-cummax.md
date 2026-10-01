as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 270.23 (270.23..561.18) | 222.27 (222.27..745.27) | -18% |  | 216,235 -> 215,907 (-0%) | ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 | same |
| create.DiscountCurve.anchors12.3630 | 157.86 (157.86..400.72) | 120.09 (120.09..303.24) | -24% |  | 89,570 -> 89,242 (-0%) | ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 | same |
| create.DiscountCurve.daily.365 | 119.80 (119.80..227.21) | 112.88 (112.88..146.39) | -6% |  | 23,541 -> 23,213 (-1%) | ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 | same |
| create.DiscountCurve.daily.36500 | 2811.08 (2811.08..4049.95) | 2828.82 (2828.82..6130.04) | +1% |  | 2,155,506 -> 2,155,178 (-0%) | ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 | same |
| create.DiscountCurve.anchors12.36500 | 604.26 (604.26..950.25) | 606.03 (606.03..1218.47) | +0% |  | 878,402 -> 878,074 (-0%) | ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 | same |
| create.DiscountCurve.anchors1200.36500 | 1149.73 (1149.73..2905.16) | 693.47 (693.47..1504.36) | -40% |  | 907,310 -> 906,982 (-0%) | ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.accumulate: 0->1 | same |
