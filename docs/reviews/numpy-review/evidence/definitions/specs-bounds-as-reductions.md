as-is tree: <repo>/src/goosedove/__init__.py
proposed tree: worktrees/wf_9922a729-5fc-2/src/goosedove/__init__.py
rounds: 5, batches: 7, batch target: 20.0 ms; 'moved' means the proposed spread lies wholly outside the as-is spread

| scenario | as-is us median (spread) | proposed us median (spread) | change | moved | peak bytes as-is -> proposed | numpy ledger diff | package ledger diff |
|---|---:|---:|---:|---|---:|---|---|
| create.ContractSpecifications.120 | 133.04 (133.04..301.93) | 175.94 (175.94..283.11) | +32% |  | 13,131 -> 13,131 (+0%) | ndarray.any: 9->6; ndarray.min: 0->1 | same |
| create.ContractSpecifications.12 | 96.67 (96.67..169.10) | 86.74 (86.74..245.62) | -10% |  | 3,723 -> 3,723 (+0%) | ndarray.any: 9->6; ndarray.min: 0->1 | same |
| create.ContractSpecifications.1200 | 504.91 (504.91..740.79) | 508.92 (508.92..1040.61) | +1% |  | 77,515 -> 77,515 (+0%) | ndarray.any: 9->6; ndarray.min: 0->1 | same |
| create.ContractSpecifications.12000 | 3785.13 (3785.13..7284.32) | 3902.70 (3902.70..11564.23) | +3% |  | 848,331 -> 848,331 (+0%) | ndarray.any: 9->6; ndarray.min: 0->1 | same |
| reject.ContractSpecifications.fee-last.1200 | 459.76 (459.76..807.91) | 643.85 (643.85..1623.76) | +40% |  | 77,515 -> 77,515 (+0%) | ndarray.any: 9->6; ndarray.min: 0->1 | same |
| create.Index.futures | 6.74 (6.74..14.34) | 7.95 (7.95..15.40) | +18% |  | 330 -> 330 (+0%) | same | same |
