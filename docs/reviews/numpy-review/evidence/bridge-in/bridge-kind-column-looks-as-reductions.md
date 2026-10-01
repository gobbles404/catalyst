as-is tree: scratch/verify/bridge-in/trees/c4base/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-in/trees/c4/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.SumQuantity.10k | 110.51 (110.51..276.97) | 96.07 (96.07..396.04) | -13% |  | 26,048 -> 23,548 (-10%) | ndarray.any: 3->0; ndarray.max: 1->4; ndarray.min: 1->3; ufunc.reduce: 7->9 | same |
| create.DiscountCurve.daily.3631 | 243.12 (243.12..422.27) | 225.78 (225.78..409.71) | -7% |  | 216,347 -> 216,347 (+0%) | ndarray.any: 4->3; ndarray.max: 1->2 | same |
| create.DiscountCurve.anchors12.3630 | 150.19 (150.19..244.31) | 149.55 (149.55..238.69) | -0% |  | 89,682 -> 89,682 (+0%) | ndarray.any: 4->3; ndarray.max: 1->2 | same |
| create.ContractSpecifications.120 | 71.37 (71.37..104.16) | 62.15 (62.15..103.07) | -13% |  | 12,904 -> 12,904 (+0%) | ndarray.any: 9->4; ndarray.max: 0->5; ndarray.min: 0->2; ufunc.reduce: 9->11 | same |
| read.DiscountCurve.3631 | 108.87 (108.87..222.15) | 99.26 (99.26..258.54) | -9% |  | 128,381 -> 128,381 (+0%) | same | same |
| read.ContractSpecifications.120 | 86.92 (86.92..176.80) | 72.27 (72.27..130.80) | -17% |  | 16,841 -> 16,841 (+0%) | same | same |
