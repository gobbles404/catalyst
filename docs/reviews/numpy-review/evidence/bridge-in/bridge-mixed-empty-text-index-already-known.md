as-is tree: scratch/verify/bridge-in/trees/c6/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-in/trees/c7/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.CountMixed.10k | 23.60 (23.60..25.37) | 23.39 (23.39..31.62) | -1% |  | 248 -> 248 (+0%) | same | same |
| reject.CountMixed.empty-deep.10k | 156.57 (156.57..177.56) | 149.29 (149.29..187.49) | -5% |  | 103,372 -> 103,372 (+0%) | ndarray.ravel: 3->2 | _cell: 1->0 |
