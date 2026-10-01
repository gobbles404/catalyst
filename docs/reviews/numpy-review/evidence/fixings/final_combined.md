as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.FuturesFixings.260 | 76.50 (76.50..99.66) | 56.07 (56.07..80.87) | -27% |  | 11,194 -> 8,495 (-24%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.2600 | 247.59 (247.59..445.53) | 107.82 (107.82..173.37) | -56% | down | 93,094 -> 69,335 (-26%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.26000 | 1711.86 (1711.86..2760.15) | 622.84 (622.84..1037.90) | -64% | down | 912,094 -> 677,735 (-26%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.260.h1000 | 113.66 (113.66..171.03) | 94.22 (94.22..131.84) | -17% |  | 18,394 -> 15,695 (-15%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.2600.h1000 | 512.90 (512.90..764.59) | 201.16 (201.16..292.45) | -61% | down | 100,294 -> 76,535 (-24%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.FuturesFixings.260.h10000 | 482.96 (482.96..681.15) | 439.00 (439.00..499.67) | -9% |  | 90,394 -> 87,695 (-3%) | ndarray.any: 4->3; ufunc.reduce: 4->3 | same |
| create.GasDailyFixings.36500 | 919.85 (919.85..1735.36) | 614.21 (614.21..1058.26) | -33% |  | 1,205,539 -> 913,387 (-24%) | ndarray.view: 0->1 | same |
| create.GasDailyFixings.365 | 36.09 (36.09..49.92) | 31.86 (31.86..44.15) | -12% |  | 13,084 -> 10,012 (-23%) | ndarray.view: 0->1 | same |
| create.GasDailyFixings.3652 | 70.99 (70.99..130.15) | 53.31 (53.31..66.94) | -25% | down | 121,555 -> 92,187 (-24%) | ndarray.view: 0->1 | same |
| create.MarketHistory.futures.360 | 27.78 (27.78..37.32) | 27.05 (27.05..29.93) | -3% |  | 3,504 -> 3,504 (+0%) | same | same |
| create.MarketHistory.futures.3630 | 29.36 (29.36..70.43) | 30.40 (30.40..41.61) | +4% |  | 16,584 -> 16,584 (+0%) | same | same |
| create.MarketHistory.futures.36000 | 36.12 (36.12..49.77) | 36.79 (36.79..59.64) | +2% |  | 146,064 -> 146,064 (+0%) | same | same |
| create.MarketHistory.gasdaily.12m | 29.14 (29.14..50.70) | 29.93 (29.93..34.02) | +3% |  | 7,388 -> 7,388 (+0%) | same | same |
| create.MarketHistory.gasdaily.120m | 33.25 (33.25..52.32) | 32.71 (32.71..44.35) | -2% |  | 19,964 -> 19,964 (+0%) | same | same |
