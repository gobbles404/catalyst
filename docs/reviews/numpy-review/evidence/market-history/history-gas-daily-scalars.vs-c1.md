as-is tree: scratch/verify/market-history/trees/c1/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.MarketHistory.gasdaily.12m | 16.58 (16.58..28.46) | 17.60 (17.60..22.77) | +6% |  | 4,770 -> 4,514 (-5%) | generic.astype: 0->1; ndarray.searchsorted: 2->0; ndarray.view: 1->0; numpy.arange: 0->1 | _every_fixed_day: 1->0; _inside: 1->0 |
| create.MarketHistory.gasdaily.120m | 16.21 (16.21..30.20) | 16.28 (16.28..26.42) | +0% |  | 4,773 -> 4,564 (-4%) | generic.astype: 0->1; ndarray.searchsorted: 2->0; ndarray.view: 1->0; numpy.arange: 0->1 | _every_fixed_day: 1->0; _inside: 1->0 |
| history.gasdaily.allfixed120m | 27.14 (27.14..37.71) | 19.10 (19.10..30.90) | -30% |  | 59,141 -> 58,932 (-0%) | generic.astype: 0->1; ndarray.searchsorted: 2->0; ndarray.view: 1->0; numpy.arange: 0->1 | _every_fixed_day: 1->0; _inside: 1->0 |
| history.gasdaily.series26000x12m | 16.80 (16.80..26.02) | 18.52 (18.52..27.64) | +10% |  | 4,773 -> 4,564 (-4%) | generic.astype: 0->1; ndarray.searchsorted: 2->0; ndarray.view: 1->0; numpy.arange: 0->1 | _every_fixed_day: 1->0; _inside: 1->0 |
| history.reject.gasdaily.short120m | 51.11 (51.11..79.25) | 11.41 (11.41..19.17) | -78% | down | 44,512 -> 1,987 (-96%) | generic.astype: 0->1; ndarray.any: 1->0; ndarray.argmax: 1->0; ndarray.searchsorted: 2->0; ndarray.view: 1->0; numpy.zeros: 1->0; ufunc.reduce: 1->0 | _every_fixed_day: 1->0; _inside: 1->0 |
