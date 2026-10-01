as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: scratch/verify/bridge-in/trees/c2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| probe.SumQuantity.10k | 330.03 (330.03..631.46) | 100.52 (100.52..177.60) | -70% | down | 135,184 -> 43,940 (-67%) | ndarray.cumsum: 1->0; ndarray.sum: 3->1; numpy.array: 1->0; ufunc.reduce: 7->5 | _refine.<locals>.<lambda>: 1->0; _text_places: 1->0 |
| create.DiscountCurve.daily.3631 | 238.70 (238.70..383.84) | 231.08 (231.08..287.75) | -3% |  | 216,235 -> 216,235 (+0%) | same | same |
| create.DiscountCurve.anchors12.3630 | 144.95 (144.95..199.56) | 136.35 (136.35..177.31) | -6% |  | 89,570 -> 89,570 (+0%) | same | same |
| create.ContractSpecifications.120 | 122.33 (122.33..153.58) | 70.59 (70.59..80.86) | -42% | down | 13,080 -> 12,904 (-1%) | ndarray.cumsum: 1->0; ndarray.sum: 3->0; numpy.array: 4->3; ufunc.reduce: 12->9 | _refine.<locals>.<lambda>: 1->0; _text_places: 1->0 |
| read.DiscountCurve.3631 | 97.94 (97.94..155.61) | 105.25 (105.25..181.72) | +7% |  | 128,381 -> 128,381 (+0%) | same | same |
| read.ContractSpecifications.120 | 71.08 (71.08..139.74) | 77.85 (77.85..100.06) | +10% |  | 16,841 -> 16,841 (+0%) | same | same |
