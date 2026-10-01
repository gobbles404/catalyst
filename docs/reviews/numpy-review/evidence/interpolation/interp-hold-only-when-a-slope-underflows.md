as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-1/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.DiscountCurve.daily.3631 | 272.65 (272.65..434.70) | 219.16 (219.16..285.81) | -20% |  | 216,235 -> 215,907 (-0%) | ndarray.any: 5->6; ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.reduce: 5->6 | same |
| create.DiscountCurve.anchors12.3630 | 142.94 (142.94..228.16) | 124.66 (124.66..223.57) | -13% |  | 89,570 -> 89,242 (-0%) | ndarray.any: 5->6; ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.reduce: 5->6 | same |
| create.DiscountCurve.daily.365 | 107.78 (107.78..162.59) | 93.39 (93.39..107.20) | -13% | down | 23,541 -> 23,213 (-1%) | ndarray.any: 5->6; ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.reduce: 5->6 | same |
| create.DiscountCurve.daily.36500 | 2629.24 (2629.24..3610.98) | 2538.54 (2538.54..4416.53) | -3% |  | 2,155,506 -> 2,155,178 (-0%) | ndarray.any: 5->6; ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.reduce: 5->6 | same |
| create.DiscountCurve.anchors12.36500 | 556.70 (556.70..946.27) | 470.02 (470.02..1061.46) | -16% |  | 878,402 -> 878,074 (-0%) | ndarray.any: 5->6; ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.reduce: 5->6 | same |
| create.DiscountCurve.anchors1200.36500 | 1160.39 (1160.39..1747.05) | 546.02 (546.02..1053.96) | -53% | down | 907,310 -> 906,982 (-0%) | ndarray.any: 5->6; ndarray.astype: 3->2; ndarray.repeat: 1->0; ufunc.reduce: 5->6 | same |
