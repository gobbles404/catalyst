as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_0d4f8983-1f8-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.GasDailyFixings.36500 | 1030.04 (1030.04..1659.73) | 723.06 (723.06..1210.97) | -30% |  | 1,205,539 -> 913,387 (-24%) | ndarray.view: 0->1 | same |
| create.GasDailyFixings.365 | 34.44 (34.44..76.94) | 34.03 (34.03..54.35) | -1% |  | 13,084 -> 10,012 (-23%) | ndarray.view: 0->1 | same |
| create.GasDailyFixings.3652 | 74.84 (74.84..153.64) | 54.65 (54.65..107.78) | -27% |  | 121,555 -> 92,187 (-24%) | ndarray.view: 0->1 | same |
