as-is tree: scratch/verify/fixings/trees/after_c2/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.FuturesFixings.260 | 50.87 (50.87..63.92) | 50.61 (50.61..67.19) | -1% |  | 8,495 -> 8,495 (+0%) | ndarray.all: 0->1; ndarray.any: 3->2 | same |
| create.FuturesFixings.2600 | 107.47 (107.47..185.57) | 103.47 (103.47..119.80) | -4% |  | 69,335 -> 69,335 (+0%) | ndarray.all: 0->1; ndarray.any: 3->2 | same |
| create.FuturesFixings.26000 | 643.02 (643.02..781.21) | 617.10 (617.10..696.62) | -4% |  | 677,735 -> 677,735 (+0%) | ndarray.all: 0->1; ndarray.any: 3->2 | same |
| create.FuturesFixings.260.h1000 | 85.17 (85.17..95.56) | 83.71 (83.71..100.32) | -2% |  | 15,695 -> 15,695 (+0%) | ndarray.all: 0->1; ndarray.any: 3->2 | same |
| create.FuturesFixings.2600.h1000 | 193.37 (193.37..250.41) | 206.92 (206.92..255.48) | +7% |  | 76,535 -> 76,535 (+0%) | ndarray.all: 0->1; ndarray.any: 3->2 | same |
| create.FuturesFixings.260.h10000 | 453.06 (453.06..524.10) | 430.84 (430.84..584.32) | -5% |  | 87,695 -> 87,695 (+0%) | ndarray.all: 0->1; ndarray.any: 3->2 | same |
