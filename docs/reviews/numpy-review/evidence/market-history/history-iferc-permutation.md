as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.MarketHistory.iferc.120m | 43.15 (43.15..80.84) | 37.35 (37.35..57.19) | -13% |  | 11,520 -> 6,488 (-44%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| create.MarketHistory.iferc.1200m | 284.49 (284.49..429.58) | 257.09 (257.09..456.82) | -10% |  | 95,220 -> 81,516 (-14%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| history.iferc.shuffled120m | 52.26 (52.26..76.81) | 37.28 (37.28..68.41) | -29% |  | 11,520 -> 6,488 (-44%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| history.iferc.shuffled1200m | 319.35 (319.35..537.75) | 283.98 (283.98..486.38) | -11% |  | 95,220 -> 81,516 (-14%) | ndarray.any: 2->0; ndarray.argsort: 1->0; ndarray.max: 0->1; numpy.arange: 0->1; numpy.empty: 0->1; numpy.zeros: 1->0; ufunc.reduce: 2->1 | same |
| history.reject.iferc.missing120m | 35.93 (35.93..40.60) | 35.62 (35.62..50.73) | -1% |  | 6,855 -> 6,648 (-3%) | ndarray.any: 2->0; ndarray.max: 0->1; ufunc.reduce: 2->1 | same |
| history.reject.iferc.unfixed120m | 33.36 (33.36..58.00) | 36.46 (36.46..57.88) | +9% |  | 6,482 -> 6,274 (-3%) | ndarray.any: 1->0; ndarray.max: 0->1 | same |
| read.MarketHistory.iferc.120m | 148.76 (148.76..236.96) | 143.91 (143.91..250.24) | -3% |  | 18,987 -> 18,987 (+0%) | same | same |
