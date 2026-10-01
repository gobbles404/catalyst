as-is tree: scratch/verify/bridge-in/trees/c5/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-in/trees/c6/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| reject.SumArray.text-last.10k | 14.99 (14.99..33.66) | 15.12 (15.12..22.81) | +1% |  | 20,640 -> 20,640 (+0%) | ndarray.item: 0->1 | same |
| reject.CountMixed.empty-deep.10k | 169.67 (169.67..323.93) | 167.89 (167.89..316.54) | -1% |  | 103,372 -> 103,372 (+0%) | ndarray.item: 0->1 | same |
| reject.FirstOfDates.fraction-deep.10k | 50.80 (50.80..79.98) | 51.97 (51.97..80.73) | +2% |  | 90,449 -> 90,449 (+0%) | ndarray.item: 0->2 | same |
