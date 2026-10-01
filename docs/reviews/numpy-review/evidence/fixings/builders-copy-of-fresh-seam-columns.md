as-is tree: scratch/verify/fixings/trees/after_c4/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.FuturesFixings.260 | 55.51 (55.51..60.80) | 48.36 (48.36..108.56) | -13% |  | 8,495 -> 6,255 (-26%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.FuturesFixings.2600 | 109.97 (109.97..190.87) | 106.56 (106.56..227.90) | -3% |  | 69,335 -> 45,392 (-35%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.FuturesFixings.26000 | 634.66 (634.66..898.71) | 615.34 (615.34..1094.91) | -3% |  | 677,735 -> 443,192 (-35%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.FuturesFixings.260.h1000 | 97.21 (97.21..144.18) | 93.88 (93.88..146.90) | -3% |  | 15,695 -> 13,455 (-14%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.FuturesFixings.2600.h1000 | 223.25 (223.25..303.73) | 223.65 (223.65..405.80) | +0% |  | 76,535 -> 45,392 (-41%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.FuturesFixings.260.h10000 | 469.24 (469.24..613.39) | 577.48 (577.48..725.13) | +23% |  | 87,695 -> 85,455 (-3%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.GasDailyFixings.36500 | 581.72 (581.72..721.03) | 300.30 (300.30..787.87) | -48% |  | 913,387 -> 621,692 (-32%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.GasDailyFixings.365 | 33.90 (33.90..55.33) | 33.67 (33.67..79.42) | -1% |  | 10,012 -> 7,397 (-26%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
| create.GasDailyFixings.3652 | 55.82 (55.82..112.81) | 64.09 (64.09..97.60) | +15% |  | 92,187 -> 63,276 (-31%) | numpy.array: 2->0; numpy.asarray: 0->2 | same |
