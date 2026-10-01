as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 274.64 (274.64..491.46) | 125.09 (125.09..213.45) | -54% | down | 216,235 -> 99,435 (-54%) | ndarray.astype: 3->2; ndarray.copy: 0->1; ndarray.repeat: 1->0; numpy.arange: 2->1; numpy.asarray: 2->1 | same |
| create.DiscountCurve.anchors12.3630 | 154.31 (154.31..242.02) | 146.45 (146.45..186.05) | -5% |  | 89,570 -> 89,570 (+0%) | same | same |
| create.DiscountCurve.daily.365 | 116.85 (116.85..256.58) | 68.26 (68.26..89.46) | -42% | down | 23,541 -> 11,253 (-52%) | ndarray.astype: 3->2; ndarray.copy: 0->1; ndarray.repeat: 1->0; numpy.arange: 2->1; numpy.asarray: 2->1 | same |
| create.DiscountCurve.daily.36500 | 2787.28 (2787.28..5983.90) | 1043.48 (1043.48..3363.72) | -63% |  | 2,155,506 -> 986,898 (-54%) | ndarray.astype: 3->2; ndarray.copy: 0->1; ndarray.repeat: 1->0; numpy.arange: 2->1; numpy.asarray: 2->1 | same |
| create.DiscountCurve.anchors12.36500 | 609.53 (609.53..1128.66) | 607.63 (607.63..984.40) | -0% |  | 878,402 -> 878,402 (+0%) | same | same |
| create.DiscountCurve.anchors1200.36500 | 687.18 (687.18..1610.09) | 657.60 (657.60..1127.29) | -4% |  | 907,310 -> 907,310 (+0%) | same | same |
