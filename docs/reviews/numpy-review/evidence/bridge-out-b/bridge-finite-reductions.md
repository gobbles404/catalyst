as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-out-b/snap/finite/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.EchoColumn.10k | 8.74 (8.74..15.71) | 10.36 (10.36..13.74) | +18% |  | 10,385 -> 320 (-97%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| probe.RowSums.100x100 | 12.70 (12.70..15.98) | 13.50 (13.50..15.59) | +6% |  | 1,728 -> 1,728 (+0%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 2->3 | same |
| probe.Grid.5000x2 | 20.21 (20.21..39.97) | 22.02 (22.02..36.55) | +9% |  | 90,385 -> 80,320 (-11%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| probe.EchoColumn.100 | 5.02 (5.02..9.22) | 5.29 (5.29..9.23) | +6% |  | 485 -> 320 (-34%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| out.FloatColumn.100 | 4.24 (4.24..7.66) | 4.79 (4.79..7.07) | +13% |  | 389 -> 224 (-42%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| out.Grid.100 | 3.73 (3.73..6.97) | 4.49 (4.49..6.53) | +20% |  | 293 -> 192 (-34%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| out.FloatColumn.10k | 7.43 (7.43..15.51) | 9.72 (9.72..13.26) | +31% |  | 10,289 -> 224 (-98%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| out.Grid.10k | 7.46 (7.46..12.05) | 9.01 (9.01..13.23) | +21% |  | 10,193 -> 192 (-98%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| out.FloatColumn.100k | 43.24 (43.24..55.91) | 51.28 (51.28..61.21) | +19% |  | 100,289 -> 224 (-100%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
| out.Grid.100k | 45.22 (45.22..78.80) | 46.97 (46.97..68.83) | +4% |  | 100,193 -> 192 (-100%) | ndarray.all: 1->0; ndarray.max: 0->1; ndarray.min: 0->1; ufunc.reduce: 1->2 | same |
