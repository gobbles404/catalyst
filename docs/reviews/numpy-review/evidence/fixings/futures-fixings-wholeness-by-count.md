as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.FuturesFixings.260 | 121.69 (121.69..198.23) | 61.06 (61.06..116.50) | -50% | down | 11,194 -> 8,495 (-24%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.2600 | 288.25 (288.25..420.76) | 147.34 (147.34..193.09) | -49% | down | 93,094 -> 69,335 (-26%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.26000 | 1858.19 (1858.19..3200.03) | 836.35 (836.35..1186.40) | -55% | down | 912,094 -> 677,735 (-26%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.260.h1000 | 158.81 (158.81..238.19) | 86.57 (86.57..201.12) | -45% |  | 18,394 -> 15,695 (-15%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.2600.h1000 | 589.25 (589.25..1136.61) | 210.09 (210.09..345.76) | -64% | down | 100,294 -> 76,535 (-24%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.260.h10000 | 551.55 (551.55..953.91) | 611.60 (611.60..798.02) | +11% |  | 90,394 -> 87,695 (-3%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
