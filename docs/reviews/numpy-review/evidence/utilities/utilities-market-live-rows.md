as-is tree: scratch/verify/utilities/trees/after_c2/src/goosedove/__init__.py
proposed tree: worktrees/wf_1c4545af-6ae-4/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| read.Market.futures.360 | 212.01 (212.01..396.69) | 207.47 (207.47..364.55) | -2% |  | 51,123 -> 51,123 (+0%) | same | same |
| read.Market.futures.3630 | 1039.65 (1039.65..1787.40) | 1133.03 (1133.03..1798.25) | +9% |  | 505,677 -> 505,677 (+0%) | same | same |
| read.Market.futures.36000 | 12338.38 (12338.38..17100.08) | 11153.75 (11153.75..18016.58) | -10% |  | 5,005,083 -> 5,005,083 (+0%) | same | same |
| read.Market.gasdaily.12m | 212.52 (212.52..344.96) | 209.51 (209.51..368.53) | -1% |  | 48,698 -> 48,698 (+0%) | same | same |
