as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.MarketHistory.gasdaily.12m | 31.15 (31.15..36.99) | 16.20 (16.20..26.70) | -48% | down | 7,388 -> 4,561 (-38%) | generic.astype: 0->1; ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; numpy.arange: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _every_fixed_day: 1->0 |
| create.MarketHistory.gasdaily.120m | 32.48 (32.48..50.80) | 15.63 (15.63..27.03) | -52% | down | 19,964 -> 4,564 (-77%) | generic.astype: 0->1; ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; numpy.arange: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _every_fixed_day: 1->0 |
| history.gasdaily.allfixed120m | 69.08 (69.08..127.83) | 20.21 (20.21..31.45) | -71% | down | 95,736 -> 58,932 (-38%) | generic.astype: 0->1; ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; numpy.arange: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _every_fixed_day: 1->0 |
| history.gasdaily.series26000x12m | 188.12 (188.12..216.31) | 16.57 (16.57..27.23) | -91% | down | 442,720 -> 4,564 (-99%) | generic.astype: 0->1; ndarray.any: 2->0; ndarray.astype: 1->0; ndarray.copy: 0->1; numpy.arange: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _every_fixed_day: 1->0 |
| history.reject.gasdaily.short120m | 60.81 (60.81..103.45) | 13.09 (13.09..25.55) | -78% | down | 80,948 -> 1,987 (-98%) | generic.astype: 0->1; ndarray.any: 2->0; ndarray.argmax: 1->0; ndarray.astype: 1->0; numpy.zeros: 1->0; ufunc.reduce: 2->0 | _every_fixed_day: 1->0 |
