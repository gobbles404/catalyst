as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-in/trees/c3/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| look.FirstOfDates.100 | 15.96 (15.96..22.29) | 18.56 (18.56..29.68) | +16% |  | 2,892 -> 2,892 (+0%) | same | same |
| create.ValuationDate | 7.29 (7.29..12.40) | 4.28 (4.28..8.96) | -41% |  | 1,144 -> 272 (-76%) | same | same |
| read.ValuationDate | 51.52 (51.52..113.64) | 55.13 (55.13..98.38) | +7% |  | 1,671 -> 1,671 (+0%) | same | same |
